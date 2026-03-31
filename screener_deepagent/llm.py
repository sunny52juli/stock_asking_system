"""
LLM 构建模块

从 config.get_api_config() (DEFAULT_API_URL / DEFAULT_MODEL / DEFAULT_API_KEY) 构建
LangChain ChatModel, 供 agent 使用。职责单一: 仅负责 LLM 实例的创建。
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

def build_llm_from_api_config(api_config: dict[str, Any]) -> Any:
    """使用与 stock_asking_system 相同的 API 配置构建 LangChain ChatModel.

    URL 约定: OpenAI SDK 与 LangChain ChatOpenAI 均期望 base_url 为「根地址」,
    库内会再拼 /chat/completions. 若 DEFAULT_API_URL 误填为完整 endpoint(含 /chat/completions),
    此处会去掉该后缀再传入, 避免 404. 详见 screener_deepagent/API_URL_ANALYSIS.md.

    Args:
        api_config: 来自 config.get_api_config() 的字典 (api_key, base_url, model 等).

    Returns:
        ChatOpenAI 实例.

    Raises:
        ImportError: 未安装 langchain-openai.
    """
    api_key = api_config.get("api_key") or ""
    base_url = (api_config.get("base_url") or "").rstrip("/") or None
    if base_url and base_url.rstrip("/").endswith("/chat/completions"):
        base_url = base_url.rstrip("/").rsplit("/chat/completions", 1)[0] or None
    model = api_config.get("model") or "gpt-4o-mini"
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
