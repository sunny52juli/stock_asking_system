"""观测与记忆管理模块 - 统一集成Telemetry和Long-term Memory."""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

from infrastructure.telemetry import get_telemetry, SimpleTelemetry
from src.agent.memory import GraphDatabaseMemory, StrategyRecord

logger = logging.getLogger(__name__)


class ObservabilityManager:
    """观测与记忆管理器.
    
    统一管理：
    - Telemetry：性能追踪、查询统计
    - Long-term Memory：策略历史、经验学习
    
    使用示例：
        obs = ObservabilityManager()
        
        # 追踪查询执行
        with obs.trace_query("找出高波动股票"):
            result = execute_screening(query)
            obs.record_strategy(
                query=query,
                strategy_name="high_volatility",
                screening_logic=result["logic"],
                candidates_count=len(result["candidates"])
            )
        
        # 获取历史策略建议
        suggestions = obs.get_strategy_suggestions("高波动")
        
        # 打印会话摘要
        obs.print_summary()
    """
    
    def __init__(self, enabled: bool = True, project_root: Path | None = None):
        """初始化观测管理器.
        
        Args:
            enabled: 是否启用观测功能
            project_root: 项目根目录（用于定位数据文件）
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
        
        self.enabled = enabled
        self.project_root = project_root
        
        # 初始化 Telemetry
        self.telemetry = get_telemetry(enabled=enabled)
        
        # 初始化 Long-term Memory（从环境变量读取配置）
        self.memory = None
        try:
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "neo4j")
            
            self.memory = GraphDatabaseMemory(
                uri=neo4j_uri,
                username=neo4j_username,
                password=neo4j_password,
                auto_start=False  # Aura 不需要自动启动
            )
            logger.info("[MEMORY] Neo4j 连接成功")
        except Exception as e:
            logger.warning(f"[MEMORY] Neo4j 连接失败，记忆功能已禁用: {e}")
            logger.warning("[MEMORY] 提示: 请检查 .env 文件中的 NEO4J_URI、NEO4J_USERNAME、NEO4J_PASSWORD 配置")
        
        logger.info(f"[OBSERVABILITY] 观测系统已{'启用' if enabled else '禁用'}")
    
    def trace_query(self, query: str, **metadata):
        """追踪查询执行（上下文管理器）.
        
        Args:
            query: 用户查询
            **metadata: 额外元数据
            
        Returns:
            上下文管理器
        """
        if not self.enabled:
            from contextlib import nullcontext
            return nullcontext()
        
        return self.telemetry.trace_span("execute_query", query=query, **metadata)
    
    def record_strategy(
        self,
        query: str,
        strategy_name: str,
        screening_logic: dict[str, Any],
        candidates_count: int,
        success: bool = True,
        notes: str = ""
    ) -> int:
        """记录策略到长期记忆.
        
        Args:
            query: 原始查询
            strategy_name: 策略名称
            screening_logic: 筛选逻辑配置
            candidates_count: 候选股票数量
            success: 是否成功执行
            notes: 备注信息
            
        Returns:
            记录ID
        """
        if not self.enabled:
            return -1
        
        try:
            record = StrategyRecord(
                query=query,
                strategy_name=strategy_name,
                screening_logic=screening_logic,
                candidates_count=candidates_count,
                success=success,
                notes=notes
            )
            record_id = self.memory.save_strategy(record)
            logger.debug(f"[MEMORY] 策略已保存: {strategy_name} (ID: {record_id})")
            return record_id
        except Exception as e:
            logger.warning(f"[MEMORY] 保存策略失败: {e}")
            return -1
    
    def get_strategy_suggestions(self, keyword: str, limit: int = 5) -> list[StrategyRecord]:
        """获取相似策略建议.
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            策略记录列表
        """
        if not self.enabled:
            return []
        
        try:
            strategies = self.memory.search_strategies(keyword, limit=limit)
            if strategies:
                logger.info(f"[MEMORY] 找到 {len(strategies)} 个相似策略")
            return strategies
        except Exception as e:
            logger.warning(f"[MEMORY] 搜索策略失败: {e}")
            return []
    
    def get_recent_strategies(self, limit: int = 10) -> list[StrategyRecord]:
        """获取最近的策略记录.
        
        Args:
            limit: 返回数量限制
            
        Returns:
            策略记录列表
        """
        if not self.enabled:
            return []
        
        try:
            return self.memory.get_recent_strategies(limit=limit)
        except Exception as e:
            logger.warning(f"[MEMORY] 获取最近策略失败: {e}")
            return []
    
    def record_tool_call(self, tool_name: str, **metadata):
        """记录工具调用.
        
        Args:
            tool_name: 工具名称
            **metadata: 额外元数据
        """
        if not self.enabled:
            return
        
        self.telemetry.record_tool_call(tool_name, **metadata)
    
    def record_query_result(self, query: str, success: bool, script_path: str | None = None):
        """记录查询结果统计.
        
        Args:
            query: 查询内容
            success: 是否成功
            script_path: 脚本路径（可选）
        """
        if not self.enabled:
            return
        
        self.telemetry.record_query_result(query, success, script_path)
    
    def print_summary(self):
        """打印会话摘要."""
        if not self.enabled:
            return
        
        self.telemetry.print_session_summary()
        
        # 显示最近策略
        recent = self.get_recent_strategies(limit=3)
        if recent:
            logger.info("=" * 60)
            logger.info("[MEMORY] 最近保存的策略")
            logger.info("=" * 60)
            for i, strategy in enumerate(recent, 1):
                logger.info(f"   {i}. {strategy.strategy_name}")
                logger.info(f"      查询: {strategy.query[:50]}...")
                logger.info(f"      候选: {strategy.candidates_count} 只")
            logger.info("=" * 60)
    
    def close(self):
        """关闭资源."""
        try:
            self.memory.close()
            logger.info("[OBSERVABILITY] 观测系统已关闭")
        except Exception as e:
            logger.warning(f"[OBSERVABILITY] 关闭失败: {e}")


# 全局单例
_instance: ObservabilityManager | None = None


def get_observability(enabled: bool = True, project_root: Path | None = None) -> ObservabilityManager:
    """获取全局观测管理器实例.
    
    Args:
        enabled: 是否启用
        project_root: 项目根目录
        
    Returns:
        ObservabilityManager实例
    """
    global _instance
    if _instance is None:
        _instance = ObservabilityManager(enabled=enabled, project_root=project_root)
    return _instance


def reset_observability():
    """重置观测管理器实例（用于测试）."""
    global _instance
    if _instance:
        _instance.close()
    _instance = None
