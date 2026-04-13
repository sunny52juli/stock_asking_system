"""Hooks 执行器 - PreToolUse/PostToolUse/Stop 钩子系统.

- Exit code 协议：0=通过, 1=警告继续, 2=阻止执行
- 支持命令型 hooks（外部脚本）
- 匹配器模式（根据工具名称触发不同 hooks）
- Shell 注入防护（严格元字符检测）
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from src.agent.config import HookMatcherConfig, HooksConfig

logger = logging.getLogger(__name__)

# 严格拒绝的注入模式: $(cmd), `cmd`, ${VAR} (变量展开), ${...} (花括号展开),
# ; (命令分隔), | (管道), & (后台/逻辑运算符), \n (换行注入)
# 不拒绝路径中孤立的 '$' 字符 (如 /home/user/path$name)
_SHELL_INJECTION_PATTERNS = re.compile(r"(\$\(|`|\$\{|;|\||&|\n)")


class _HookPayloadEncoder(json.JSONEncoder):
    """Hook Payload 的自定义 JSON 编码器.
    
    处理 LangChain 消息对象和其他不可序列化的类型。
    """
    def default(self, obj: Any) -> Any:
        # 处理 LangChain 消息对象
        if hasattr(obj, 'content') and hasattr(obj, 'type'):
            return {
                "type": getattr(obj, 'type', 'unknown'),
                "content": str(getattr(obj, 'content', '')),
            }
        # 处理其他有 __dict__ 的对象
        if hasattr(obj, '__dict__'):
            return str(obj)
        # 默认行为
        return super().default(obj)


class HookResult:
    """Hook 执行结果."""

    PASSED = 0      # 通过，继续执行
    WARNING = 1     # 警告，记录日志但继续
    BLOCKED = 2     # 阻止，返回错误给 Agent

    def __init__(self, exit_code: int, message: str = ""):
        self.exit_code = exit_code
        self.message = message

    @property
    def is_passed(self) -> bool:
        return self.exit_code == self.PASSED

    @property
    def is_warning(self) -> bool:
        return self.exit_code == self.WARNING

    @property
    def is_blocked(self) -> bool:
        return self.exit_code == self.BLOCKED


class HookExecutor:
    """Hooks 执行器.

    使用示例：
        executor = HookExecutor(hooks_config, config_dir)
        
        # 在工具调用前执行
        result = executor.execute_pre_tool_use("run_screening", tool_input={...})
        if result.is_blocked:
            raise Exception(f"Hook blocked: {result.message}")
        
        # 在 Agent 结束时执行
        result = executor.execute_stop(session_data={...})
    """

    def __init__(self, hooks_config: HooksConfig, config_dir: Path):
        self.hooks_config = hooks_config
        self.config_dir = config_dir
        logger.warning(f"HookExecutor initialized with config_dir: {self.config_dir}")
        logger.warning(f"HookExecutor config_dir exists: {self.config_dir.exists()}")
        logger.warning(f"HookExecutor hooks directory: {self.config_dir / 'hooks'}")
        logger.warning(f"HookExecutor hooks directory exists: {(self.config_dir / 'hooks').exists()}")

    def execute_pre_tool_use(self, tool_name: str, tool_input: dict[str, Any]) -> HookResult:
        """执行 PreToolUse hooks.
        
        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            
        Returns:
            HookResult
        """
        return self._execute_hooks_for_event("PreToolUse", tool_name, tool_input)

    def execute_post_tool_use(self, tool_name: str, tool_output: Any) -> HookResult:
        """执行 PostToolUse hooks.
        
        Args:
            tool_name: 工具名称
            tool_output: 工具输出结果
            
        Returns:
            HookResult
        """
        return self._execute_hooks_for_event("PostToolUse", tool_name, {"output": str(tool_output)})

    def execute_stop(self, session_data: dict[str, Any]) -> HookResult:
        """执行 Stop hooks（Agent 会话结束时）.
        
        Args:
            session_data: 会话数据
            
        Returns:
            HookResult
        """
        return self._execute_hooks_for_event("Stop", None, session_data)

    def _execute_hooks_for_event(
        self, 
        event: str, 
        tool_name: str | None, 
        payload: dict[str, Any]
    ) -> HookResult:
        """为指定事件执行匹配的 hooks.
        
        Args:
            event: 事件类型（PreToolUse/PostToolUse/Stop）
            tool_name: 工具名称（可选）
            payload: 传递给 hook 的数据
            
        Returns:
            HookResult（最严重的结果）
        """
        # 支持字典和对象两种访问方式
        if isinstance(self.hooks_config, dict):
            if event == "PreToolUse":
                matchers = self.hooks_config.get("PreToolUse", [])
            elif event == "PostToolUse":
                matchers = self.hooks_config.get("PostToolUse", [])
            elif event == "Stop":
                matchers = self.hooks_config.get("Stop", [])
            else:
                logger.warning(f"Unknown event type: {event}")
                return HookResult(HookResult.PASSED)
        else:
            # Pydantic 对象访问
            if event == "PreToolUse":
                matchers = self.hooks_config.PreToolUse
            elif event == "PostToolUse":
                matchers = self.hooks_config.PostToolUse
            elif event == "Stop":
                matchers = self.hooks_config.Stop
            else:
                logger.warning(f"Unknown event type: {event}")
                return HookResult(HookResult.PASSED)

        worst_result = HookResult(HookResult.PASSED)

        for matcher_config in matchers:
            # 检查是否匹配
            if not self._matches(matcher_config, tool_name):
                continue

            # 执行所有配置的 hooks（支持字典和对象）
            if isinstance(matcher_config, dict):
                hooks_list = matcher_config.get("hooks", [])
            else:
                hooks_list = matcher_config.hooks
            
            for hook_config in hooks_list:
                result = self._execute_single_hook(hook_config, payload)
                
                # 更新最严重结果
                if result.exit_code > worst_result.exit_code:
                    worst_result = result
                
                # 如果被阻止，立即返回
                if result.is_blocked:
                    logger.warning(f"Hook blocked execution: {result.message}")
                    return result

        return worst_result

    def _matches(self, matcher_config, tool_name: str | None) -> bool:
        """检查工具名称是否匹配 hook 配置."""
        # 支持字典和对象两种访问方式
        if isinstance(matcher_config, dict):
            matcher = matcher_config.get("matcher")
        else:
            matcher = matcher_config.matcher
        
        if matcher is None:
            return True  # 无匹配器，始终执行
        
        if tool_name is None:
            return False
        
        # 简单通配符匹配
        pattern = matcher
        if pattern == "*":
            return True
        
        if "*" in pattern:
            # 转换为正则表达式
            import re
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(f"^{regex_pattern}$", tool_name))
        
        return pattern == tool_name

    def _execute_single_hook(self, hook_config, payload: dict[str, Any]) -> HookResult:
        """执行单个 hook 命令 - 增强版（带 Shell 注入防护）.
        
        Args:
            hook_config: Hook 配置
            payload: 传递给 hook 的数据（通过 stdin JSON）
            
        Returns:
            HookResult
        """
        # 支持字典和对象两种访问方式
        if isinstance(hook_config, dict):
            hook_type = hook_config.get("type", "command")
            command = hook_config.get("command", "")
        else:
            hook_type = hook_config.type
            command = hook_config.command
        
        if hook_type != "command":
            logger.warning(f"Unsupported hook type: {hook_type}")
            return HookResult(HookResult.PASSED)

        try:
            # 展开环境变量
            expanded_command = self._expand_env_vars(command)
            
            # Shell 注入安全检查
            self._validate_command(expanded_command)
            
            # 处理相对路径：如果命令中包含 Python 脚本且是相对路径，转换为基于 config_dir 的绝对路径
            args = shlex.split(expanded_command)
            if args and args[0] == "python" and len(args) > 1:
                script_path = Path(args[1])
                if not script_path.is_absolute():
                    # 相对路径，基于 config_dir 解析
                    absolute_script = self.config_dir / script_path
                    logger.debug(f"Hook script path resolution:")
                    logger.debug(f"  Original: {script_path}")
                    logger.debug(f"  Config dir: {self.config_dir}")
                    logger.debug(f"  Resolved: {absolute_script}")
                    logger.debug(f"  Exists: {absolute_script.exists()}")
                    
                    # 无论是否存在，都使用绝对路径（让错误信息更清晰）
                    args[1] = str(absolute_script)
            
            # 执行命令，通过 stdin 传递 JSON payload
            # 使用自定义编码器处理 LangChain 消息对象
            process = subprocess.run(
                args,
                input=json.dumps(payload, cls=_HookPayloadEncoder),
                capture_output=True,
                text=True,
                timeout=30,  # 30秒超时
                env=self._get_env_with_config_dir()
            )

            exit_code = process.returncode
            stderr_output = process.stderr.strip()
            stdout_output = process.stdout.strip()

            # 解析退出码
            if exit_code == 0:
                logger.debug(f"Hook passed: {expanded_command[:50]}...")
                return HookResult(HookResult.PASSED, stdout_output)
            elif exit_code == 1:
                logger.warning(f"Hook warning: {stderr_output or stdout_output}")
                return HookResult(HookResult.WARNING, stderr_output or stdout_output)
            elif exit_code == 2:
                logger.error(f"Hook blocked: {stderr_output or stdout_output}")
                return HookResult(HookResult.BLOCKED, stderr_output or stdout_output)
            else:
                logger.error(f"Hook failed with exit code {exit_code}: {stderr_output}")
                return HookResult(HookResult.BLOCKED, f"Hook execution failed: {stderr_output}")

        except ValueError as exc:
            # Shell 注入检查失败
            logger.error("Hook command 安全检查失败: %s", exc)
            return HookResult(HookResult.BLOCKED, str(exc))
        except subprocess.TimeoutExpired:
            logger.error(f"Hook execution timed out: {command}")
            return HookResult(HookResult.BLOCKED, "Hook execution timed out")
        except Exception as e:
            logger.error(f"Hook execution failed: {e}")
            return HookResult(HookResult.BLOCKED, f"Hook execution error: {str(e)}")

    def _expand_env_vars(self, command: str) -> str:
        """展开命令中的环境变量."""
        import os
        import re

        def replace_var(match: re.Match) -> str:
            var_expr = match.group(1)
            if ":-" in var_expr:
                var_name, default = var_expr.split(":-", 1)
                return os.environ.get(var_name, default)
            else:
                return os.environ.get(var_expr, "")

        return re.sub(r"\$\{([^}]+)\}", replace_var, command)

    def _get_env_with_config_dir(self) -> dict[str, str]:
        """获取包含 CONFIG_DIR 的环境变量."""
        import os
        env = os.environ.copy()
        env.setdefault("STOCK_ASKING_CONFIG_DIR", str(self.config_dir))
        return env

    @staticmethod
    def _validate_command(command: str) -> None:
        """拒绝含 shell 注入模式的命令。

        允许单引号/双引号、括号内英文/数字（rsi_14 等参数值）、路径中含 '$'。
        仅拒绝明确用于 shell 注入的模式: `` $( ` ${ ; | & `` 及换行符。
        
        Args:
            command: 待校验的命令字符串
            
        Raises:
            ValueError: 如果命令包含禁止的元字符
        """
        if _SHELL_INJECTION_PATTERNS.search(command):
            matched = _SHELL_INJECTION_PATTERNS.search(command).group(0)
            raise ValueError(
                f"命令包含禁止的 shell 元字符 {matched!r}: {command!r}。"
                "不允许使用 $( ` ${ ; | & 等符号，请使用纯命令+参数形式。"
            )
