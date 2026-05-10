"""交互式筛选条件编辑器 - 支持增量修改和即时预览."""

from __future__ import annotations

import json
import copy
import time
from typing import Any, Callable
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScreeningState:
    """筛选状态快照."""
    logic: dict
    candidates_count: int = 0
    execution_time: float = 0.0
    timestamp: str = ""
    
    def to_dict(self) -> dict:
        return {
            "logic": self.logic,
            "candidates_count": self.candidates_count,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ScreeningState":
        return cls(
            logic=data["logic"],
            candidates_count=data.get("candidates_count", 0),
            execution_time=data.get("execution_time", 0.0),
            timestamp=data.get("timestamp", "")
        )


class InteractiveConditionEditor:
    """交互式筛选条件编辑器.
    
    支持：
    1. 直接编辑表达式
    2. 参数微调
    3. 工具增删
    4. 即时预览效果
    5. 版本管理（撤销/重做/保存变体）
    """
    
    def __init__(self, initial_logic: dict | None = None):
        """初始化编辑器.
        
        Args:
            initial_logic: 初始筛选逻辑（可选）
        """
        self.current_state: ScreeningState | None = None
        self.history: list[ScreeningState] = []
        self.redo_stack: list[ScreeningState] = []
        
        if initial_logic:
            self.load_logic(initial_logic)
    
    def load_logic(self, logic: dict) -> None:
        """加载筛选逻辑."""
        state = ScreeningState(logic=copy.deepcopy(logic))
        self.current_state = state
        self.history.clear()
        self.redo_stack.clear()
        logger.info(f"[OK] 已加载筛选逻辑: {logic.get('name', '未命名')}")
    
    def show_current_state(self) -> None:
        """显示当前筛选状态."""
        if not self.current_state:
            logger.warning("[WARN] 未加载任何筛选逻辑")
            return
        
        logic = self.current_state.logic
        
        print("\n" + "="*70)
        print("📋 当前筛选逻辑")
        print("="*70)
        print(f"名称: {logic.get('name', '未命名')}")
        
        # [OK] 智能显示筛选说明
        rationale = logic.get('rationale', '')
        if rationale and rationale.strip():
            print(f"说明: {rationale}")
        else:
            # 如果没有说明，根据表达式和工具生成简要说明
            expression = logic.get('expression', '')
            tools = logic.get('tools', [])
            if expression and tools:
                tool_names = [t.get('tool', '') for t in tools if t.get('tool')]
                print(f"说明: 使用 {', '.join(tool_names)} 指标，条件: {expression[:50]}...")
            else:
                print(f"说明: 基于技术指标的量化筛选策略")
        
        print(f"\n表达式:")
        print(f"  {logic.get('expression', '无')}")
        
        tools = logic.get('tools', [])
        if tools:
            print(f"\n工具列表 ({len(tools)} 个):")
            for i, tool in enumerate(tools, 1):
                var = tool.get('var', 'N/A')
                tool_name = tool.get('tool', 'N/A')
                params = tool.get('params', {})
                print(f"  {i}. {var}: {tool_name}({params})")
        
        if self.current_state.candidates_count > 0:
            print(f"\n[DATA] 上次执行结果: {self.current_state.candidates_count} 只股票")
            print(f"⏱️  执行时间: {self.current_state.execution_time:.2f}s")
        
        print("="*70)
    
    def execute_and_preview(self, executor_func: Callable) -> dict:
        """执行筛选并预览结果.
        
        Args:
            executor_func: 执行函数，接收 screening_logic 返回 candidates
            
        Returns:
            执行结果
        """
        if not self.current_state:
            raise ValueError("未加载筛选逻辑")
        
        start_time = time.time()
        try:
            result = executor_func(self.current_state.logic)
            elapsed = time.time() - start_time
            
            # 更新状态
            self.current_state.candidates_count = len(result)
            self.current_state.execution_time = elapsed
            self.current_state.timestamp = datetime.now().isoformat()
            
            # 保存到历史
            self._save_to_history()
            
            # 显示预览
            self._show_execution_preview(result, elapsed)
            
            return result
            
        except Exception as e:
            logger.error(f"[ERROR] 执行失败: {e}")
            raise
    
    def adjust_expression(self, new_expression: str, executor_func=None) -> None:
        """调整筛选表达式.
        
        Args:
            new_expression: 新的表达式字符串
            executor_func: 可选的执行函数，如果提供则自动执行预览
        """
        if not self.current_state:
            raise ValueError("未加载筛选逻辑")
        
        old_expr = self.current_state.logic.get('expression', '')
        self.current_state.logic['expression'] = new_expression
        
        logger.info(f"✏️  表达式已更新:")
        logger.info(f"   旧: {old_expr}")
        logger.info(f"   新: {new_expression}")
        
        # [OK] 自动执行预览（如果提供了执行函数）
        if executor_func:
            print(f"\n🔄 自动执行预览...")
            try:
                self.execute_and_preview(executor_func)
            except Exception as e:
                logger.warning(f"[WARN]  预览执行失败: {e}")
    
    def adjust_parameter(self, var_name: str, param_name: str, new_value: Any, executor_func=None) -> None:
        """调整工具参数.
        
        Args:
            var_name: 变量名（如 "beta_60"）
            param_name: 参数名（如 "window"）
            new_value: 新值
            executor_func: 可选的执行函数，如果提供则自动执行预览
        """
        if not self.current_state:
            raise ValueError("未加载筛选逻辑")
        
        tools = self.current_state.logic.get('tools', [])
        found = False
        
        for tool in tools:
            if tool.get('var') == var_name:
                params = tool.setdefault('params', {})
                old_value = params.get(param_name)
                params[param_name] = new_value
                found = True
                
                logger.info(f"✏️  参数已更新: {var_name}.{param_name}")
                logger.info(f"   旧值: {old_value}")
                logger.info(f"   新值: {new_value}")
                break
        
        if not found:
            raise ValueError(f"未找到变量: {var_name}")
        
        # [OK] 自动执行预览（如果提供了执行函数）
        if executor_func and found:
            print(f"\n🔄 自动执行预览...")
            try:
                self.execute_and_preview(executor_func)
            except Exception as e:
                logger.warning(f"[WARN]  预览执行失败: {e}")
    

    
    def undo(self) -> bool:
        """撤销上一步操作."""
        if len(self.history) < 2:
            logger.warning("[WARN]  无法撤销（没有历史记录）")
            return False
        
        # 将当前状态压入 redo 栈
        if self.current_state:
            self.redo_stack.append(self.current_state)
        
        # 恢复到上一个状态
        self.current_state = self.history.pop()
        logger.info("↩️  已撤销")
        return True
    
    def redo(self) -> bool:
        """重做上一步撤销的操作."""
        if not self.redo_stack:
            logger.warning("[WARN]  无法重做（没有可重做的操作）")
            return False
        
        # 将当前状态压入历史
        if self.current_state:
            self.history.append(self.current_state)
        
        # 恢复 redo 栈顶状态
        self.current_state = self.redo_stack.pop()
        logger.info("↪️  已重做")
        return True
    
    def save_snapshot(self, name: str) -> Path:
        """保存当前状态为快照.
        
        Args:
            name: 快照名称
            
        Returns:
            保存的文件路径
        """
        if not self.current_state:
            raise ValueError("未加载筛选逻辑")
        
        snapshot_dir = Path("app/screening_scripts/snapshots")
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{name}_{self.current_state.timestamp.replace(':', '-')}.json"
        filepath = snapshot_dir / filename
        
        snapshot_data = {
            "name": name,
            "created_at": self.current_state.timestamp,
            "state": self.current_state.to_dict()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 快照已保存: {filepath}")
        return filepath
    
    def load_snapshot(self, filepath: str | Path) -> None:
        """加载快照.
        
        Args:
            filepath: 快照文件路径
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"快照文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            snapshot_data = json.load(f)
        
        state_data = snapshot_data['state']
        state = ScreeningState.from_dict(state_data)
        
        self.current_state = state
        self.history.clear()
        self.redo_stack.clear()
        
        logger.info(f"📂 已加载快照: {snapshot_data.get('name', '未命名')}")
    
    def export_logic(self, filepath: str | Path) -> None:
        """导出当前筛选逻辑为 JSON.
        
        Args:
            filepath: 输出文件路径
        """
        if not self.current_state:
            raise ValueError("未加载筛选逻辑")
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_state.logic, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📤 筛选逻辑已导出: {filepath}")
    
    def save_as_script(self, script_name: str | None = None) -> str | None:
        """将当前筛选逻辑保存为策略脚本.
        
        Args:
            script_name: 可选的脚本名称
            
        Returns:
            保存的文件路径，或 None
        """
        if not self.current_state:
            raise ValueError("未加载筛选逻辑")
        
        try:
            from src.screening.script_generator import ScriptGenerator
            
            logic = self.current_state.logic
            
            # 生成脚本
            generator = ScriptGenerator()
            script_content = generator.generate(logic)
            
            # 确定文件名
            if not script_name:
                strategy_name = logic.get('name', 'strategy')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                script_name = f"{strategy_name}_{timestamp}"
            
            # 确保 .py 后缀
            if not script_name.endswith('.py'):
                script_name += '.py'
            
            # 保存路径
            output_dir = Path("app/screening_scripts")
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / script_name
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            logger.info(f"💾 策略脚本已保存: {filepath}")
            return str(filepath)
            
        except ImportError:
            logger.error("[ERROR] ScriptGenerator 模块不存在")
            return None
        except Exception as e:
            logger.error(f"[ERROR] 脚本保存失败: {e}", exc_info=True)
            return None
    
    def _save_to_history(self) -> None:
        """保存当前状态到历史."""
        if self.current_state:
            self.history.append(copy.deepcopy(self.current_state))
            # 限制历史长度
            if len(self.history) > 20:
                self.history.pop(0)
            # 清空 redo 栈
            self.redo_stack.clear()
    
    def _show_execution_preview(self, candidates: list, elapsed: float, show_details: bool = True) -> None:
        """显示执行预览 - 复用主流程的详细展示.
        
        Args:
            candidates: 候选股票列表
            elapsed: 执行时间
            show_details: 是否显示详细信息（表格、行业分布等），False 则只显示摘要
        """
        from src.screening.result_display import ResultDisplayer
        
        print("\n" + "="*70)
        print(f"[DATA] 编辑模式预览 (耗时: {elapsed:.2f}s)")
        print("="*70)
        
        if not candidates:
            print(f"💡 提示: 当前条件下没有找到符合条件的股票")
            print(f"   建议: 放宽筛选条件或检查变量名是否正确")
            return

        # ✅ 如果不需要详细信息，只显示摘要
        if not show_details:
            print(f"[OK] 找到 {len(candidates)} 只符合条件的股票")
            # 显示前3只股票作为示例
            for i, stock in enumerate(candidates[:3], 1):
                ts_code = stock.get("ts_code", "N/A")
                name = stock.get('name', 'N/A')
                industry = stock.get("industry", "N/A")
                score = stock.get('confidence', 0)
                print(f"   {i}. {ts_code} {name} ({industry}) 评分: {score:.2f}")
            if len(candidates) > 3:
                print(f"   ... 还有 {len(candidates) - 3} 只股票")
            return

        # 构造完整的 result 结构以复用展示逻辑
        result = {
            "candidates": candidates,
            "screening_logic": self.current_state.logic if self.current_state else {},
            "success": True
        }
        
        # 使用 ResultDisplayer 进行详细展示（包含表格、行业分布等）
        displayer = ResultDisplayer()
        displayer.display(result)
    
    def show_help(self) -> None:
        """显示帮助信息."""
        help_text = """
╔═══════════════════════════════════════════════════════════╗
║         交互式筛选条件编辑器 - 命令帮助                    ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  📋 查看状态                                              ║
║    show                  - 显示当前筛选逻辑               ║
║                                                           ║
║  ✏️  修改表达式                                             ║
║    expr <新表达式>       - 设置筛选表达式                 ║
║    例: expr beta < 1.2 & outperform > 0.5                ║
║                                                           ║
║  ⚙️ 调整参数                                              ║
║    param <变量> <参数> <值> - 修改工具参数                ║
║    例: param beta_60 window 60                           ║
║                                                           ║
║  ❓ 其他                                                  ║
║    help                  - 显示此帮助                     ║
║    quit / exit           - 退出编辑器                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
        print(help_text)
