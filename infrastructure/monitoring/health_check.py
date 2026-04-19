"""系统健康检查 - 自动监控和告警.

from infrastructure.cache import get_data_cache
import os
import shutil
提供：
- 组件健康状态检查
- 性能指标监控
- 自动告警
- 健康报告生成
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """组件健康状态."""
    
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    last_check: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat(),
            "details": self.details,
        }


@dataclass
class HealthReport:
    """健康报告."""
    
    timestamp: datetime
    overall_status: HealthStatus
    components: list[ComponentHealth]
    summary: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status.value,
            "components": [c.to_dict() for c in self.components],
            "summary": self.summary,
        }


class HealthChecker:
    """健康检查器.
    
    功能：
    - 注册健康检查项
    - 定期执行检查
    - 自动告警
    - 生成健康报告
    
    使用示例::
    
        checker = HealthChecker()
        
        # 注册检查项
        checker.register_check("database", check_database_health)
        checker.register_check("api", check_api_health)
        
        # 执行检查
        report = checker.check_all()
        
        if report.overall_status != HealthStatus.HEALTHY:
            send_alert(report)
    """
    
    def __init__(self, alert_threshold: int = 3):
        """初始化健康检查器.
        
        Args:
            alert_threshold: 连续失败多少次后触发告警
        """
        self.checks: dict[str, Callable[[], ComponentHealth]] = {}
        self.failure_counts: dict[str, int] = {}
        self.alert_threshold = alert_threshold
        self.last_report: HealthReport | None = None
    
    def register_check(self, name: str, check_func: Callable[[], ComponentHealth]) -> None:
        """注册健康检查项.
        
        Args:
            name: 检查项名称
            check_func: 检查函数，返回 ComponentHealth
        """
        self.checks[name] = check_func
        self.failure_counts[name] = 0
        logger.info(f"✅ 注册健康检查: {name}")
    
    def check_component(self, name: str) -> ComponentHealth:
        """检查单个组件.
        
        Args:
            name: 组件名称
            
        Returns:
            组件健康状态
        """
        if name not in self.checks:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"未注册的检查项: {name}",
            )
        
        start_time = time.time()
        
        try:
            health = self.checks[name]()
            latency = (time.time() - start_time) * 1000
            health.latency_ms = latency
            
            # 更新失败计数
            if health.status == HealthStatus.HEALTHY:
                self.failure_counts[name] = 0
            else:
                self.failure_counts[name] += 1
                
                # 检查是否需要告警
                if self.failure_counts[name] >= self.alert_threshold:
                    logger.error(f"🚨 告警: {name} 连续失败 {self.failure_counts[name]} 次")
                    self._trigger_alert(name, health)
            
            return health
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            
            health = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"检查异常: {str(e)}",
                latency_ms=latency,
            )
            
            self.failure_counts[name] += 1
            
            if self.failure_counts[name] >= self.alert_threshold:
                self._trigger_alert(name, health)
            
            return health
    
    def check_all(self) -> HealthReport:
        """检查所有组件.
        
        Returns:
            健康报告
        """
        logger.info("🔍 开始全面健康检查...")
        
        component_healths = []
        
        for name in self.checks:
            health = self.check_component(name)
            component_healths.append(health)
            
            status_icon = {
                HealthStatus.HEALTHY: "✅",
                HealthStatus.DEGRADED: "⚠️",
                HealthStatus.UNHEALTHY: "❌",
                HealthStatus.UNKNOWN: "❓",
            }.get(health.status, "?")
            
            logger.info(f"  {status_icon} {name}: {health.status.value} ({health.latency_ms:.1f}ms)")
        
        # 计算整体状态
        overall_status = self._calculate_overall_status(component_healths)
        
        # 生成摘要
        summary = {
            "total_components": len(component_healths),
            "healthy_count": sum(1 for c in component_healths if c.status == HealthStatus.HEALTHY),
            "degraded_count": sum(1 for c in component_healths if c.status == HealthStatus.DEGRADED),
            "unhealthy_count": sum(1 for c in component_healths if c.status == HealthStatus.UNHEALTHY),
            "avg_latency_ms": sum(c.latency_ms for c in component_healths) / len(component_healths) if component_healths else 0,
        }
        
        report = HealthReport(
            timestamp=datetime.now(),
            overall_status=overall_status,
            components=component_healths,
            summary=summary,
        )
        
        self.last_report = report
        
        logger.info(f"{'=' * 60}")
        logger.info(f"整体状态: {overall_status.value.upper()}")
        logger.info(f"  健康: {summary['healthy_count']}")
        logger.info(f"  降级: {summary['degraded_count']}")
        logger.info(f"  异常: {summary['unhealthy_count']}")
        logger.info(f"  平均延迟: {summary['avg_latency_ms']:.1f}ms")
        logger.info(f"{'=' * 60}")
        
        return report
    
    def get_last_report(self) -> HealthReport | None:
        """获取上次健康报告."""
        return self.last_report
    
    def _calculate_overall_status(self, components: list[ComponentHealth]) -> HealthStatus:
        """计算整体健康状态."""
        if not components:
            return HealthStatus.UNKNOWN
        
        statuses = [c.status for c in components]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        
        return HealthStatus.DEGRADED
    
    def _trigger_alert(self, component_name: str, health: ComponentHealth) -> None:
        """触发告警.
        
        Args:
            component_name: 组件名称
            health: 健康状态
        """
        alert_message = (
            f"🚨 健康告警\n"
            f"组件: {component_name}\n"
            f"状态: {health.status.value}\n"
            f"消息: {health.message}\n"
            f"时间: {datetime.now().isoformat()}"
        )
        
        logger.error(alert_message)
        
        # TODO: 集成实际告警渠道（邮件、钉钉、企业微信等）
        # send_alert_notification(alert_message)


# 预定义的健康检查函数

def check_llm_api_health(api_key: str | None = None) -> ComponentHealth:
    """检查 LLM API 健康状态."""
    
    api_key = api_key or os.getenv("DEFAULT_API_KEY")
    
    if not api_key:
        return ComponentHealth(
            name="llm_api",
            status=HealthStatus.UNHEALTHY,
            message="API Key 未配置",
        )
    
    # 简单检查：验证 API Key 格式
    if len(api_key) < 10:
        return ComponentHealth(
            name="llm_api",
            status=HealthStatus.DEGRADED,
            message="API Key 格式可能不正确",
        )
    
    return ComponentHealth(
        name="llm_api",
        status=HealthStatus.HEALTHY,
        message="LLM API 配置正常",
    )


def check_data_cache_health() -> ComponentHealth:
    """检查数据缓存健康状态."""
    
    try:
        cache = get_data_cache()
        stats = cache.stats()
        
        return ComponentHealth(
            name="data_cache",
            status=HealthStatus.HEALTHY,
            message="数据缓存正常",
            details=stats,
        )
    except Exception as e:
        return ComponentHealth(
            name="data_cache",
            status=HealthStatus.UNHEALTHY,
            message=f"缓存异常: {str(e)}",
        )


def check_disk_space_health(threshold_percent: float = 90.0) -> ComponentHealth:
    """检查磁盘空间."""
    
    try:
        total, used, free = shutil.disk_usage(".")
        usage_percent = (used / total) * 100
        
        if usage_percent > threshold_percent:
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=f"磁盘使用率过高: {usage_percent:.1f}%",
                details={
                    "total_gb": total / (1024**3),
                    "used_gb": used / (1024**3),
                    "free_gb": free / (1024**3),
                    "usage_percent": usage_percent,
                },
            )
        
        return ComponentHealth(
            name="disk_space",
            status=HealthStatus.HEALTHY,
            message=f"磁盘使用率: {usage_percent:.1f}%",
            details={
                "total_gb": total / (1024**3),
                "used_gb": used / (1024**3),
                "free_gb": free / (1024**3),
                "usage_percent": usage_percent,
            },
        )
    except Exception as e:
        return ComponentHealth(
            name="disk_space",
            status=HealthStatus.UNKNOWN,
            message=f"无法检查磁盘空间: {str(e)}",
        )


# 全局健康检查器实例
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器."""
    global _health_checker
    
    if _health_checker is None:
        _health_checker = HealthChecker()
        
        # 注册默认检查项
        _health_checker.register_check("llm_api", check_llm_api_health)
        _health_checker.register_check("data_cache", check_data_cache_health)
        _health_checker.register_check("disk_space", check_disk_space_health)
    
    return _health_checker


def reset_health_checker():
    """重置健康检查器（用于测试）."""
    global _health_checker
    _health_checker = None
