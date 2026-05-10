"""交互式筛选模式管理器 - 协调编辑器和主程序."""

from __future__ import annotations

from typing import Any
from infrastructure.logging.logger import get_logger
from src.agent.interactive.editor import InteractiveConditionEditor
from src.agent.interactive.command_parser import CommandParser

logger = get_logger(__name__)


class InteractiveModeManager:
    """交互式模式管理器 - 管理编辑会话的生命周期."""
    
    def __init__(self, orchestrator, state_manager):
        """初始化交互式模式管理器.
        
        Args:
            orchestrator: ScreenerOrchestrator 实例
            state_manager: SessionStateManager 实例
        """
        self.orchestrator = orchestrator
        self.state_manager = state_manager
        self.editor: InteractiveConditionEditor | None = None
        self.parser: CommandParser | None = None
    
    def start_session(self, initial_logic: dict | None = None) -> str | None:
        """启动交互编辑会话.
        
        Args:
            initial_logic: 初始筛选逻辑（可选，通常来自上一次查询结果）
        """
        print("\n" + "="*70)
        print("🎨 进入交互式筛选条件编辑模式")
        print("="*70)
        
        # 创建编辑器和解析器
        self.editor = InteractiveConditionEditor(initial_logic)
        self.parser = CommandParser(self.editor, self.orchestrator)
        
        # 显示初始状态或提示
        if initial_logic:
            print("[OK] 已加载筛选逻辑\n")
            self._display_full_logic(initial_logic)
        else:
            # 尝试从 session 恢复上次编辑的策略
            restored_logic = self._restore_from_session()
            if restored_logic:
                print("[OK] 从 session 恢复上次编辑的策略\n")
                self.editor.current_state.logic = restored_logic
                self._display_full_logic(restored_logic)
            else:
                print("💡 提示：当前没有正在编辑的策略")
                print("\n📝 你可以:")
                print("   • 输入 'load <文件路径>' 加载之前保存的策略")
                print("   • 输入 'quit' 退出，然后先用自然语言查询生成新策略")
                print("      例: 找出高波动且持续跑赢大盘的股票")
        
        print("="*70)
        
        # 进入命令循环
        return self._command_loop()
    
    def _display_full_logic(self, logic: dict) -> None:
        """显示完整的筛选逻辑."""
        print(f"📋 策略名称: {logic.get('name', '未命名')}")
        
        # [OK] 智能显示筛选说明
        rationale = logic.get('rationale', '')
        tools = logic.get('tools', [])  # 提前定义 tools
        
        if rationale and rationale.strip():
            print(f"📝 筛选说明: {rationale}")
        else:
            # 如果没有说明，根据表达式和工具生成简要说明
            expression = logic.get('expression', '')
            if expression and tools:
                tool_names = [t.get('tool', '') for t in tools if t.get('tool')]
                print(f"📝 筛选说明: 使用 {', '.join(tool_names)} 指标，条件: {expression[:50]}...")
            else:
                print(f"📝 筛选说明: 基于技术指标的量化筛选策略")
        
        print(f"\n🛠️  工具列表 ({len(tools)} 个):")
        for i, tool in enumerate(tools, 1):
            var = tool.get('var', 'N/A')
            tool_name = tool.get('tool', 'N/A')
            params = tool.get('params', {})
            print(f"   {i}. {var} = {tool_name}({params})")
        
        print(f"\n[SEARCH] 筛选表达式:")
        print(f"   {logic.get('expression', '无')}")
        print(f"\n[DATA] 得分公式:")
        print(f"   {logic.get('confidence_formula', '1.0')}")
        
        print()
    
    def _restore_from_session(self) -> dict | None:
        """从 session 恢复上次编辑的策略.
        
        Returns:
            策略字典，或 None（如果没有找到）
        """
        try:
            # 使用 state_manager 的 last_screening_logic
            if self.state_manager and self.state_manager.last_screening_logic:
                logger.info("[OK] 从 session 恢复上次筛选逻辑")
                return self.state_manager.last_screening_logic
            
            return None
            
        except Exception as e:
            logger.warning(f"[WARN] 从 session 恢复策略失败: {e}")
            return None
    
    def _save_to_session(self) -> None:
        """保存当前编辑状态到 session."""
        try:
            if self.editor and self.editor.current_state and self.state_manager:
                self.state_manager.last_screening_logic = self.editor.current_state.logic
                logger.debug("[OK] 已保存当前编辑状态到 session")
        except Exception as e:
            logger.warning(f"[WARN] 保存到 session 失败: {e}")
    
    def _command_loop(self) -> str | None:
        """命令输入循环.
        
        Returns:
            如果用户在编辑模式下输入了自然语言，返回该字符串；否则返回 None
        """
        new_query = None
        try:
            while True:
                try:
                    command = input("\n[CONFIG] 编辑> ").strip()
                    
                    if not command:
                        continue
                    
                    # 创建执行函数包装器
                    executor_func = self._create_executor_func()
                    
                    # 解析并执行命令
                    result = self.parser.parse_and_execute(command, executor_func)
                    
                    # [OK] 处理智能回退：如果返回的是元组 (False, query)
                    if isinstance(result, tuple):
                        should_continue, new_query = result
                        if not should_continue:
                            break
                    elif not result:
                        break
                
                except KeyboardInterrupt:
                    print("\n\n👋 用户中断")
                    break
                except Exception as e:
                    logger.error(f"[ERROR] 命令执行失败: {e}", exc_info=True)
                    print(f"错误: {e}")
        finally:
            # 退出前保存当前状态到 session
            self._save_to_session()
            
            # [OK] 如果带回了新查询，则不提示保存（因为马上要执行新任务）
            # [OK] 修复：如果是 quit/exit 命令退出，也不提示保存
            if not new_query and self.editor and self.editor.current_state:
                # 检查是否是 quit/exit 退出
                last_command = getattr(self.editor, '_last_command', '').lower()
                if last_command not in ['quit', 'exit', 'q']:
                    print("\n" + "="*70)
                    save_choice = input("💾 是否保存当前编辑的策略脚本？(y/n): ").strip().lower()
                    if save_choice in ['y', 'yes', '是']:
                        script_name = input("请输入策略名称 (直接回车使用默认名): ").strip()
                        if not script_name:
                            script_name = self.editor.current_state.logic.get('name', '未命名策略')
                        
                        # 调用编排器的保存功能
                        candidates = self._create_executor_func()(self.editor.current_state.logic)
                        from utils.screening.interactive_helpers import save_strategy_script
                        save_strategy_script(
                            self.editor.current_state.logic, 
                            candidates, 
                            script_name,
                            self.state_manager,
                            self.orchestrator.settings
                        )
        
        return new_query
    
    def _create_executor_func(self):
        """创建执行函数包装器.
        
        Returns:
            可调用对象，接收 screening_logic 返回 candidates
        """
        def execute_screening(logic: dict) -> list[dict[str, Any]]:
            """执行筛选的包装函数."""
            # 使用 orchestrator 执行筛选逻辑
            result = self.orchestrator.execute_query_with_logic(
                logic=logic,
                state_manager=self.state_manager
            )
            
            # [OK] 关键修复：检查执行是否成功
            if not result.get("success", False):
                error_msg = result.get("error", "未知错误")
                raise RuntimeError(f"筛选执行失败: {error_msg}")
            
            return result.get("candidates", [])
        
        return execute_screening
    
    def get_current_logic(self) -> dict | None:
        """获取当前编辑的筛选逻辑.
        
        Returns:
            当前筛选逻辑字典，或 None
        """
        if self.editor and self.editor.current_state:
            return self.editor.current_state.logic
        return None
    
    def save_current_as_script(self, script_name: str | None = None) -> str | None:
        """将当前逻辑保存为脚本.
        
        Args:
            script_name: 脚本名称（可选）
            
        Returns:
            保存的文件路径，或 None
        """
        if not self.editor or not self.editor.current_state:
            logger.warning("[WARN] 没有可保存的筛选逻辑")
            return None
        
        logic = self.editor.current_state.logic
        
        # TODO: 调用脚本生成器
        # 这里可以集成现有的 ScriptGenerator
        logger.info("[WARN] 脚本生成功能待实现")
        
        return None
