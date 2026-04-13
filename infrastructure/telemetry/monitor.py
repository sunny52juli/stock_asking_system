"""轻量级可观测性系统 - 追踪脚本生成质量和性能."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TraceRecord:
    """追踪记录."""
    
    operation: str
    start_time: float
    end_time: float | None = None
    status: str = "running"  # running/success/error
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    
    @property
    def duration_ms(self) -> float:
        """执行耗时（毫秒）."""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "metadata": self.metadata,
            "error": self.error,
        }


class SimpleTelemetry:
    """轻量级遥测系统.
    
    特点：
    - 零开销禁用模式（enabled=False 时完全跳过）
    - 文件输出 Trace 记录
    - 自动统计关键指标
    """
    
    def __init__(
        self,
        enabled: bool = True,
        trace_dir: str | Path | None = None,
    ):
        # 使用项目根目录作为基准路径
        if trace_dir is None:
            from pathlib import Path as StdPath
            project_root = StdPath(__file__).resolve().parent.parent.parent
            trace_dir = project_root / ".stock_asking" / "traces"
        
        self.enabled = enabled
        self.trace_dir = Path(trace_dir)
        
        if self.enabled:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📊 Telemetry 已启用，Trace 目录：{self.trace_dir}")
        else:
            logger.debug("📊 Telemetry 已禁用")
        
        # 会话级别的统计
        self._current_session_stats: dict[str, Any] = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_duration_ms": 0.0,
            "tool_calls": 0,
        }
    
    @contextmanager
    def trace_span(self, operation_name: str, **metadata):
        """创建追踪 Span（上下文管理器）.
        
        Usage:
            with telemetry.trace_span("generate_script", query=query):
                # 执行业务逻辑
                result = agent.invoke(...)
        """
        if not self.enabled:
            yield
            return
        
        record = TraceRecord(
            operation=operation_name,
            start_time=time.time(),
            metadata=metadata,
        )
        
        try:
            yield record
            record.status = "success"
            record.end_time = time.time()
            self._save_trace(record)
            self._update_stats(success=True, duration_ms=record.duration_ms)
        except Exception as e:
            record.status = "error"
            record.error = str(e)
            record.end_time = time.time()
            self._save_trace(record)
            self._update_stats(success=False, duration_ms=record.duration_ms)
            raise
    
    def record_tool_call(self, tool_name: str, **metadata):
        """记录工具调用."""
        if not self.enabled:
            return
        
        record = TraceRecord(
            operation=f"tool_call.{tool_name}",
            start_time=time.time(),
            end_time=time.time(),
            status="success",
            metadata=metadata,
        )
        self._save_trace(record)
        self._current_session_stats["tool_calls"] += 1
    
    def record_query_result(self, query: str, success: bool, script_path: str | None = None):
        """记录查询结果."""
        if not self.enabled:
            return
        
        self._current_session_stats["total_queries"] += 1
        if success:
            self._current_session_stats["successful_queries"] += 1
        else:
            self._current_session_stats["failed_queries"] += 1
        
        # 保存会话统计
        self._save_session_stats()
    
    def _save_trace(self, record: TraceRecord):
        """保存 Trace 记录到文件."""
        try:
            timestamp = int(record.start_time * 1000)
            trace_file = self.trace_dir / f"trace_{timestamp}_{record.operation.replace('.', '_')}.json"
            trace_file.write_text(
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存 Trace 记录失败：{e}")
    
    def _update_stats(self, success: bool, duration_ms: float):
        """更新会话统计."""
        self._current_session_stats["total_duration_ms"] += duration_ms
    
    def _save_session_stats(self):
        """保存会话统计."""
        try:
            stats_file = self.trace_dir / "session_stats.json"
            stats_file.write_text(
                json.dumps(self._current_session_stats, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存会话统计失败：{e}")
    
    def get_session_summary(self) -> dict[str, Any]:
        """获取当前会话摘要."""
        stats = self._current_session_stats.copy()
        total = stats["total_queries"]
        if total > 0:
            stats["success_rate"] = round(stats["successful_queries"] / total * 100, 2)
            stats["avg_duration_ms"] = round(stats["total_duration_ms"] / total, 2)
        else:
            stats["success_rate"] = 0.0
            stats["avg_duration_ms"] = 0.0
        
        return stats
    
    def print_session_summary(self):
        """打印会话摘要."""
        summary = self.get_session_summary()
        logger.info("=" * 60)
        logger.info("📊 会话统计摘要")
        logger.info("=" * 60)
        logger.info(f"   总查询数：{summary['total_queries']}")
        logger.info(f"   成功数：{summary['successful_queries']}")
        logger.info(f"   失败数：{summary['failed_queries']}")
        logger.info(f"   成功率：{summary['success_rate']}%")
        logger.info(f"   平均耗时：{summary['avg_duration_ms']}ms")
        logger.info(f"   工具调用次数：{summary['tool_calls']}")
        logger.info("=" * 60)


# 全局单例
_telemetry_instance: SimpleTelemetry | None = None


def get_telemetry(enabled: bool = True) -> SimpleTelemetry:
    """获取全局 Telemetry 实例."""
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = SimpleTelemetry(enabled=enabled)
    return _telemetry_instance


def reset_telemetry():
    """重置 Telemetry 实例（用于测试）."""
    global _telemetry_instance
    _telemetry_instance = None
