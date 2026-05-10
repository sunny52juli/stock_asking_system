"""查询执行器 - 负责执行用户查询."""

from __future__ import annotations

import time
from typing import Any

from infrastructure.logging.logger import get_logger
from infrastructure.session import SessionManager, QueryRecord
from infrastructure.telemetry import SimpleTelemetry
from infrastructure.errors.exceptions import AgentExecutionError

from src.agent.execution.candidate_extractor import CandidateExtractor
from src.agent.execution.result_processor import ResultProcessor

logger = get_logger(__name__)


class QueryExecutor:
    """查询执行器 - 协调Agent调用和结果处理."""
    
    def __init__(
        self,
        agent,
        initial_files: dict,
        session_manager: SessionManager,
        telemetry: SimpleTelemetry,
        quality_evaluator,
        settings: Any,
        hooks=None,
    ):
        """初始化.
        
        Args:
            agent: Agent实例
            initial_files: 初始文件上下文
            session_manager: 会话管理器
            telemetry: 遥测系统
            quality_evaluator: 质量评估器
            settings: 全局配置
            hooks: HookExecutor实例（可选）
        """
        self.agent = agent
        self.initial_files = initial_files
        self.session_manager = session_manager
        self.telemetry = telemetry
        self.quality_evaluator = quality_evaluator
        self.settings = settings
        self.hooks = hooks
        
        # 结果处理器
        self.result_processor = ResultProcessor(quality_evaluator, hooks)
    
    def execute_query(self, query: str, query_id: int) -> dict[str, Any] | None:
        """执行单个查询.
        
        Args:
            query: 用户查询
            query_id: 查询ID
            
        Returns:
            查询结果或None
        """
        from src.agent.tools import bridge
        
        # 重置run_screening调用计数器
        bridge._run_screening_call_count = 0
        bridge._last_screening_result = None
        
        # ✅ 简化日志：只显示查询ID，不显示完整query内容（避免输出冗长的prompt）
        logger.info(f"🔄 执行查询 {query_id}")
        
        thread_id = f"query-{query_id}"
        start_time = time.time()
        
        # 创建会话记录
        session = self.session_manager.get_current_session()
        if not session:
            session = self.session_manager.create_session()
        
        session.add_message("user", query, query_id=query_id)
        
        # 添加查询记录
        query_record = QueryRecord(query_id=query_id, query_text=query)
        session.add_query_record(query_record)
        
        try:
            with self.telemetry.trace_span("execute_query", query_id=query_id, query=query[:50]):
                result = self._execute_query(query, query_id, thread_id, session)
                return result
            
        except KeyboardInterrupt:
            logger.warning("\n用户中断程序")
            session.update_query_status(query_id=query_id, status="interrupted")
            session.save()
            return None
        except Exception as e:
            logger.exception("查询失败：%s", e)
            execution_time_ms = (time.time() - start_time) * 1000
            session.update_query_status(
                query_id=query_id,
                status="failed",
                error_message=str(e),
                execution_time_ms=execution_time_ms,
            )
            session.save()
            
            raise AgentExecutionError(
                f"查询执行失败：{e}",
                error_code="QUERY_EXECUTION_FAILED",
                recoverable=True,
                suggestion="请检查网络连接或稍后重试",
                details={
                    "query": query,
                    "query_id": query_id,
                    "execution_time_ms": execution_time_ms,
                },
            ) from e
    
    def _execute_query(
        self, 
        query: str, 
        query_id: int, 
        thread_id: str,
        session
    ) -> dict[str, Any] | None:
        """执行查询（内部实现）."""
        start_time = time.time()
        
        if not self.agent:
            logger.error("[ERROR] Agent未初始化！")
            return None
        
        # 调用Agent
        try:
            recursion_limit = max(60, self.settings.harness.max_iterations * 20) if self.settings.harness.deep_thinking else 30
            
            result = self.agent.invoke(
                {
                    "messages": [{"role": "user", "content": query}],
                    "files": self.initial_files,
                },
                config={
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": recursion_limit,
                },
            )
        except Exception as e:
            if "Recursion limit" in str(e):
                logger.error("[ERROR] Agent陷入无限循环，已强制停止")
                return {
                    "status": "failed",
                    "message": "Agent执行超时：无法找到符合条件的股票。",
                    "error_type": "recursion_limit_exceeded",
                }
            raise
        
        if result is None:
            raise RuntimeError("Agent.invoke()返回None，LLM调用失败")
        
        execution_time_ms = (time.time() - start_time) * 1000
        logger.info(f"\n[OK] 查询完成 ({execution_time_ms:.0f}ms)")
        
        # 提取candidates
        result = CandidateExtractor.extract(result)
        
        # 处理结果（质量评估、重试、显示、保存脚本）
        result = self.result_processor.process_result(
            result=result,
            query=query,
            session=session,
            query_id=query_id,
            execution_time_ms=execution_time_ms,
        )
        
        # 记录遥测数据
        self.telemetry.record_query_result(
            query=query,
            success=(result.get("quality_evaluation", {}).get("candidate_count", 0) > 0),
            script_path=result.get("script_path"),
        )
        
        return result
