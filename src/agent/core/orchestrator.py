"""查询编排器 - 协调Agent初始化和查询执行（精简版）."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from infrastructure.logging.logger import LoggerMixin, get_logger
from infrastructure.config.settings import get_settings
from utils.agent.result_checker import _check_api_key
from src.agent.quality.quality_evaluator import ScreeningQualityEvaluator
from src.agent.harness.hooks import HookExecutor
from infrastructure.telemetry import get_telemetry
from infrastructure.session import get_session_manager
from infrastructure.retry.manager import get_retry_manager

# 导入新的模块化组件
from src.agent.initialization.component_initializer import ComponentInitializer
from src.agent.execution.query_executor import QueryExecutor

from infrastructure.errors.exceptions import ToolExecutionError
from src.agent.models.screening_logic import ToolStep
logger = get_logger(__name__)


class ScreenerOrchestrator(LoggerMixin):
    """筛选器编排器 - 负责高层协调和组件管理."""
    
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        
        # 使用项目根目录（相对于此文件的位置）
        # orchestrator.py -> core/ -> agent/ -> src/ -> 项目根目录
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        
        # 初始化核心组件管理器
        self.component_initializer = ComponentInitializer(self.settings, project_root)
        
        # 质量评估器
        self.quality_evaluator = ScreeningQualityEvaluator(project_root / "app" / "setting" / "rules")
        
        # Harness组件
        self.config_dir = project_root / ".stock_asking"
        logger.info(f"📁 Hook config directory: {self.config_dir}")
        logger.info(f"📁 Hook scripts directory: {self.config_dir / 'hooks'}")
        self.hooks = HookExecutor(self.settings.harness.hooks, self.config_dir)
        
        # 可观测性和会话管理
        self.telemetry = get_telemetry(enabled=True)
        self.session_manager = get_session_manager()
        
        # 重试管理器
        self.retry_manager = get_retry_manager()
        
        # Agent 相关组件（延迟初始化）
        self.agent = None
        self.initial_files = None
        self.data = None
        self.index_data = None  # 指数数据
        self.stock_codes = []
        
        # 查询执行器（在数据加载后创建）
        self.query_executor: QueryExecutor | None = None
    
    def initialize(self) -> bool:
        """初始化Agent系统.
        
        Returns:
            True if successful
        """
        if not _check_api_key():
            return False
        
        try:
            # 0. 设置全局观察期约束（用于 ToolStep 参数验证）
            ToolStep.set_observation_days(self.settings.observation_days)
            logger.info(f"🔧 设置工具窗口参数上限：window <= {self.settings.observation_days} (observation_days)")
            
            # 1. 初始化所有组件（不加载数据）
            logger.info("\n" + "=" * 60)
            logger.info("步骤 1/2: 初始化Agent组件")
            logger.info("=" * 60)
            self.component_initializer.initialize_all()
            
            # 2. 创建 Bridge 工具和 Tool Provider（数据将在 StockPoolService 中加载）
            logger.info("\n" + "=" * 60)
            logger.info("步骤 2/2: 创建工具层（占位符）")
            logger.info("=" * 60)
            
            # 暂时使用空数据，实际数据将在 StockPoolService.apply_filter() 中加载
            def get_data():
                data_tuple = (self.data, self.index_data)
                return data_tuple
            
            self.component_initializer.create_bridge_tools(
                data_fn=get_data,
                stock_codes=self.stock_codes
            )
            self.component_initializer.create_tool_provider()
            
            # 3. 创建查询执行器
            self.query_executor = QueryExecutor(
                agent=None,  # 延迟创建
                initial_files=None,  # 将在创建Agent时设置
                session_manager=self.session_manager,
                telemetry=self.telemetry,
                quality_evaluator=self.quality_evaluator,
                settings=self.settings,
                hooks=self.hooks,  # 传入 HookExecutor 实例
            )
            
            # 4. 深度模式下立即创建 Agent
            if self.settings.harness.deep_thinking:
                self._create_agent()
            
            logger.info("\n" + "=" * 60)
            logger.info("✅ 系统初始化完成（数据将在 StockPoolService 中加载）")
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.exception("初始化失败：%s", e)
            return False
    
    def _create_agent(self, query: str | None = None):
        """创建或复用 Agent.
        
        Args:
            query: 用户查询（可选），用于智能选择工具
        """
        # Deep Mode: Agent 已预创建，直接返回
        if self.settings.harness.deep_thinking and self.agent:
            logger.debug("Reusing pre-created deep thinking agent")
            return
        
        # Quick Mode: 检查是否可以复用
        if not self.settings.harness.deep_thinking and self.agent:
            logger.debug("Reusing quick mode agent")
            return
        
        # 创建新 Agent
        logger.info(f"Creating new agent (deep_thinking={self.settings.harness.deep_thinking})...")
        self.agent, self.initial_files = self.component_initializer.create_agent(
            llm=self.component_initializer.llm,
            tool_provider=self.component_initializer.tool_provider,
            skill_registry=self.component_initializer.skill_registry,
            long_term_memory=self.component_initializer.long_term_memory,
            query=query,
        )
        
        # 更新查询执行器的 agent 和 initial_files
        if self.query_executor:
            self.query_executor.agent = self.agent
            self.query_executor.initial_files = self.initial_files
    
    def execute_query(self, query: str, query_id: int) -> dict[str, Any] | None:
        """执行单个查询.
        
        Args:
            query: 用户查询
            query_id: 查询ID
            
        Returns:
            查询结果或None
        """
        if not self.query_executor:
            raise RuntimeError("系统未初始化，请先调用 initialize()")
        
        # 快速模式下，如果 Agent 尚未创建，则根据查询创建
        if not self.settings.harness.deep_thinking and not self.agent:
            self._create_agent(query)
        
        return self.query_executor.execute_query(query, query_id)
    
    def execute_with_retry(self, tool_name: str, func, **params):
        """带重试的执行.
        
        Args:
            tool_name: 工具名称
            func: 要执行的函数
            **params: 函数参数
            
        Returns:
            执行结果
        """
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                result = func(**params)
                self.retry_manager.record_success(tool_name)
                return result
            except Exception as e:
                last_error = e
                should_retry, adjusted_params = self.retry_manager.check_and_prepare_retry(
                    e, tool_name, params
                )
                if not should_retry:
                    raise
                params = adjusted_params
                logger.warning(f"⚠️ 重试第 {attempt + 1} 次...")
        
        raise ToolExecutionError(
            f"工具 {tool_name} 重试 {max_attempts} 次后仍失败",
            error_code="TOOL_RETRY_EXHAUSTED",
            recoverable=False,
            details={"tool_name": tool_name, "last_error": str(last_error)},
        ) from last_error
