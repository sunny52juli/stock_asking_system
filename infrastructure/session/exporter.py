"""会话导出器 - 将会话导出为HTML报告."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from infrastructure.logging.logger import get_logger

if TYPE_CHECKING:
    from infrastructure.session.storage import SessionStorage

logger = get_logger(__name__)


class SessionExporter:
    """会话导出器 - 生成HTML报告."""
    
    @staticmethod
    def export_to_html(
        session: SessionStorage,
        output_path: str | Path | None = None
    ) -> Path:
        """将会话导出为 HTML 报告.
        
        Args:
            session: 会话对象
            output_path: 输出路径（可选，默认为 .stock_asking/reports/）
            
        Returns:
            HTML 文件路径
        """
        # 生成 HTML 内容
        html_content = SessionExporter._generate_html_report(session)
        
        # 确定输出路径
        if output_path is None:
            reports_dir = Path(".stock_asking/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = reports_dir / f"{session.session_id}.html"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        output_path.write_text(html_content, encoding="utf-8")
        logger.info(f"📄 HTML 报告已导出：{output_path}")
        
        return output_path
    
    @staticmethod
    def _generate_html_report(session: SessionStorage) -> str:
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
                <td>{SessionExporter._escape_html(q.query_text)}</td>
                <td><span style="color: {status_color}; font-weight: bold;">{q.status}</span></td>
                <td>{q.candidates_count}</td>
                <td>{script_link}</td>
                <td>{q.execution_time_ms:.2f}ms</td>
                <td>{SessionExporter._format_timestamp(q.timestamp)}</td>
            </tr>
            """
        
        # 生成完整HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>会话报告 - {stats['session_id']}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }}
        table {{
            width: 100%;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 会话报告</h1>
        <p>会话ID: {stats['session_id']}</p>
        <p>创建时间: {stats['created_at']} | 更新时间: {stats['updated_at']}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>总查询数</h3>
            <div class="value">{stats['total_queries']}</div>
        </div>
        <div class="stat-card">
            <h3>成功查询</h3>
            <div class="value" style="color: #28a745;">{stats['successful_queries']}</div>
        </div>
        <div class="stat-card">
            <h3>失败查询</h3>
            <div class="value" style="color: #dc3545;">{stats['failed_queries']}</div>
        </div>
        <div class="stat-card">
            <h3>成功率</h3>
            <div class="value">{stats['success_rate']}%</div>
        </div>
    </div>
    
    <h2>查询历史</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>查询内容</th>
                <th>状态</th>
                <th>候选数</th>
                <th>脚本</th>
                <th>执行时间</th>
                <th>时间戳</th>
            </tr>
        </thead>
        <tbody>
            {query_rows}
        </tbody>
    </table>
</body>
</html>"""
        
        return html
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))
    
    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        """格式化时间戳."""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
