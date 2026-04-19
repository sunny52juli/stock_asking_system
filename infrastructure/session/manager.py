"""会话管理系统 - 持久化查询历史和脚本路径."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger

from datetime import datetime
from pathlib import Path as StdPath
logger = get_logger(__name__)


@dataclass
class SessionMessage:
    """会话消息."""
    
    role: str  # user/assistant
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMessage:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QueryRecord:
    """查询记录."""
    
    query_id: int
    query_text: str
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending/success/failed/interrupted
    script_path: str | None = None
    candidates_count: int = 0
    execution_time_ms: float = 0.0
    error_message: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "timestamp": self.timestamp,
            "status": self.status,
            "script_path": self.script_path,
            "candidates_count": self.candidates_count,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "error_message": self.error_message,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryRecord:
        return cls(
            query_id=data["query_id"],
            query_text=data["query_text"],
            timestamp=data.get("timestamp", time.time()),
            status=data.get("status", "pending"),
            script_path=data.get("script_path"),
            candidates_count=data.get("candidates_count", 0),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            error_message=data.get("error_message"),
        )


class Session:
    """会话管理类.
    
    功能：
    - 保存查询历史到 JSON 文件
    - 支持加载历史会话
    - 列出所有已保存的会话
    - 自动添加消息和时间戳
    """
    
    def __init__(self, session_id: str, sessions_dir: str | Path | None = None):
        # 使用项目根目录作为基准路径
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
    
    @classmethod
    def list_sessions(cls, sessions_dir: str | Path | None = None) -> list[dict[str, Any]]:
        """列出所有已保存的会话."""
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
    def load(cls, session_id: str, sessions_dir: str | Path | None = None) -> Session | None:
        """加载指定会话."""
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


class SessionManager:
    """会话管理器（单例模式）."""
    
    _instance: SessionManager | None = None
    
    def __init__(self, sessions_dir: str | Path | None = None):
        # 使用项目根目录作为基准路径
        if sessions_dir is None:
            project_root = StdPath(__file__).resolve().parent.parent.parent
            sessions_dir = project_root / ".stock_asking" / "sessions"
        
        self.sessions_dir = Path(sessions_dir)
        self.current_session: Session | None = None
    
    @classmethod
    def get_instance(cls, sessions_dir: str | Path | None = None) -> SessionManager:
        """获取单例实例."""
        if cls._instance is None:
            cls._instance = cls(sessions_dir)
        return cls._instance
    
    def create_session(self, session_id: str | None = None) -> Session:
        """创建新会话."""
        if session_id is None:
            # 使用格式化的系统时间作为会话ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"session_{timestamp}"
        
        self.current_session = Session(session_id, self.sessions_dir)
        logger.info(f"🆕 创建新会话：{session_id}")
        return self.current_session
    
    def get_current_session(self) -> Session | None:
        """获取当前会话."""
        return self.current_session
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话."""
        return Session.list_sessions(self.sessions_dir)
    
    def load_session(self, session_id: str) -> Session | None:
        """加载会话."""
        session = Session.load(session_id, self.sessions_dir)
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
        session = Session.load(session_id, self.sessions_dir)
        if not session:
            raise ValueError(f"会话不存在：{session_id}")
        
        # 生成 HTML 内容
        html_content = self._generate_html_report(session)
        
        # 确定输出路径
        if output_path is None:
            reports_dir = Path(".stock_asking/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = reports_dir / f"{session_id}.html"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        output_path.write_text(html_content, encoding="utf-8")
        logger.info(f"📄 HTML 报告已导出：{output_path}")
        
        return output_path
    
    def _generate_html_report(self, session: Session) -> str:
        """生成 HTML 报告内容."""
        stats = session.get_statistics()
        queries = session.get_query_history()
        
        # 构建查询表格行
        query_rows = ""
        for q in queries:
            status_color = {
                "success": "#28a745",
                "failed": "#dc3545",
                "interrupted": "#ffc107",
                "pending": "#6c757d",
            }.get(q.status, "#6c757d")
            
            script_link = ""
            if q.script_path:
                script_link = f'<a href="file:///{q.script_path}" target="_blank">查看脚本</a>'
            
            query_rows += f"""
            <tr>
                <td>{q.query_id}</td>
                <td>{self._escape_html(q.query_text)}</td>
                <td><span style="color: {status_color}; font-weight: bold;">{q.status}</span></td>
                <td>{q.candidates_count}</td>
                <td>{script_link}</td>
                <td>{q.execution_time_ms:.0f} ms</td>
                <td>{self._format_timestamp(q.timestamp)}</td>
            </tr>
            """
        
        # 完整的 HTML 模板
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>会话报告 - {session.session_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2em;
            margin-bottom: 10px;
        }}
        
        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .stat-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        
        .stat-card .label {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .content h2 {{
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: #6c757d;
            background: #f8f9fa;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 会话报告</h1>
            <p>{session.session_id}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="value">{stats['total_queries']}</div>
                <div class="label">总查询数</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color: #28a745;">{stats['successful_queries']}</div>
                <div class="label">成功查询</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color: #dc3545;">{stats['failed_queries']}</div>
                <div class="label">失败查询</div>
            </div>
            <div class="stat-card">
                <div class="value">{stats['success_rate']}%</div>
                <div class="label">成功率</div>
            </div>
        </div>
        
        <div class="content">
            <h2>📋 查询历史</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>查询内容</th>
                        <th>状态</th>
                        <th>候选数</th>
                        <th>脚本</th>
                        <th>耗时</th>
                        <th>时间</th>
                    </tr>
                </thead>
                <tbody>
                    {query_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>生成时间：{self._format_timestamp(time.time())}</p>
            <p>Stock Asking System - AI 股票筛选系统</p>
        </div>
    </div>
</body>
</html>"""
        
        return html_template
    
    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
    
    def _format_timestamp(self, timestamp: float) -> str:
        """格式化时间戳."""
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


# 全局便捷函数
def get_session_manager() -> SessionManager:
    """获取全局会话管理器."""
    return SessionManager.get_instance()


def reset_session_manager():
    """重置会话管理器（用于测试）."""
    SessionManager._instance = None
