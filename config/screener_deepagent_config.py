"""
Screener DeepAgent 配置模块 (含 data_accessor 类型别名，供 agent 与 bridge 共用).

复用 StockQueryConfig 的配置项 (含 get_api_config: DEFAULT_API_URL / DEFAULT_MODEL / DEFAULT_API_KEY).
本模块仅提供 Deep Agent 结构类配置：MCP 命令、脚本目录、skills 路径等.
LLM 的 api_key / model / base_url 由 get_api_config() 提供，agent 通过该接口建 LLM.

MCP 配置：优先从包目录 screener_mcp.json 读取 (mcpServers 下全部条目，支持 uv/uvx 及多 MCP), 失败则回退到本包 screener_mcp/server.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

import pandas as pd

# 延迟导入以避免循环导入
from utils.base_messages import COMMON_ERROR_MESSAGES, BaseMessageMixin
from utils.logger import get_logger

logger = get_logger(__name__)

# 类型别名：无参、返回 DataFrame 的 callable (agent 与 bridge 共用)
data_accessor = Callable[[], pd.DataFrame]


class ScreenerDeepAgentConfig(BaseMessageMixin):
    """Screener DeepAgent 配置类 (含 get_message 用于本模块 UI 消息)."""

    # ==================== Deep Agent 结构配置 ====================
    # Skills 目录路径
    SKILLS_DIR = Path(__file__).parent.parent / "screener_deepagent" / "skills"

    # ==================== MCP 服务配置 ====================
    # 默认使用 python 从 screener_mcp 文件夹加载；无 screener_mcp.json 或解析失败时回退
    MCP_SERVER_COMMAND = "python"
    _PROJECT_ROOT = Path(__file__).parent.parent
    MCP_SERVER_ARGS = [
        "-m",
        "screener_mcp.server"
    ]

    # MCP 服务超时 (秒)
    MCP_SERVER_TIMEOUT = 30

    # ==================== 筛选脚本输出配置 ====================

    DEFAULT_SCRIPTS_DIR = Path(__file__).parent.parent  / "screening_scripts"

    # ==================== 本模块 UI 错误消息 (解耦 StockQueryPrompts) ====================
    ERROR_MESSAGES = {
        **COMMON_ERROR_MESSAGES,
        "no_api_key": "未检测到 API 密钥，请设置环境变量 DEFAULT_API_KEY",
        "data_error": "数据加载失败：{error}",
        "query_failed": "查询失败：{error}",
        "api_error": "API 调用失败：{error}",
    }

    @classmethod
    def get_api_config(cls) -> dict:
        """获取 API 配置（直接导入 Config）"""
        from config.api_config import APIConfig
        return APIConfig.get_api_config()

    @classmethod
    def get_mcp_server_config_from_json(cls) -> list[dict] | None:
        """从 screener_mcp 文件夹下的 screener_mcp.json 读取全部 MCP 配置 (mcpServers 下每条目一个). 文件不存在或解析失败时返回 None."""
        mcp_json_path = Path(__file__).parent.parent / "screener_mcp" / "screener_mcp.json"
        if not mcp_json_path.is_file():
            logger.debug("screener_mcp.json 不存在，使用默认 MCP 配置：%s", mcp_json_path)
            return None
        try:
            raw = mcp_json_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("读取 screener_mcp.json 失败，使用默认 MCP 配置：%s", e)
            return None
        servers = data.get("mcpServers") or {}
        if not isinstance(servers, dict):
            logger.warning("screener_mcp.json 中 mcpServers 非对象，使用默认 MCP 配置")
            return None
        result: list[dict] = []
        for name, cfg in servers.items():
            if not cfg or not isinstance(cfg, dict):
                continue
            command = cfg.get("command")
            args = cfg.get("args")
            if not command or not isinstance(args, list):
                logger.warning("screener_mcp.json 中 [%s] command/args 无效，跳过", name)
                continue
            timeout = cfg.get("timeout")
            if timeout is None:
                timeout = cls.MCP_SERVER_TIMEOUT
            result.append({
                "name": str(name),
                "command": str(command),
                "args": list(args),
                "timeout": int(timeout),
            })
        if not result:
            logger.warning("screener_mcp.json 中未找到有效 mcpServers 条目，使用默认 MCP 配置")
            return None
        return result

    @classmethod
    def get_mcp_server_config(cls) -> list[dict]:
        """获取 MCP 服务器配置列表 (优先 screener_mcp.json 全部 mcpServers, 否则回退单条默认). 每项含 name, command, args, timeout."""
        from_json = cls.get_mcp_server_config_from_json()
        if from_json is not None:
            return from_json
        return [
            {
                "name": "screener-screener_mcp",
                "command": cls.MCP_SERVER_COMMAND,
                "args": cls.MCP_SERVER_ARGS,
                "timeout": cls.MCP_SERVER_TIMEOUT,
            }
        ]

    @classmethod
    def get_deep_agent_config(cls) -> dict:
        """获取 Deep Agent 结构配置 (路径、MCP 命令等). LLM 由 get_api_config() 提供."""
        return {
            "skills_dir": str(cls.SKILLS_DIR),
            "mcp_server_config": cls.get_mcp_server_config(),
        }

    @classmethod
    def get_scripts_dir(cls) -> Path:
        """获取筛选脚本输出目录 (默认项目级 screening_scripts/screening_scripts, 可设 SCREENER_SCRIPTS_DIR 覆盖)."""
        if os.environ.get("SCREENER_SCRIPTS_DIR"):
            scripts_dir = Path(os.environ["SCREENER_SCRIPTS_DIR"])
        else:
            scripts_dir = Path.cwd() / "screening_scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        return scripts_dir

    @classmethod
    def get_demo_queries(cls) -> list[str]:
        """获取演示查询列表 (供 run main/demo 使用)."""
        from config.strategy_des import StrategyDescriptions
        return StrategyDescriptions.get_demo_queries()
