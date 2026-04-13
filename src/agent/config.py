"""Agent 配置 - 复用 infrastructure 配置模型.

从 infrastructure.config.settings 导入共享配置，
仅定义 Agent 特有的配置项。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# 从 infrastructure 导入共享配置
from infrastructure.config.settings import (
    BacktestConfig,
    DataConfig,
    HarnessConfig,
    LLMConfig,
    OutputConfig,
    PermissionsConfig,
)

# Agent 特有配置（基础设施中未定义的）
class LoggingConfig(BaseModel):
    """日志配置."""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class TelemetryConfig(BaseModel):
    """遥测配置."""
    enabled: bool = Field(default=False, description="是否启用遥测")
    endpoint: str | None = Field(default=None, description="遥测端点")


class ReflectionConfig(BaseModel):
    """反思配置."""
    enabled: bool = Field(default=True, description="是否启用反思机制")
    max_retries: int = Field(default=3, description="最大重试次数")

# Agent 特有配置
class AgentConfig(BaseModel):
    """Agent 核心配置."""

    mode: str = Field(default="single", description="运行模式: single/deep_thinking")
    enable_subagents: bool = Field(default=False, description="是否启用子Agent")


class HookConfig(BaseModel):
    """Hook 配置."""

    type: str = Field(default="command", description="Hook类型: command/script")
    command: str = Field(..., description="执行的命令")


class HookMatcherConfig(BaseModel):
    """Hook 匹配器配置."""

    matcher: str | None = Field(default=None, description="工具名称匹配模式")
    hooks: list[HookConfig] = Field(default_factory=list)


class HooksConfig(BaseModel):
    """Hooks 完整配置."""

    PreToolUse: list[HookMatcherConfig] = Field(default_factory=list)
    PostToolUse: list[HookMatcherConfig] = Field(default_factory=list)
    Stop: list[HookMatcherConfig] = Field(default_factory=list)


class AgentConfigModel(BaseModel):
    """Agent 完整配置模型."""

    agent: AgentConfig = Field(default_factory=AgentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    reflection: ReflectionConfig = Field(default_factory=ReflectionConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
