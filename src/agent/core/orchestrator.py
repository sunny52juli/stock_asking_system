"""查询编排器 - 协调Agent初始化和查询执行."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.logging.logger import get_logger
from infrastructure.config.settings import get_settings
from utils.agent.result_checker import _check_api_key

# 导入新的模块化组件
from src.agent.core.component_manager import ComponentManager
from src.agent.core.agent_factory import AgentFactory
from src.agent.execution.query_executor import QueryExecutor
from src.agent.execution.state_manager import SessionStateManager

logger = get_logger(__name__)


class ScreenerOrchestrator:
    """筛选器编排器 - 协调组件管理和查询执行."""
    
    def __init__(self, settings=None, state_manager: SessionStateManager | None = None):
        """初始化.
        
        Args:
            settings: 全局配置
            state_manager: 会话状态管理器
        """
        self.settings = settings or get_settings()
        self.state_manager = state_manager
        
        # 使用项目根目录
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        
        # 初始化组件管理器
        self.component_manager = ComponentManager(self.settings, project_root)
        
        # Agent工厂
        self.agent_factory = AgentFactory(self.settings)
        
        # 数据相关（延迟加载）
        self.data = None
        self.index_data = None
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
            # 0. 设置全局观察期约束
            self.component_manager.set_observation_days(self.settings.observation_days)
            
            # 1. 初始化所有组件
            self.component_manager.initialize_all()
            
            # 2. 创建Bridge工具和Tool Provider
            def get_data():
                return (self.data, self.index_data)
            
            self.component_manager.create_bridge_tools(
                data_fn=get_data,
                stock_codes=self.stock_codes
            )
            
            # 3. 创建查询执行器
            self.query_executor = QueryExecutor(
                agent=None,
                initial_files=None,
                session_manager=self.component_manager.session_manager,
                telemetry=self.component_manager.telemetry,
                quality_evaluator=self.component_manager.quality_evaluator,
                settings=self.settings,
                hooks=self.component_manager.hooks,
            )
            
            # 4. 立即创建Agent
            self._create_agent()
            
            logger.info("\n" + "=" * 60)
            logger.info("[OK] 系统初始化完成")
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.exception("初始化失败：%s", e)
            return False
    
    def _create_agent(self, query: str | None = None, bridge_tools: dict | None = None):
        """创建或复用Agent.
        
        Args:
            query: 用户查询（可选）
            bridge_tools: 桥接工具字典（交互式模式）
        """
        self.agent_factory.create_or_reuse(
            component_initializer=self.component_manager.component_initializer,
            query=query,
            bridge_tools=bridge_tools,
        )
        
        # 更新查询执行器
        self.agent_factory.update_executor(self.query_executor)
    
    def execute_query(self, query: str, query_id: int | SessionStateManager = None) -> dict[str, Any] | None:
        """执行单个查询.
        
        Args:
            query: 用户查询
            query_id: 查询ID或SessionStateManager实例
            
        Returns:
            查询结果或None
        """
        if not self.query_executor:
            logger.error("[ERROR] QueryExecutor未初始化")
            return None
        
        # 每次查询前创建Agent
        self._create_agent(query=query)
        
        # 委托给QueryExecutor执行
        return self.query_executor.execute_query(query, query_id)
    
    def execute_query_with_logic(self, logic: dict, state_manager: SessionStateManager) -> dict[str, Any]:
        """使用指定的筛选逻辑执行查询.
        
        Args:
            logic: 筛选逻辑字典
            state_manager: 会话状态管理器
            
        Returns:
            查询结果字典
        """
        if not self.query_executor:
            logger.error("[ERROR] QueryExecutor未初始化")
            return {"success": False, "error": "QueryExecutor未初始化", "candidates": []}
        
        try:
            # 直接使用 StockScreener 执行筛选逻辑
            from utils.screening.stock_screener import StockScreener
            
            screener = StockScreener(
                data=self.data,
                stock_codes=self.stock_codes,
                index_data=self.index_data,
            )
            
            candidates = screener.execute_screening(
                screening_logic=logic,
                top_n=10,
                query=logic.get("name", ""),
            )
            
            return {
                "success": True,
                "candidates": candidates,
                "messages": [],
            }
            
        except Exception as e:
            logger.error(f"[ERROR] 执行筛选逻辑失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "candidates": [],
            }
