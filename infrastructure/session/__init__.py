"""Session 模块 - 会话管理系统（重构版）."""

from infrastructure.session.models import SessionMessage, QueryRecord
from infrastructure.session.storage import SessionStorage
from infrastructure.session.manager import SessionManager

# 向后兼容：Session 别名指向 SessionStorage
Session = SessionStorage


def get_session_manager(sessions_dir: str | None = None) -> SessionManager:
    """获取会话管理器单例."""
    return SessionManager.get_instance(sessions_dir)


def reset_session_manager():
    """重置会话管理器单例（用于测试）."""
    SessionManager._instance = None


__all__ = [
    "SessionMessage",
    "QueryRecord",
    "SessionStorage",
    "Session",  # 向后兼容
    "SessionManager",
    "get_session_manager",
    "reset_session_manager",
]
