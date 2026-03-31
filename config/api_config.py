"""
API 配置模块 - 管理所有 API 相关的配置
"""

import os
from typing import Any

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class APIConfig:
    """API 配置类 - 包含所有 API 相关的配置"""

    # API 基础配置
    DEFAULT_API_URL = os.getenv("DEFAULT_API_URL")
    DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

    # 模型参数配置
    MAX_ITERATIONS = 5
    MAX_TOKENS = 4096
    TEMPERATURE = 0.7

    @classmethod
    def get_api_config(cls) -> dict[str, Any]:
        """
        获取 API 配置字典

        Returns:
            dict: 包含所有 API 配置的字典
        """
        # 确保 api_url 是完整的 chat completions 端点
        raw_base = (cls.DEFAULT_API_URL or "").strip().rstrip("/")
        # 供 SDK/LangChain 用的 base: 若用户误填了完整 endpoint, 去掉 /chat/completions 避免重复拼接
        if raw_base.endswith("/chat/completions"):
            base_url = raw_base.rsplit("/chat/completions", 1)[0] or ""
        else:
            base_url = raw_base
        if not raw_base.endswith("/chat/completions"):
            api_url = f"{raw_base}/chat/completions" if raw_base else ""
        else:
            api_url = raw_base

        return {
            "api_key": cls.DEFAULT_API_KEY,
            "model": cls.DEFAULT_MODEL,
            "api_url": api_url,
            "base_url": base_url if base_url else cls.DEFAULT_API_URL,  # SDK/LangChain 用，不含 /chat/completions
            "max_iterations": cls.MAX_ITERATIONS,
            "max_tokens": cls.MAX_TOKENS,
            "temperature": cls.TEMPERATURE,
        }
