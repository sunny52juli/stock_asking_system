"""Agent执行三阶段循环 - Plan → Execute → Reflect.

"""

from __future__ import annotations

from typing import Any

from infrastructure.logging.logger import get_logger
from src.agent.quality.quality_evaluator import ScreeningQualityEvaluator
from infrastructure.config.settings import Settings

logger = get_logger(__name__)


def execute_query_with_reflection(
    agent: Any,
    query: str,
    initial_files: dict,
    quality_evaluator: ScreeningQualityEvaluator,
    settings: Settings,
    thread_id: str,
) -> dict[str, Any]:
    """执行带反思的查询循环.
    
    Args:
        agent: DeepAgent实例
        query: 用户查询
        initial_files: 初始文件上下文
        quality_evaluator: 质量评估器
        settings: 全局配置
        thread_id: 线程ID
        
    Returns:
        最终结果
    """
    max_iterations = settings.harness.max_iterations
    current_query = query
    
    for iteration in range(1, max_iterations + 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Iteration {iteration}/{max_iterations}")
        logger.info(f"{'='*60}")
        
        # === Phase 1: Execute ===
        logger.info("Phase 1: Execute")
        try:
            result = agent.invoke(
                {
                    "messages": [{"role": "user", "content": current_query}],
                    "files": initial_files,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "error": str(e),
                "status": "failed",
                "iteration": iteration,
            }
        
        # === Phase 2: Reflect ===
        logger.info("Phase 2: Reflect")
        quality_report = quality_evaluator.evaluate(query, result)
        
        if quality_report.get('reflection_rules'):
            logger.info("已加载 reflection.md 规则，Agent 将自行评估质量")
        
        if quality_report['suggestions']:
            logger.info("Suggestions:")
            for suggestion in quality_report['suggestions']:
                logger.info(f"  - {suggestion}")
        
        # === Phase 3: Decide ===
        # 注意：should_retry 现在由 Agent 根据 reflection.md 决定
        if not quality_report.get('should_retry', False):
            logger.info("✅ Quality check passed")
            return result
        
        if iteration >= max_iterations:
            logger.warning(f"⚠️ Reached max iterations ({max_iterations})")
            return result
        
        # === Retry with adjusted query ===
        logger.info("🔄 Retrying with adjusted query...")
        current_query = _build_retry_query(current_query, quality_report)
    
    return result


def _build_retry_query(original_query: str, quality_report: dict[str, Any]) -> str:
    """构建重试查询.
    
    Args:
        original_query: 原始查询
        quality_report: 质量报告
        
    Returns:
        调整后的查询
    """
    suggestions = quality_report.get('suggestions', [])
    if not suggestions:
        return original_query
    
    retry_instruction = "\n\n请根据以下建议优化筛选条件:\n"
    for i, suggestion in enumerate(suggestions, 1):
        retry_instruction += f"{i}. {suggestion}\n"
    
    return f"{original_query}{retry_instruction}"
