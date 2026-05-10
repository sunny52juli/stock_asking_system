"""候选股票提取器 - 从 Agent 结果中提取 candidates."""

from __future__ import annotations

import json
from typing import Any

from infrastructure.logging.logger import get_logger
from src.agent.tools import bridge

logger = get_logger(__name__)


class CandidateExtractor:
    """候选股票提取器 - 多策略提取 candidates."""
    
    @staticmethod
    def extract(result: dict) -> dict:
        """从 Agent 消息历史中提取 candidates.
        
        优先级：
        1. result 中已有的 candidates
        2. Bridge 工具保存的全局最后一次筛选结果
        3. 从 Agent 消息中解析
        
        Args:
            result: Agent 返回的结果
            
        Returns:
            添加了 candidates 字段的结果
        """
        # 如果 result 中已有 candidates，直接返回
        if "candidates" in result and result["candidates"]:
            return result
        
        # 方法1：优先使用 Bridge 工具保存的全局最后一次筛选结果
        candidates = CandidateExtractor._extract_from_bridge()
        if candidates is not None:
            result["candidates"] = candidates
            return result
        
        # 方法2：降级方案 - 从 Agent 消息中解析
        candidates = CandidateExtractor._extract_from_messages(result)
        if candidates is not None:
            result["candidates"] = candidates
            return result
        
        logger.warning("[WARN] 未能从任何来源获取 candidates")
        return result
    
    @staticmethod
    def _extract_from_bridge() -> list[dict] | None:
        """从 Bridge 工具获取 candidates.
        
        Returns:
            candidates 列表或 None
        """
        try:
            last_result = bridge.get_last_screening_result()
            if last_result and "candidates" in last_result:
                candidates = last_result["candidates"]
                logger.info(f"[OK] 从 Bridge 工具获取到 {len(candidates)} 只候选股票")
                return candidates
        except Exception as e:
            logger.debug(f"从 Bridge 获取 candidates 失败: {e}")
        
        return None
    
    @staticmethod
    def _extract_from_messages(result: dict) -> list[dict] | None:
        """从 Agent 消息中解析 candidates.
        
        Args:
            result: Agent 返回的结果
            
        Returns:
            candidates 列表或 None
        """
        messages = result.get("messages", [])
        for message in messages:
            if hasattr(message, "content") and message.content:
                try:
                    content_str = message.content if isinstance(message.content, str) else str(message.content)
                    
                    # 查找 JSON 格式的 run_screening 返回结果
                    if '"candidates"' in content_str and '"status": "success"' in content_str:
                        start = content_str.find('{')
                        if start >= 0:
                            json_str = content_str[start:]
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict) and "candidates" in parsed:
                                candidates = parsed["candidates"]
                                logger.info(f"[OK] 从消息中提取到 {len(candidates)} 只候选股票")
                                return candidates
                except (json.JSONDecodeError, TypeError):
                    pass
        
        return None
