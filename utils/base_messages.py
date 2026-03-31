#!/usr/bin/env python3
"""
通用消息基础模块 - 提供消息模板基类和通用消息

解决问题：
- factor_backtest_system 和 stock_asking_system 中存在重复的消息模板和 get_message 逻辑
- 两个系统共享相同的 API 相关、JSON 解析、系统错误等通用消息

使用方法：
    # 1. 继承 BaseMessageMixin，自动获得 get_message 方法和通用消息
    class MyPrompts(BaseMessageMixin):
        ERROR_MESSAGES = {
            **BaseMessageMixin.ERROR_MESSAGES,       # 继承通用消息
            'my_custom_error': "❌ 自定义错误: {error}",  # 添加自定义消息
        }

    # 2. 使用便捷函数
    from utils.base_messages import get_message
    msg = get_message(MyPrompts, 'ERROR', 'api_failed', status_code=500)
"""

import logging

logger = logging.getLogger(__name__)


# ==================== 通用消息常量 ====================
# 以下消息在多个子系统中通用，避免重复定义

COMMON_ERROR_MESSAGES = {
    'api_failed': "❌ API调用失败: {status_code}",
    'api_timeout': "❌ API调用超时，请重试",
    'api_exception': "❌ API调用异常: {error}",
    'json_parse_failed': "❌ JSON解析失败: {error}",
    'computation_failed': "❌ 计算失败: {error}",
    'unknown_error': "❌ 未知错误: {error}",
    'system_failed': "❌ 系统执行失败: {error}",
    'no_api_key_error': "❌ 未检测到API密钥，请设置环境变量 DEFAULT_API_KEY",
}

COMMON_WARNING_MESSAGES = {
    'no_api_key': "⚠️ 未找到DEFAULT_API_KEY，功能受限",
    'invalid_format': "⚠️ 返回格式不符合要求",
    'nan_values': "⚠️ 包含 {count} 个无效值",
}

COMMON_SUCCESS_MESSAGES = {
    'api_success': "✅ API响应成功",
}

COMMON_INFO_MESSAGES = {
    'calling_api': "📡 调用API: {url}",
}

COMMON_HINT_MESSAGES = {
    'set_api_key': "💡 提示: 设置DEFAULT_API_KEY环境变量以启用AI功能",
    'export_api_key': "请设置环境变量: export DEFAULT_API_KEY='your-api-key'",
}


# ==================== 消息基类 ====================

class BaseMessageMixin:
    """
    消息模板基类 Mixin

    为子系统 Prompt 类提供：
    1. 通用消息常量（继承即可获得）
    2. get_message 类方法（按 category + key 查找消息并格式化）

    子类可以通过字典合并（{**base, **custom}）来扩展或覆盖消息。
    """

    # 子类可通过 {**COMMON_xxx, ...} 合并来继承通用消息并添加自定义消息
    ERROR_MESSAGES: dict[str, str] = COMMON_ERROR_MESSAGES
    WARNING_MESSAGES: dict[str, str] = COMMON_WARNING_MESSAGES
    SUCCESS_MESSAGES: dict[str, str] = COMMON_SUCCESS_MESSAGES
    INFO_MESSAGES: dict[str, str] = COMMON_INFO_MESSAGES
    HINT_MESSAGES: dict[str, str] = COMMON_HINT_MESSAGES

    @classmethod
    def get_message(cls, category: str, key: str, **kwargs) -> str:
        """
        获取消息模板

        Args:
            category: 消息类别（ERROR, WARNING, SUCCESS, INFO, HINT）
            key: 消息键
            **kwargs: 格式化参数

        Returns:
            格式化后的消息文本

        Examples:
            >>> cls.get_message('ERROR', 'api_failed', status_code=500)
            '❌ API调用失败: 500'

            >>> cls.get_message('SUCCESS', 'api_success')
            '✅ API响应成功'
        """
        messages = {
            'ERROR': cls.ERROR_MESSAGES,
            'WARNING': cls.WARNING_MESSAGES,
            'SUCCESS': cls.SUCCESS_MESSAGES,
            'INFO': cls.INFO_MESSAGES,
            'HINT': cls.HINT_MESSAGES,
        }

        message_dict = messages.get(category, {})
        if not message_dict:
            logger.warning(f"未知的消息类别: '{category}'，可选值: {list(messages.keys())}")
            return ""

        template = message_dict.get(key, "")
        if not template:
            logger.warning(f"未找到消息键: category='{category}', key='{key}'")
            return ""

        if kwargs:
            return template.format(**kwargs)
        return template


# ==================== 便捷函数 ====================

def get_message(prompt_cls, category: str, key: str, **kwargs) -> str:
    """
    从指定的 Prompt 类中获取消息模板（便捷函数）

    Args:
        prompt_cls: 带有 get_message 方法的 Prompt 类
        category: 消息类别
        key: 消息键
        **kwargs: 格式化参数

    Returns:
        格式化后的消息文本
    """
    return prompt_cls.get_message(category, key, **kwargs)
