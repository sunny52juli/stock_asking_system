"""可观测性模块 - OpenTelemetry 集成.

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import SpanExportResult
from src.agent.config import TelemetryConfig
from src.agent.telemetry import get_tracer, get_meter, record_metric
提供 Trace Span 和 Metrics 支持，默认关闭不影响性能。
通过 settings.yaml 中的 telemetry.enabled 配置开关。

使用方法::


    tracer = get_tracer()
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("key", "value")
        ...

    # 记录 metrics
    record_metric("agent.tool_calls.count", 5)
"""

from __future__ import annotations

import contextlib
import json
import time
from contextlib import contextmanager
from pathlib import Path
, Any

from infrastructure.logging.logger import get_logger


logger = get_logger(__name__)

# 全局状态
_initialized = False
_tracer: Any = None
_meter: Any = None
_metrics: dict[str, Any] = {}
_session_metrics: dict[str, float | int] = {}


class _NoOpSpan:
    """空操作 Span，当 OpenTelemetry 未启用时使用."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass


class _NoOpTracer:
    """空操作 Tracer."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any):  # noqa: ANN201
        yield _NoOpSpan()


class _NoOpMeter:
    """空操作 Meter."""

    def create_counter(self, name: str, **kwargs: Any) -> Any:
        return _NoOpCounter()

    def create_histogram(self, name: str, **kwargs: Any) -> Any:
        return _NoOpCounter()

    def create_up_down_counter(self, name: str, **kwargs: Any) -> Any:
        return _NoOpCounter()


class _NoOpCounter:
    """空操作计数器."""

    def add(self, amount: int | float, attributes: dict[str, str] | None = None) -> None:
        pass

    def record(self, amount: int | float, attributes: dict[str, str] | None = None) -> None:
        pass


def init_telemetry(config: TelemetryConfig) -> None:
    """初始化 OpenTelemetry.

    Args:
        config: TelemetryConfig 配置实例
    """
    global _initialized, _tracer, _meter, _metrics

    if not config.enabled:
        _tracer = _NoOpTracer()
        _meter = _NoOpMeter()
        _initialized = True
        return

    try:

        resource = Resource.create({"service.name": "stock-asking-agent"})

        # 配置 Tracer
        tracer_provider = TracerProvider(resource=resource)

        if config.exporter == "console":
                ConsoleSpanExporter,
                SimpleSpanProcessor,
            )

            tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        elif config.exporter == "otlp" and config.endpoint:
                OTLPSpanExporter,
            )

            tracer_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=config.endpoint))
            )

        elif config.exporter == "file":
                SimpleSpanProcessor,
            )

            trace_path = Path(config.trace_file)
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            tracer_provider.add_span_processor(
                SimpleSpanProcessor(_FileSpanExporter(str(trace_path)))
            )

        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer("stock-asking.agent")

        # 配置 Meter
        meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter("stock-asking.agent")

        # 创建核心 metrics
        _metrics["query_duration"] = _meter.create_histogram(
            "agent.query.duration",
            unit="s",
            description="Agent 查询执行时间",
        )
        _metrics["tool_calls_count"] = _meter.create_counter(
            "agent.tool_calls.count",
            description="工具调用次数",
        )
        _metrics["retry_count"] = _meter.create_counter(
            "agent.retry.count",
            description="重试次数",
        )

        _initialized = True
        logger.info("OpenTelemetry 已启用 (exporter=%s)", config.exporter)

    except ImportError:
        logger.warning(
            "opentelemetry 包未安装，可观测性功能已禁用。"
            "请运行: pip install opentelemetry-api opentelemetry-sdk"
        )
        _tracer = _NoOpTracer()
        _meter = _NoOpMeter()
        _initialized = True


class _FileSpanExporter:
    """将 Span 导出到 JSON 文件."""

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def export(self, spans: Any) -> Any:
        with contextlib.suppress(Exception), open(self._file_path, "a") as f:
            for span in spans:
                span_data = {
                    "name": span.name,
                    "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "attributes": dict(span.attributes) if span.attributes else {},
                    "status": str(span.status),
                }
                f.write(json.dumps(span_data, ensure_ascii=False, default=str) + "\n")
        # 返回 SUCCESS
        try:

            return SpanExportResult.SUCCESS
        except ImportError:
            return None

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def get_tracer() -> Any:
    """获取 Tracer 实例."""
    if not _initialized:
        return _NoOpTracer()
    return _tracer


def get_meter() -> Any:
    """获取 Meter 实例."""
    if not _initialized:
        return _NoOpMeter()
    return _meter


def record_metric(name: str, value: float | int, attributes: dict[str, str] | None = None) -> None:
    """记录 metric 值."""
    # 累积到 session metrics
    _session_metrics[name] = _session_metrics.get(name, 0) + value

    if name in _metrics:
        metric = _metrics[name]
        if hasattr(metric, "record"):
            metric.record(value, attributes)
        elif hasattr(metric, "add"):
            metric.add(value, attributes)


def reset_session_metrics() -> None:
    """重置 session metrics."""
    _session_metrics.clear()


def get_session_metrics_summary() -> dict[str, float | int]:
    """获取当前 session 的 metrics 摘要."""
    return dict(_session_metrics)


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None):
    """便捷的 span 上下文管理器.

    Args:
        name: Span 名称
        attributes: 可选属性
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v) if not isinstance(v, int | float | bool | str) else v)
        start = time.time()
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            duration = time.time() - start
            span.set_attribute(f"{name}.duration_s", duration)
