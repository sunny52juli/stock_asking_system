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
        
        # 📝 记录当前迭代的查询内容
        if iteration == 1:
            logger.info(f"🎯 初始查询: {query[:100]}{'...' if len(query) > 100 else ''}")
        else:
            logger.info(f"🔄 第 {iteration} 次迭代 - 基于质量反馈的优化查询")
        
        # === Phase 1: Execute ===
        logger.info("Phase 1: Execute")
        try:
            result = agent.invoke(
                {
                    "messages": [{"role": "user", "content": current_query}],
                    "files": initial_files,
                },
                config={
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": max_iterations * 2,  # LangGraph uses pairs of steps (plan + execute)
                },
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
        
        # 📊 详细记录质量评估结果
        candidate_count = quality_report.get('candidate_count', 0)
        quality_score = quality_report.get('quality_score', 0.0)
        logger.info(f"📊 质量评估结果:")
        logger.info(f"   候选数量: {candidate_count}")
        logger.info(f"   质量评分: {quality_score:.2f}")
        
        # 📋 尝试提取并显示本次迭代的筛选逻辑概要
        try:
            screening_logic = _extract_screening_logic(result)
            if screening_logic:
                expression = screening_logic.get('expression', 'N/A')
                tools = screening_logic.get('tools', [])
                tool_names = [t.get('tool', '') for t in tools if t.get('tool')]
                logger.info(f"📋 本次迭代使用的筛选策略:")
                logger.info(f"   表达式: {expression[:80]}{'...' if len(expression) > 80 else ''}")
                logger.info(f"   工具列表: {', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}")
        except Exception as e:
            logger.debug(f"无法提取筛选逻辑: {e}")
        
        if quality_report.get('issues'):
            logger.info(f"⚠️  发现的问题:")
            for issue in quality_report['issues']:
                logger.info(f"   - {issue}")
        
        if quality_report['suggestions']:
            logger.info("💡 优化建议:")
            for suggestion in quality_report['suggestions']:
                logger.info(f"   - {suggestion}")
        
        # === Phase 3: Decide ===
        if not quality_report.get('should_retry', False):
            logger.info("✅ 质量检查通过，返回结果")
            return result
        
        if iteration >= max_iterations:
            logger.warning(f"⚠️  达到最大迭代次数 ({max_iterations})，返回当前最佳结果")
            return result
        
        # === Retry with adjusted query ===
        logger.info(f"\n🔄 第 {iteration} 次迭代结束，准备第 {iteration + 1} 次重试...")
        logger.info(f"📝 重试原因: 质量评分 {quality_score:.2f} 低于阈值，需要优化")
        current_query = _build_retry_query(current_query, quality_report)
        logger.info(f"🔧 调整后的查询策略已生成，将在下一次迭代中应用")
    
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
    
    # 📋 详细记录调整内容
    logger.info(f"\n📋 本次迭代的调整策略:")
    retry_instruction = "\n\n请根据以下建议优化筛选条件:\n"
    for i, suggestion in enumerate(suggestions, 1):
        retry_instruction += f"{i}. {suggestion}\n"
        logger.info(f"   {i}. {suggestion}")
    
    return f"{original_query}{retry_instruction}"


def _extract_screening_logic(result: dict) -> dict | None:
    """从结果中提取筛选逻辑.
    
    Args:
        result: Agent执行结果
        
    Returns:
        筛选逻辑字典，或None
    """
    # 尝试从多个位置提取 screening_logic
    
    # 1. 直接从顶层获取
    if 'screening_logic' in result:
        return result['screening_logic']
    
    # 2. 从 messages 中的工具调用获取
    messages = result.get('messages', [])
    for msg in reversed(messages):
        # 检查 tool_calls
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call.get('name') == 'run_screening':
                    args = tool_call.get('args', {})
                    if 'screening_logic_json' in args:
                        import json
                        try:
                            return json.loads(args['screening_logic_json'])
                        except (json.JSONDecodeError, TypeError):
                            pass
        
        # 检查 content 中的 JSON
        if hasattr(msg, 'content') and msg.content:
            try:
                content_str = msg.content if isinstance(msg.content, str) else str(msg.content)
                if 'screening_logic' in content_str or 'expression' in content_str:
                    # 尝试提取 JSON
                    start = content_str.find('{')
                    if start >= 0:
                        json_str = content_str[start:]
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict):
                            if 'screening_logic' in parsed:
                                return parsed['screening_logic']
                            elif 'expression' in parsed and 'tools' in parsed:
                                return parsed
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
    
    return None
