"""自然语言策略修改器 - 允许用户在编辑模式下通过自然语言调整策略.

✅ 重构方案：复用完整的 Agent 流程（Harness + Hooks + 质量评估）
而不是简单的 LLM 调用，确保生成的逻辑符合系统规范。
"""

from __future__ import annotations

import json
from typing import Any
from infrastructure.logging.logger import get_logger
from src.agent.core.orchestrator import ScreenerOrchestrator

logger = get_logger(__name__)


class NaturalLanguageModifier:
    """自然语言修改器 - 将用户的自然语言指令转换为对现有 screening_logic 的修改.
    
    ✅ 重构后：直接调用 orchestrator.execute_query()，利用完整的 Agent 流程
    """

    def __init__(self, orchestrator: ScreenerOrchestrator):
        self.orchestrator = orchestrator

    def modify_logic(self, current_logic: dict, user_instruction: str) -> dict | None:
        """根据用户指令修改当前逻辑.
        
        ✅ 新方案：构造增强查询，调用完整 Agent 流程
        
        Args:
            current_logic: 当前的筛选逻辑字典
            user_instruction: 用户的自然语言指令（如"增加均线发散条件"）
            
        Returns:
            修改后的逻辑字典，或 None（如果修改失败）
        """
        try:
            logger.info(f"🔄 正在根据指令修改策略: '{user_instruction}'")
            logger.info(f"   📋 当前策略: {current_logic.get('name', '未命名')}")
            
            # ✅ 构造增强查询：将当前逻辑作为上下文
            enhanced_query = self._build_enhanced_query(current_logic, user_instruction)
            
            logger.info(f"   🔍 调用完整 Agent 流程...")
            
            # ✅ 调用完整的 Agent 流程（Harness + Hooks + 质量评估）
            import time
            query_id = int(time.time() * 1000)  # 使用时间戳作为唯一 ID
            
            result = self.orchestrator.execute_query(
                query=enhanced_query,
                query_id=query_id
            )
            
            if not result:
                logger.warning("[WARN] Agent 执行返回空结果")
                return None
            
            # ✅ 从结果中提取筛选逻辑
            modified_logic = self._extract_logic_from_result(result)
            
            if modified_logic:
                logger.info("[OK] 策略逻辑已成功根据自然语言指令更新")
                logger.info(f"   📊 新表达式: {modified_logic.get('expression', 'N/A')[:80]}...")
                return modified_logic
            else:
                logger.warning("[WARN] 无法从 Agent 结果中提取筛选逻辑")
                return None

        except Exception as e:
            logger.error(f"[ERROR] 自然语言修改失败: {e}", exc_info=True)
            return None
    
    def _build_enhanced_query(self, current_logic: dict, user_instruction: str) -> str:
        """构造增强查询，将当前逻辑作为上下文.
        
        Args:
            current_logic: 当前筛选逻辑
            user_instruction: 用户指令
            
        Returns:
            增强后的查询字符串
        """
        # 提取当前策略的关键信息
        current_expr = current_logic.get('expression', '')
        current_tools = current_logic.get('tools', [])
        strategy_name = current_logic.get('name', '当前策略')
        
        # 构造工具列表摘要
        tool_summary = ", ".join([t.get('var', t.get('tool', '')) for t in current_tools[:5]])
        if len(current_tools) > 5:
            tool_summary += f" 等{len(current_tools)}个工具"
        
        # ✅ 构造结构化查询
        enhanced_query = f"""【策略优化任务】

当前策略：{strategy_name}
当前表达式：{current_expr}
当前工具：{tool_summary}

用户需求：{user_instruction}

请基于当前策略进行增量修改：
1. 保留原有的核心逻辑
2. 根据用户需求添加/调整条件
3. 确保工具名称正确（参考可用工具列表）
4. 保持变量名一致性

注意：这是一个策略优化任务，不是从零开始生成。"""
        
        return enhanced_query
    
    def _extract_logic_from_result(self, result: dict) -> dict | None:
        """从 Agent 结果中提取筛选逻辑.
        
        Args:
            result: Agent 执行结果
            
        Returns:
            筛选逻辑字典，或 None
        """
        try:
            # 尝试从 messages 中提取
            messages = result.get("messages", [])
            if messages:
                for message in reversed(messages):
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        for tool_call in message.tool_calls:
                            if tool_call.get("name") in ["run_screening", "cached_run_screening"]:
                                args = tool_call.get("args", {})
                                if "screening_logic_json" in args:
                                    logic = json.loads(args["screening_logic_json"])
                                    return logic
            
            # 尝试从顶层获取
            if "screening_logic" in result:
                return result["screening_logic"]
            
            return None
            
        except Exception as e:
            logger.error(f"[ERROR] 提取筛选逻辑失败: {e}")
            return None
