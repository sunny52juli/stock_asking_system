"""会话管理器 - 负责会话的创建、加载和管理."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from infrastructure.session.storage import SessionStorage
from infrastructure.session.exporter import SessionExporter

logger = get_logger(__name__)


class SessionManager:
    """会话管理器（单例模式）."""
    
    _instance: SessionManager | None = None
    
    def __init__(self, sessions_dir: str | Path | None = None):
        """初始化.
        
        Args:
            sessions_dir: 会话目录
        """
        from pathlib import Path as StdPath
        
        if sessions_dir is None:
            project_root = StdPath(__file__).resolve().parent.parent.parent
            sessions_dir = project_root / ".stock_asking" / "sessions"
        
        self.sessions_dir = Path(sessions_dir)
        self.current_session: SessionStorage | None = None
    
    @classmethod
    def get_instance(cls, sessions_dir: str | Path | None = None) -> SessionManager:
        """获取单例实例."""
        if cls._instance is None:
            cls._instance = cls(sessions_dir)
        return cls._instance
    
    def create_session(self, session_id: str | None = None) -> SessionStorage:
        """创建新会话."""
        if session_id is None:
            # 使用格式化的系统时间作为会话ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"session_{timestamp}"
        
        self.current_session = SessionStorage(session_id, self.sessions_dir)
        logger.info(f"🆕 创建新会话：{session_id}")
        return self.current_session
    
    def get_current_session(self) -> SessionStorage | None:
        """获取当前会话."""
        return self.current_session
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话."""
        return SessionStorage.list_sessions(self.sessions_dir)
    
    def load_session(self, session_id: str) -> SessionStorage | None:
        """加载会话."""
        session = SessionStorage.load(session_id, self.sessions_dir)
        if session:
            self.current_session = session
            logger.info(f"📂 加载会话：{session_id}")
        return session
    
    def print_session_list(self):
        """打印会话列表."""
        sessions = self.list_sessions()
        
        if not sessions:
            logger.info("📋 没有已保存的会话")
            return
        
        logger.info("=" * 80)
        logger.info("📋 已保存的会话列表")
        logger.info("=" * 80)
        
        for i, session in enumerate(sessions, 1):
            logger.info(f"{i}. {session['session_id']}")
            logger.info(f"   创建时间：{session['created_at']}")
            logger.info(f"   更新时间：{session['updated_at']}")
            logger.info(f"   查询数：{session['total_queries']} | 成功脚本：{session['successful_scripts']}")
            logger.info("")
        
        logger.info("=" * 80)
    
    def export_to_html(self, session_id: str, output_path: str | Path | None = None) -> Path:
        """将会话导出为 HTML 报告.
        
        Args:
            session_id: 会话ID
            output_path: 输出路径（可选，默认为 .stock_asking/reports/）
            
        Returns:
            HTML 文件路径
        """
        session = SessionStorage.load(session_id, self.sessions_dir)
        if not session:
            raise ValueError(f"会话不存在：{session_id}")
        
        return SessionExporter.export_to_html(session, output_path)
