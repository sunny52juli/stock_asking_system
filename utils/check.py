from utils.logger import get_logger
from config.screener_deepagent_config import ScreenerDeepAgentConfig

logger = get_logger(__name__)



def _extract_screening_logic_from_result(result: dict) -> str | None:
    """从 Agent 结果中提取 run_screening 工具调用的 screening_logic_json 参数."""
    try:
        messages = result.get("messages", [])
        for message in reversed(messages):
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.get("name") == "run_screening":
                        args = tool_call.get("args", {})
                        if "screening_logic_json" in args:
                            return args["screening_logic_json"]
        return None
    except Exception as e:
        logger.debug("提取 screening_logic 失败：%s", e)
        return None


def _is_screening_successful(result: dict) -> bool:
    """检查 Agent 结果是否表示筛选成功."""
    try:
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

        success_keywords = ["成功筛选", "成功匹配", "筛选成功", "找到", "候选股票", "筛选完成"]
        return any(keyword in content for keyword in success_keywords)
    except Exception as e:
        logger.debug("检查筛选成功状态失败：%s", e)
        return False


def _check_api_key() -> bool:
    """检查 API 密钥是否配置."""
    api_key = ScreenerDeepAgentConfig.get_api_config().get("api_key")
    if not api_key:
        logger.error(ScreenerDeepAgentConfig.get_message("ERROR", "no_api_key"))
        logger.info("设置方法：复制 .env.example 为 .env, 在 .env 中配置 DEFAULT_API_KEY")
        return False
    logger.info("API 密钥已配置")
    return True
