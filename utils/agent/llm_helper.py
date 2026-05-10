"""LLM 构建工具 - 从配置创建 LangChain ChatModel."""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI


def build_llm_from_api_config(api_config: dict[str, Any]) -> Any:
    """使用 API 配置构建 LangChain ChatModel.

    URL 约定: OpenAI SDK 与 LangChain ChatOpenAI 均期望 base_url 为「根地址」,
    库内会再拼 /chat/completions. 若 DEFAULT_API_URL 误填为完整 endpoint(含 /chat/completions),
    此处会去掉该后缀再传入, 避免 404.

    Args:
        api_config: API 配置字典 (api_key, base_url, model 等).

    Returns:
        ChatOpenAI 实例.

    Raises:
        ImportError: 未安装 langchain-openai.
    """
    # 支持 Pydantic 模型和 dict
    if hasattr(api_config, 'model_dump'):
        # Pydantic v2
        config_dict = api_config.model_dump()
    elif hasattr(api_config, 'dict'):
        # Pydantic v1
        config_dict = api_config.dict()
    else:
        # 已经是 dict
        config_dict = api_config
    
    # ✅ 兼容 LLMConfig 的字段名差异：api_url -> base_url
    if 'api_url' in config_dict and 'base_url' not in config_dict:
        config_dict['base_url'] = config_dict.pop('api_url')
    
    # 验证必需的配置项
    api_key = config_dict.get("api_key")
    if not api_key:
        raise ValueError("API密钥(api_key)未配置，请在配置文件中设置有效的API密钥")
    
    base_url = config_dict.get("base_url")
    if not base_url:
        raise ValueError("API基础URL(base_url)未配置，请在配置文件中设置正确的API端点地址")
    
    model = config_dict.get("model")
    if not model:
        raise ValueError("模型名称(model)未配置，请在配置文件中指定要使用的模型")
    
    # 处理base_url格式（去除末尾斜杠和/chat/completions后缀）
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url.rsplit("/chat/completions", 1)[0]
    
    temperature = config_dict.get("temperature", 0.7)
    max_tokens = config_dict.get("max_tokens", 4096)
    
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=120,  # 请求超时（秒）- deepagents 需要更长时间
        max_retries=2,  # 最大重试次数
    )
