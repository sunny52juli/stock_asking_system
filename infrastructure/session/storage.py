"""会话存储 - 负责会话数据的持久化和加载."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from infrastructure.session.models import SessionMessage, QueryRecord

logger = get_logger(__name__)


class SessionStorage:
    """会话存储 - 管理单个会话的持久化."""
    
    def __init__(self, session_id: str, sessions_dir: str | Path | None = None):
        """初始化.
        
        Args:
            session_id: 会话ID
            sessions_dir: 会话目录（默认为 .stock_asking/sessions）
        """
        from pathlib import Path as StdPath
        
        if sessions_dir is None:
            project_root = StdPath(__file__).resolve().parent.parent.parent
            sessions_dir = project_root / ".stock_asking" / "sessions"
        
        self.session_id = session_id
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_file = self.sessions_dir / f"{session_id}.json"
        
        # 会话数据
        self.data = {
            "session_id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [],
            "queries": [],
            "metadata": {
                "total_queries": 0,
                "successful_scripts": 0,
            },
        }
        
        # 如果文件存在，加载历史数据
        if self.session_file.exists():
            self._load_from_file()
    
    def add_message(self, role: str, content: str, **metadata):
        """添加消息到会话."""
        message = SessionMessage(role=role, content=content, metadata=metadata)
        self.data["messages"].append(message.to_dict())
        self._touch()
    
    def add_query_record(self, record: QueryRecord):
        """添加查询记录."""
        self.data["queries"].append(record.to_dict())
        self.data["metadata"]["total_queries"] += 1
        
        if record.status == "success" and record.script_path:
            self.data["metadata"]["successful_scripts"] += 1
        
        self._touch()
    
    def update_query_status(
        self,
        query_id: int,
        status: str,
        script_path: str | None = None,
        candidates_count: int = 0,
        execution_time_ms: float = 0.0,
        error_message: str | None = None,
    ):
        """更新查询状态."""
        for query_data in self.data["queries"]:
            if query_data["query_id"] == query_id:
                query_data["status"] = status
                if script_path:
                    query_data["script_path"] = script_path
                if candidates_count > 0:
                    query_data["candidates_count"] = candidates_count
                if execution_time_ms > 0:
                    query_data["execution_time_ms"] = execution_time_ms
                if error_message:
                    query_data["error_message"] = error_message
                
                if status == "success" and script_path:
                    self.data["metadata"]["successful_scripts"] += 1
                
                self._touch()
                break
    
    def save(self):
        """保存会话到文件."""
        try:
            self.data["updated_at"] = time.time()
            self.session_file.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(f"💾 会话已保存：{self.session_file}")
        except Exception as e:
            logger.warning(f"保存会话失败：{e}")
    
    def _load_from_file(self):
        """从文件加载会话数据."""
        try:
            content = self.session_file.read_text(encoding="utf-8")
            loaded_data = json.loads(content)
            
            # 合并数据（保留新创建的字段）
            self.data.update(loaded_data)
            logger.info(f"📂 已加载历史会话：{self.session_id} ({len(self.data['queries'])} 条查询)")
        except Exception as e:
            logger.warning(f"加载会话失败：{e}")
    
    def _touch(self):
        """更新时间戳并自动保存."""
        self.data["updated_at"] = time.time()
        # 每 5 条消息或查询自动保存一次
        if len(self.data["messages"]) % 5 == 0 or len(self.data["queries"]) % 5 == 0:
            self.save()
    
    def get_query_history(self) -> list[QueryRecord]:
        """获取查询历史."""
        return [QueryRecord.from_dict(q) for q in self.data["queries"]]
    
    def get_recent_queries(self, limit: int = 10) -> list[QueryRecord]:
        """获取最近的查询."""
        queries = self.get_query_history()
        return queries[-limit:]
    
    def get_statistics(self) -> dict[str, Any]:
        """获取会话统计."""
        queries = self.get_query_history()
        total = len(queries)
        successful = sum(1 for q in queries if q.status == "success")
        failed = sum(1 for q in queries if q.status == "failed")
        
        return {
            "session_id": self.session_id,
            "total_queries": total,
            "successful_queries": successful,
            "failed_queries": failed,
            "success_rate": round(successful / total * 100, 2) if total > 0 else 0.0,
            "created_at": datetime.fromtimestamp(self.data["created_at"]).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.fromtimestamp(self.data["updated_at"]).strftime("%Y-%m-%d %H:%M:%S"),
        }
    
    @staticmethod
    def list_sessions(sessions_dir: str | Path | None = None) -> list[dict[str, Any]]:
        """列出所有已保存的会话."""
        from pathlib import Path as StdPath
        
        if sessions_dir is None:
            project_root = StdPath(__file__).resolve().parent.parent.parent
            sessions_dir = project_root / ".stock_asking" / "sessions"
        
        sessions_dir = Path(sessions_dir)
        if not sessions_dir.exists():
            return []
        
        sessions = []
        for session_file in sessions_dir.glob("*.json"):
            try:
                content = session_file.read_text(encoding="utf-8")
                data = json.loads(content)
                
                sessions.append({
                    "session_id": data["session_id"],
                    "created_at": datetime.fromtimestamp(data["created_at"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": datetime.fromtimestamp(data["updated_at"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "total_queries": data.get("metadata", {}).get("total_queries", 0),
                    "successful_scripts": data.get("metadata", {}).get("successful_scripts", 0),
                })
            except Exception as e:
                logger.warning(f"读取会话文件失败 {session_file}: {e}")
        
        # 按更新时间排序（最新的在前）
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions
    
    @classmethod
    def load(cls, session_id: str, sessions_dir: str | Path | None = None) -> SessionStorage | None:
        """加载指定会话."""
        from pathlib import Path as StdPath
        
        if sessions_dir is None:
            project_root = StdPath(__file__).resolve().parent.parent.parent
            sessions_dir = project_root / ".stock_asking" / "sessions"
        
        sessions_dir = Path(sessions_dir)
        session_file = sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            logger.warning(f"会话不存在：{session_id}")
            return None
        
        session = cls(session_id, sessions_dir)
        return session
