"""交互式编辑器命令解析器 - 处理用户输入的命令."""

from __future__ import annotations

import json
from typing import Callable
from infrastructure.logging.logger import get_logger
from src.agent.interactive.editor import InteractiveConditionEditor
from src.agent.interactive.nl_modifier import NaturalLanguageModifier

logger = get_logger(__name__)


class CommandParser:
    """命令解析器 - 将用户输入转换为编辑器操作."""
    
    def __init__(self, editor: InteractiveConditionEditor, orchestrator=None):
        """初始化命令解析器.
        
        Args:
            editor: InteractiveConditionEditor 实例
            orchestrator: ScreenerOrchestrator 实例（用于自然语言修改）
        """
        self.editor = editor
        self.nl_modifier = NaturalLanguageModifier(orchestrator) if orchestrator else None
    
    def parse_and_execute(self, command: str, executor_func: Callable | None = None) -> bool:
        """解析并执行命令.
        
        Args:
            command: 用户输入的命令字符串
            executor_func: 执行函数（用于 preview 命令）
            
        Returns:
            True 如果命令执行成功，False 如果需要退出
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        try:
            if cmd == 'show':
                if not self.editor.current_state:
                    print("[ERROR] 未加载筛选逻辑")
                    print("💡 提示:")
                    print("   1. 先通过自然语言查询生成策略")
                    print("   2. 或使用 'load <文件路径>' 加载快照")
                    print("   3. 或输入 'edit' 重新启动编辑会话并传入初始逻辑")
                else:
                    self.editor.show_current_state()
                return True
            
            elif cmd == 'expr':
                return self._handle_expr(args, executor_func)
            
            elif cmd == 'param':
                return self._handle_param(args, executor_func)
            
            elif cmd == 'undo':
                self.editor.undo()
                return True
            
            elif cmd == 'redo':
                self.editor.redo()
                return True
            
            elif cmd == 'save':
                return self._handle_save(args)
            
            elif cmd == 'load':
                return self._handle_load(args)
            
            elif cmd in ['quit', 'exit', 'q']:
                print("\n👋 退出编辑模式")
                return False
            
            elif cmd == 'help':
                self.editor.show_help()
                return True
            
            else:
                # [OK] 智能识别：判断是表达式、自然语言修改还是新查询
                # 1. 如果包含逻辑运算符，视为直接修改表达式
                if any(op in command for op in ['&', '|', '>', '<', '=']) and '(' in command:
                    print(f"\n[INFO] 检测到筛选表达式，直接更新并预览...")
                    return self._handle_expr(command, executor_func)
                
                # 2. 如果是中文自然语言，尝试在编辑模式下进行 AI 辅助修改
                elif any('\u4e00' <= c <= '\u9fff' for c in command):
                    if self.nl_modifier and self.editor.current_state:
                        print(f"\n[INFO] 检测到自然语言修改指令，正在调用 AI 调整策略...")
                        new_logic = self.nl_modifier.modify_logic(
                            self.editor.current_state.logic, 
                            command
                        )
                        if new_logic:
                            # 更新编辑器状态
                            self.editor.current_state.logic = new_logic
                            # ✅ 自动执行预览（使用详细显示，与首次查询一致）
                            if executor_func:
                                try:
                                    candidates = executor_func(new_logic)
                                    # 传递 show_details=True，显示完整表格和行业分布
                                    self.editor._show_execution_preview(candidates, 0, show_details=True)
                                except Exception as e:
                                    print(f"[ERROR] 预览执行失败: {e}")
                            return True
                        else:
                            print("[WARN] AI 未能理解修改指令，请尝试更明确的描述或使用 'expr' 命令")
                            return True
                    else:
                        print("[WARN] 自然语言修改功能未初始化或未加载策略")
                        return True
                
                # 3. 其他情况（如英文短命令）视为退出编辑模式的新查询
                else:
                    print(f"\n[INFO] 检测到新查询意图，退出编辑模式并执行...")
                    return False, command
        
        except Exception as e:
            logger.error(f"[ERROR] 命令执行失败: {e}", exc_info=True)
            print(f"错误: {e}")
            return True
    
    def _handle_expr(self, args: str, executor_func: Callable | None = None) -> bool:
        """处理表达式修改命令."""
        if not args:
            print("[ERROR] 用法: expr <新表达式>")
            print("   例: expr beta < 1.2 & outperform > 0.5")
            return True
        
        if not self.editor.current_state:
            print("[ERROR] 错误: 未加载筛选逻辑")
            print("提示: 请先通过自然语言查询生成策略，或使用 'load' 加载快照")
            return True
        
        try:
            # [OK] 传入 executor_func 以自动执行预览
            self.editor.adjust_expression(args, executor_func=executor_func)
            # 注意：adjust_expression 内部已调用 execute_preview，不再需要手动提示
        except Exception as e:
            print(f"[ERROR] 表达式更新失败: {e}")
        
        return True
    
    def _handle_param(self, args: str, executor_func: Callable | None = None) -> bool:
        """处理参数调整命令."""
        param_parts = args.split()
        if len(param_parts) != 3:
            print("[ERROR] 用法: param <变量名> <参数名> <新值>")
            print("   例: param beta_60 window 60")
            return True
        
        if not self.editor.current_state:
            print("[ERROR] 错误: 未加载筛选逻辑")
            return True
        
        var_name, param_name, value_str = param_parts
        
        # 尝试转换为数值
        try:
            if '.' in value_str:
                value = float(value_str)
            else:
                value = int(value_str)
        except ValueError:
            value = value_str  # 保持字符串
        
        try:
            # [OK] 传入 executor_func 以自动执行预览
            self.editor.adjust_parameter(var_name, param_name, value, executor_func=executor_func)
            # 注意：adjust_parameter 内部已调用 execute_preview，不再需要手动提示
        except Exception as e:
            print(f"[ERROR] 参数更新失败: {e}")
        
        return True
    

    
    def _handle_save(self, args: str) -> bool:
        """处理保存快照命令."""
        if not args:
            print("[ERROR] 用法: save <快照名称>")
            return True
        
        self.editor.save_snapshot(args)
        return True
    
    def _handle_load(self, args: str) -> bool:
        """处理加载快照命令."""
        if not args:
            print("[ERROR] 用法: load <文件路径>")
            return True
        
        try:
            self.editor.load_snapshot(args)
            print("[OK] 快照已加载")
            return True
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return True
    
    def _handle_preview(self, executor_func: Callable | None) -> bool:
        """处理预览命令（已废弃，现在自动执行）。"""
        print("[INFO] 'preview' 命令已移除，修改表达式或参数后会自动预览。")
        return True
