"""会话数据模型."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


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
