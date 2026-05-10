"""组件管理器 - 负责系统组件的初始化和管理."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from src.agent.quality.quality_evaluator import ScreeningQualityEvaluator
from src.agent.harness.hooks import HookExecutor
from infrastructure.telemetry import get_telemetry
from infrastructure.session import get_session_manager
from infrastructure.retry.manager import get_retry_manager
from src.agent.initialization.component_initializer import ComponentInitializer

logger = get_logger(__name__)


class ComponentManager:
    """组件管理器 - 管理所有系统组件的生命周期."""
    
    def __init__(self, settings: Any, project_root: Path):
        """初始化.
        
        Args:
            settings: 全局配置
            project_root: 项目根目录
        """
        self.settings = settings
        self.project_root = project_root
        
        # 核心组件初始化器
        self.component_initializer = ComponentInitializer(settings, project_root)
        
        # 质量评估器
        self.quality_evaluator = ScreeningQualityEvaluator(
            project_root / "app" / "setting" / "rules"
        )
        
        # Harness组件
        self.config_dir = project_root / ".stock_asking"
        logger.info(f"[CONFIG] Hook config directory: {self.config_dir}")
        self.hooks = HookExecutor(settings.harness.hooks, self.config_dir)
        
        # 可观测性和会话管理
        self.telemetry = get_telemetry(enabled=True)
        self.session_manager = get_session_manager()
        
        # 重试管理器
        self.retry_manager = get_retry_manager()
    
    def initialize_all(self):
        """初始化所有组件."""
        logger.info("\n" + "=" * 60)
        logger.info("步骤 1/2: 初始化Agent组件")
        logger.info("=" * 60)
        self.component_initializer.initialize_all()
    
    def create_bridge_tools(self, data_fn, stock_codes: list):
        """创建Bridge工具.
        
        Args:
            data_fn: 数据获取函数
            stock_codes: 股票代码列表
        """
        logger.info("\n" + "=" * 60)
        logger.info("步骤 2/2: 创建工具层")
        logger.info("=" * 60)
        
        self.component_initializer.create_bridge_tools(
            data_fn=data_fn,
            stock_codes=stock_codes
        )
        self.component_initializer.create_tool_provider()
    
    def set_observation_days(self, observation_days: int):
        """设置全局观察期约束.
        
        Args:
            observation_days: 观察期天数
        """
        from src.agent.models.screening_logic import ToolStep
        ToolStep.set_observation_days(observation_days)
        logger.info(f"[CONFIG] 设置工具窗口参数上限：window <= {observation_days}")
