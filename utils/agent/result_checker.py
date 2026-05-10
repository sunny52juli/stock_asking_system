"""Agent 结果检查工具 - 验证筛选执行状态."""

from infrastructure.logging.logger import get_logger
from infrastructure.config.settings import get_settings

logger = get_logger(__name__)


def _extract_screening_logic_from_result(result: dict) -> str | None:
    """从 Agent 结果中提取 run_screening 工具调用的 screening_logic_json 参数."""
    try:
        messages = result.get("messages", [])
        for message in reversed(messages):
            # ✅ 兼容两种格式：对象属性和字典
            tool_calls = None
            if hasattr(message, "tool_calls"):
                tool_calls = message.tool_calls
            elif isinstance(message, dict):
                tool_calls = message.get("tool_calls", [])
            
            if not tool_calls:
                continue
            
            for tool_call in tool_calls:
                # ✅ 支持多种工具名称
                tool_name = tool_call.get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
                if tool_name in ["run_screening", "cached_run_screening"]:
                    args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                    if "screening_logic_json" in args:
                        return args["screening_logic_json"]
        return None
    except Exception as e:
        logger.debug("提取 screening_logic 失败: %s", e)
        return None


def _is_screening_successful(result: dict) -> bool:
    """检查 Agent 结果是否表示筛选成功."""
    try:
        # 优先检查是否有 candidates 数据
        candidates = result.get("candidates", [])
        if candidates and len(candidates) > 0:
            logger.debug(f"✅ 检测到 {len(candidates)} 只候选股票，筛选成功")
            return True
        
        # 其次检查消息内容
        messages = result.get("messages", [])
        if not messages:
            return False

        final_message = messages[-1]
        content = ""
        if hasattr(final_message, "content"):
            content = final_message.content or ""
        elif isinstance(final_message, dict):
            content = final_message.get("content", "") or ""
        elif isinstance(final_message, str):
            content = final_message

        success_keywords = ["成功筛选", "成功匹配", "筛选成功", "找到", "候选股票", "筛选完成", "共筛选出"]
        has_keyword = any(keyword in content for keyword in success_keywords)
        
        if has_keyword:
            logger.debug("✅ 检测到成功关键词")
        
        return has_keyword

    except Exception as e:
        logger.debug("检查筛选成功状态失败：%s", e)
        return False


def _check_api_key() -> bool:
    """检查 API 密钥是否配置."""
    settings = get_settings()
    api_key = settings.llm.api_key
    if not api_key:
        logger.error("未检测到 API 密钥，请设置环境变量 DEFAULT_API_KEY")
        logger.info("设置方法：复制 .env.example 为 .env, 在 .env 中配置 DEFAULT_API_KEY")
        return False
    logger.info("API 密钥已配置")
    return True
