"""查询执行器 - 负责执行用户查询."""

from __future__ import annotations

import time
from typing import Any

from infrastructure.logging.logger import get_logger
from infrastructure.session import SessionManager, QueryRecord
from infrastructure.telemetry import SimpleTelemetry
from src.agent.execution.planner import TaskPlanner
from utils.agent.result_checker import _is_screening_successful
from src.screening.script_saver import ScriptSaver
from src.screening.result_display import ResultDisplayer

logger = get_logger(__name__)


class QueryExecutor:
    """查询执行器 - 封装所有查询执行逻辑."""
    
    def __init__(
        self,
        agent,
        initial_files: dict,
        session_manager: SessionManager,
        telemetry: SimpleTelemetry,
        planner: TaskPlanner,
        quality_evaluator,
        settings: Any,
        hooks=None,  # HookExecutor 实例
    ):
        """初始化查询执行器.
        
        Args:
            agent: Agent 实例
            initial_files: 初始文件上下文
            session_manager: 会话管理器
            telemetry: 遥测系统
            planner: 任务规划器
            quality_evaluator: 质量评估器
            settings: 全局配置
            hooks: HookExecutor 实例（可选）
        """
        self.agent = agent
        self.initial_files = initial_files
        self.session_manager = session_manager
        self.telemetry = telemetry
        self.planner = planner
        self.quality_evaluator = quality_evaluator
        self.settings = settings
        self.hooks = hooks  # 保存 HookExecutor 实例
        
        # 工具类
        self.result_displayer = ResultDisplayer()
        self.script_saver: ScriptSaver | None = None
    
    def execute_query(self, query: str, query_id: int) -> dict[str, Any] | None:
        """执行单个查询.
        
        Args:
            query: 用户查询
            query_id: 查询ID
            
        Returns:
            查询结果或None
        """
        # 重置 run_screening 调用计数器（每个查询独立计数）
        from src.agent.tools import bridge
        bridge._run_screening_call_count = 0
        
        logger.info("=" * 60)
        logger.info(f"查询 {query_id}: {query}")
        logger.info("=" * 60)
        
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
                # 检查是否为复杂查询，需要任务分解
                is_complex = not self.planner.is_simple_query(query)
                
                if is_complex:
                    logger.info("🔍 检测到复杂查询，启动任务分解...")
                    result = self._execute_complex_query(query, query_id, thread_id, session)
                else:
                    # 简单查询，直接执行
                    result = self._execute_simple_query(query, query_id, thread_id, session)
                
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
            
            from infrastructure.errors.exceptions import AgentExecutionError
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
    
    def _execute_simple_query(
        self, 
        query: str, 
        query_id: int, 
        thread_id: str,
        session
    ) -> dict[str, Any] | None:
        """执行简单查询（原有逻辑）."""
        from infrastructure.config.settings import get_settings
        settings = get_settings()
        
        start_time = time.time()
        
        # 注意：Agent 应该在 orchestrator.execute_query() 中已经创建
        # 这里直接使用 self.agent，不应该再次创建
        if not self.agent:
            logger.error("❌ Agent 未初始化！这不应该发生，请检查 orchestrator 的初始化逻辑")
            return None
        
        # 直接调用 Agent
        result = self.agent.invoke(
            {
                "messages": [{"role": "user", "content": query}],
                "files": self.initial_files,
            },
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 50,
            },
        )
        
        execution_time_ms = (time.time() - start_time) * 1000
        logger.info(f"\n✅ 查询完成 ({execution_time_ms:.0f}ms)")
        
        # Stop Hook: 质量门禁（使用 orchestrator 传入的 hooks）
        if self.hooks:
            hook_result = self.hooks.execute_stop({"result": result, "query": query})
            
            if hook_result.is_blocked:
                logger.warning(f"⚠️ Stop Hook阻止了结果返回: {hook_result.message}")
                result["hook_feedback"] = hook_result.message
        
        # 质量评估反馈循环
        quality_result = self.quality_evaluator.evaluate(query, result)
        result["quality_evaluation"] = quality_result
        
        # 如果质量问题严重，自动触发重试
        if quality_result.get("should_retry", False):
            logger.warning(f"\n⚠️ 检测到质量问题，尝试自动优化...")
            logger.info(f"   问题：{', '.join(quality_result['issues'][:3])}")
            
            # 记录详细的失败诊断信息
            self._log_screening_failure_details(result, quality_result)
            
            retry_result = self._retry_with_quality_feedback(
                query, thread_id, result, quality_result, session
            )
            if retry_result:
                result = retry_result
                logger.info("✅ 自动优化完成")
        
        # 显示结果
        self.result_displayer.display(result)
        
        # 保存脚本（根据配置决定是否询问）
        script_path = None
        if _is_screening_successful(result):
            # 初始化脚本保存器（如果尚未初始化）
            if self.script_saver is None:
                from src.agent.tools.bridge import create_bridge_tools
                from infrastructure.config.settings import get_settings
                settings = get_settings()
                
                # 创建 bridge tools
                def get_data():
                    return self.data if hasattr(self, 'data') else None
                
                bridge_tools = create_bridge_tools(
                    data_fn=get_data,
                    scripts_dir=str(settings.output.strategies_dir),
                    stock_codes=None
                )
                
                self.script_saver = ScriptSaver(
                    bridge_tools,
                    auto_save=settings.output.auto_save_script
                )
            save_result = self.script_saver.handle_save(result, query)
            if save_result:
                script_path = save_result.get("script_path")
        
        # 更新查询记录
        candidates_count = len(result.get("candidates", []))
        status = "success" if _is_screening_successful(result) else "failed"
        
        session.update_query_status(
            query_id=query_id,
            status=status,
            script_path=script_path,
            candidates_count=candidates_count,
            execution_time_ms=execution_time_ms,
        )
        
        # 记录遥测数据
        self.telemetry.record_query_result(
            query=query,
            success=(status == "success"),
            script_path=script_path,
        )
        
        session.save()
        return result
    
    def _execute_complex_query(
        self,
        query: str,
        query_id: int,
        thread_id: str,
        session
    ) -> dict[str, Any] | None:
        """执行复杂查询（使用任务分解）."""
        start_time = time.time()
        
        # 1. 分解任务
        plan = self.planner.decompose_query(query)
        self.planner.print_plan(plan)
        
        # 2. 按顺序执行子任务
        context = {
            "original_query": query,
            "subtask_results": [],
            "files": self.initial_files,
        }
        
        for task_id in plan.execution_order:
            task = next(t for t in plan.tasks if t.id == task_id)
            logger.info(f"\n{'='*60}")
            logger.info(f"▶️  执行子任务 {task.id}/{len(plan.tasks)}: {task.task_type}")
            logger.info(f"   描述：{task.description}")
            logger.info(f"{'='*60}")
            
            task.status = "running"
            
            try:
                # 确保 Agent 已创建
                if not self.agent:
                    from src.agent.core.agent_factory import create_screener_agent
                    from infrastructure.config.settings import get_settings
                    settings = get_settings()
                    self.agent, self.initial_files = create_screener_agent(
                        llm=None,
                        tool_provider=None,
                        skill_registry=None,
                        long_term_memory=None,
                        skills_dir=None,
                        deep_thinking=settings.harness.deep_thinking,
                        max_iterations=settings.harness.max_iterations,
                    )
                
                # 构建子任务消息
                subtask_message = self._build_subtask_message(task, context)
                
                # 执行子任务
                subtask_result = self.agent.invoke(
                    {
                        "messages": [{"role": "user", "content": subtask_message}],
                        "files": context["files"],
                    },
                    config={
                        "configurable": {"thread_id": f"{thread_id}-task-{task_id}"},
                        "recursion_limit": 50,
                    },
                )
                
                # 保存子任务结果
                context["subtask_results"].append({
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "result": subtask_result,
                })
                
                task.status = "completed"
                logger.info(f"✅ 子任务 {task_id} 完成")
                
            except Exception as e:
                logger.exception(f"❌ 子任务 {task_id} 失败：{e}")
                task.status = "failed"
                task.error_message = str(e)
        
        # 3. 聚合结果
        execution_time_ms = (time.time() - start_time) * 1000
        result = self._aggregate_subtask_results(context, plan)
        
        # 4. 保存会话
        session.update_query_status(
            query_id=query_id,
            status="success",
            execution_time_ms=execution_time_ms,
        )
        session.save()
        
        return result
    
    def _build_subtask_message(self, task, context: dict) -> str:
        """构建子任务消息."""
        message_parts = [
            f"任务类型：{task.task_type}",
            f"任务描述：{task.description}",
            f"\n原始查询：{context['original_query']}",
        ]
        
        # 如果有前置任务结果，添加到上下文中
        if context.get("subtask_results"):
            message_parts.append("\n前置任务结果：")
            for prev_result in context["subtask_results"]:
                message_parts.append(f"- {prev_result['task_type']}: {str(prev_result['result'])[:200]}")
        
        message_parts.append("\n请执行上述任务。")
        
        return "\n".join(message_parts)
    
    def _aggregate_subtask_results(self, context: dict, plan) -> dict[str, Any]:
        """聚合子任务结果为最终结果."""
        # 以最后一个成功的 screening 或 code_generation 任务的结果为主
        final_result = {
            "candidates": context.get("screening_candidates", []),
            "script_code": context.get("screening_code", ""),
            "subtask_summary": {
                "total_tasks": len(plan.tasks),
                "completed_tasks": sum(1 for t in plan.tasks if t.status == "completed"),
                "failed_tasks": sum(1 for t in plan.tasks if t.status == "failed"),
            },
        }
        
        # 如果有 validation 任务，合并其优化建议
        for subtask in context.get("subtask_results", []):
            if subtask["task_type"] == "validation" and "result" in subtask:
                validation_result = subtask["result"]
                if isinstance(validation_result, dict):
                    final_result["validation_feedback"] = validation_result
        
        return final_result
    
    def _extract_screening_logic_summary(self, result: dict) -> str | None:
        """从结果中提取筛选逻辑摘要（用于排查问题）.
        
        Args:
            result: Agent 执行结果
            
        Returns:
            筛选逻辑摘要字符串，或 None
        """
        try:
            messages = result.get("messages", [])
            for message in reversed(messages):
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if tool_call.get("name") == "run_screening":
                            args = tool_call.get("args", {})
                            if "screening_logic_json" in args:
                                import json
                                logic = json.loads(args["screening_logic_json"])
                                tools_count = len(logic.get("tools", []))
                                expression = logic.get("expression", "")[:100]
                                return f"tools={tools_count}个步骤, expression={expression}"
            return None
        except Exception as e:
            logger.debug(f"提取筛选逻辑摘要失败: {e}")
            return None
    
    def _log_screening_failure_details(self, result: dict, quality_result: dict):
        """记录筛选失败的详细信息（用于诊断）.
        
        Args:
            result: Agent 执行结果
            quality_result: 质量评估结果
        """
        candidate_count = quality_result.get("candidate_count", 0)
        if candidate_count != 0:
            return  # 只在结果为空时输出详细诊断
        
        logger.error(f"\n❌ 筛选失败详细诊断：")
        
        # 提取筛选逻辑
        screening_logic_summary = self._extract_screening_logic_summary(result)
        if screening_logic_summary:
            logger.error(f"   筛选逻辑：{screening_logic_summary}")
        else:
            logger.error(f"   ⚠️ 未能提取筛选逻辑（Agent 可能未调用工具）")
        
        # 检查是否有工具调用
        messages = result.get("messages", [])
        has_tool_call = False
        for message in messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.get("name") == "run_screening":
                        has_tool_call = True
                        break
        
        if not has_tool_call:
            logger.error(f"   ⚠️ Agent 未调用 run_screening 工具")
            logger.error(f"   可能原因：")
            logger.error(f"      1. Agent 理解错了任务意图")
            logger.error(f"      2. System prompt 不够清晰")
            logger.error(f"      3. 工具注册有问题")
    
    def _retry_with_quality_feedback(
        self,
        query: str,
        thread_id: str,
        original_result: dict,
        quality_result: dict,
        session
    ) -> dict | None:
        """基于质量评估反馈进行自动重试.
        
        Args:
            query: 原始查询
            thread_id: 线程ID
            original_result: 原始结果
            quality_result: 质量评估结果
            session: 会话对象
            
        Returns:
            优化后的结果，或 None（如果重试失败）
        """
        # 使用配置中的 max_iterations（减去1，因为已经执行了1次）
        max_retries = max(0, self.settings.harness.max_iterations - 1)
        
        for retry_attempt in range(1, max_retries + 1):
            logger.info(f"\n🔄 第 {retry_attempt} 次自动优化...")
            
            # 构建优化提示
            issues = quality_result.get("issues", [])
            suggestions = quality_result.get("suggestions", [])
            
            # 根据重试次数调整优化策略
            if retry_attempt == 1:
                # 第一次重试：大幅放宽条件
                optimization_strategy = """
【优化策略】
请大幅放宽筛选条件：
1. 降低技术指标阈值（如成交量倍数从 1.5 降到 1.2）
2. 减少约束条件数量（保留最核心的 2-3 个条件）
3. 扩大行业或板块范围
4. 降低涨幅要求（如从 3% 降到 1%）
"""
            else:
                # 后续重试：继续优化
                optimization_strategy = """
【优化策略】
请进一步优化筛选条件，尝试不同的技术指标组合。
"""
            
            optimization_prompt = f"""
请根据以下质量问题优化之前的结果：

【发现的问题】
{chr(10).join(f'- {issue}' for issue in issues[:5])}

【改进建议】
{chr(10).join(f'- {suggestion}' for suggestion in suggestions[:5])}

{optimization_strategy}

请重新生成优化后的结果。
"""
            
            try:
                # 调用 Agent 进行优化
                retry_result = self.agent.invoke(
                    {
                        "messages": [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": str(original_result)},
                            {"role": "user", "content": optimization_prompt},
                        ],
                        "files": self.initial_files,
                    },
                    config={
                        "configurable": {"thread_id": f"{thread_id}-retry-{retry_attempt}"},
                        "recursion_limit": 50,
                    },
                )
                
                # 重新评估质量
                new_quality = self.quality_evaluator.evaluate(query, retry_result)
                retry_result["quality_evaluation"] = new_quality
                
                # 如果质量改善，返回新结果
                if not new_quality.get("should_retry", False):
                    logger.info(f"✅ 第 {retry_attempt} 次优化成功，质量问题已解决")
                    
                    # 记录到会话
                    session.add_message(
                        "assistant",
                        f"自动优化完成（第{retry_attempt}次重试）",
                        retry_attempt=retry_attempt,
                        old_issues=len(issues),
                        new_issues=len(new_quality.get("issues", [])),
                    )
                    
                    return retry_result
                else:
                    new_issues = new_quality.get("issues", [])
                    logger.warning(f"⚠️ 第 {retry_attempt} 次优化后仍有质量问题，继续尝试...")
                    logger.warning(f"   剩余问题 ({len(new_issues)} 个)：")
                    for i, issue in enumerate(new_issues[:5], 1):
                        logger.warning(f"      {i}. {issue}")
                    if len(new_issues) > 5:
                        logger.warning(f"      ... 还有 {len(new_issues) - 5} 个问题")
                    quality_result = new_quality
            
            except Exception as e:
                logger.error(f"❌ 第 {retry_attempt} 次优化失败：{e}")
                continue
        
        logger.warning(f"⚠️ 经过 {max_retries} 次优化仍未能完全解决问题，使用最佳结果")
        final_issues = quality_result.get("issues", [])
        if final_issues:
            logger.warning(f"   最终遗留问题 ({len(final_issues)} 个)：")
            for i, issue in enumerate(final_issues[:5], 1):
                logger.warning(f"      {i}. {issue}")
            if len(final_issues) > 5:
                logger.warning(f"      ... 还有 {len(final_issues) - 5} 个问题")
        return None
