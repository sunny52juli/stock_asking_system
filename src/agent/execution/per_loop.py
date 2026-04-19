"""Plan-Execute-Reflect 循环 - 智能任务执行与反思."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

from infrastructure.logging.logger import get_logger
from src.agent.execution.planner import TaskPlan, SubTask

import time
logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """执行结果."""
    
    task_id: int
    success: bool
    output: Any = None
    error: str | None = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": str(self.output) if self.output else None,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class Reflection:
    """反思结果."""
    
    task_id: int
    quality_score: float  # 0-1
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    needs_revision: bool = False
    revision_plan: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "quality_score": self.quality_score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "needs_revision": self.needs_revision,
            "revision_plan": self.revision_plan,
        }


class PlanExecuteReflectLoop:
    """Plan-Execute-Reflect 循环控制器.
    
    工作流程：
    1. Plan: 分解任务为子任务
    2. Execute: 按依赖顺序执行子任务
    3. Reflect: 评估执行结果质量
    4. Revise: 如果需要，重新规划并执行
    
    特性：
    - 自动重试失败的任务
    - 质量驱动的反思机制
    - 增量式改进
    - 完整的执行轨迹记录
    """
    
    def __init__(self, max_iterations: int = 3, quality_threshold: float = 0.7):
        """初始化循环控制器.
        
        Args:
            max_iterations: 最大迭代次数
            quality_threshold: 质量阈值（低于此值触发反思）
        """
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.execution_history: list[dict[str, Any]] = []
    
    def run(self, plan: TaskPlan, executor_func, reflect_func) -> dict[str, Any]:
        """执行完整的 Plan-Execute-Reflect 循环.
        
        Args:
            plan: 任务计划
            executor_func: 执行函数 (task_id, task) -> ExecutionResult
            reflect_func: 反思函数 (task_id, result) -> Reflection
            
        Returns:
            最终执行结果汇总
        """
        logger.info("=" * 60)
        logger.info("🚀 启动 Plan-Execute-Reflect 循环")
        logger.info(f"   任务数: {len(plan.tasks)}")
        logger.info(f"   最大迭代: {self.max_iterations}")
        logger.info(f"   质量阈值: {self.quality_threshold}")
        logger.info("=" * 60)
        
        iteration = 0
        final_results: dict[int, ExecutionResult] = {}
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"\n{'=' * 60}")
            logger.info(f"📊 迭代 {iteration}/{self.max_iterations}")
            logger.info(f"{'=' * 60}")
            
            # Phase 1: Execute
            results = self._execute_plan(plan, executor_func, iteration)
            final_results.update(results)
            
            # Phase 2: Reflect
            reflections = self._reflect_on_results(results, reflect_func)
            
            # Phase 3: Check if revision needed
            needs_revision = any(r.needs_revision for r in reflections.values())
            
            if not needs_revision:
                logger.info("\n✅ 所有任务达到质量标准，无需修订")
                break
            
            # Phase 4: Revise plan
            logger.info("\n🔄 检测到需要修订的任务，调整计划...")
            plan = self._revise_plan(plan, reflections, results)
            
            if not plan.tasks:
                logger.info("⚠️  修订后无任务可执行，退出循环")
                break
        
        # Generate final summary
        summary = self._generate_summary(final_results, reflections, iteration)
        
        logger.info(f"\n{'=' * 60}")
        logger.info("✅ Plan-Execute-Reflect 循环完成")
        logger.info(f"   总迭代: {iteration}")
        logger.info(f"   成功任务: {sum(1 for r in final_results.values() if r.success)}")
        logger.info(f"   平均质量: {summary.get('avg_quality', 0):.2f}")
        logger.info(f"{'=' * 60}")
        
        return summary
    
    def _execute_plan(
        self, 
        plan: TaskPlan, 
        executor_func,
        iteration: int
    ) -> dict[int, ExecutionResult]:
        """执行任务计划.
        
        Args:
            plan: 任务计划
            executor_func: 执行函数
            iteration: 当前迭代次数
            
        Returns:
            执行结果字典 {task_id: ExecutionResult}
        """
        results: dict[int, ExecutionResult] = {}
        
        for task_id in plan.execution_order:
            task = next((t for t in plan.tasks if t.id == task_id), None)
            if not task:
                continue
            
            # Check dependencies
            if not self._dependencies_met(task, results):
                logger.warning(f"⚠️  任务 {task_id} 的依赖未满足，跳过")
                results[task_id] = ExecutionResult(
                    task_id=task_id,
                    success=False,
                    error="Dependencies not met",
                )
                continue
            
            logger.info(f"\n▶️  执行任务 {task_id}: {task.description}")
            task.status = "running"
            
            try:
                start_time = time.time()
                
                result = executor_func(task_id, task)
                
                elapsed = time.time() - start_time
                result.execution_time = elapsed
                
                results[task_id] = result
                task.status = "completed" if result.success else "failed"
                
                status_icon = "✅" if result.success else "❌"
                logger.info(f"{status_icon} 任务 {task_id} 完成 (耗时: {elapsed:.2f}s)")
                
            except Exception as e:
                logger.exception(f"❌ 任务 {task_id} 执行异常: {e}")
                results[task_id] = ExecutionResult(
                    task_id=task_id,
                    success=False,
                    error=str(e),
                )
                task.status = "failed"
        
        return results
    
    def _reflect_on_results(
        self,
        results: dict[int, ExecutionResult],
        reflect_func
    ) -> dict[int, Reflection]:
        """反思执行结果.
        
        Args:
            results: 执行结果
            reflect_func: 反思函数
            
        Returns:
            反思结果字典 {task_id: Reflection}
        """
        logger.info("\n💭 开始反思执行结果...")
        
        reflections: dict[int, Reflection] = {}
        
        for task_id, result in results.items():
            if not result.success:
                # 失败的任务自动标记为需要修订
                reflections[task_id] = Reflection(
                    task_id=task_id,
                    quality_score=0.0,
                    issues=[f"Execution failed: {result.error}"],
                    suggestions=["Retry with adjusted parameters"],
                    needs_revision=True,
                    revision_plan=f"Fix error and retry: {result.error}",
                )
                continue
            
            try:
                reflection = reflect_func(task_id, result)
                reflections[task_id] = reflection
                
                quality_icon = "✅" if reflection.quality_score >= self.quality_threshold else "⚠️"
                logger.info(
                    f"  {quality_icon} 任务 {task_id}: 质量={reflection.quality_score:.2f}"
                )
                
                if reflection.needs_revision:
                    logger.info(f"     问题: {reflection.issues[:2]}")
                    logger.info(f"     建议: {reflection.suggestions[:2]}")
                    
            except Exception as e:
                logger.warning(f"⚠️  任务 {task_id} 反思失败: {e}")
                reflections[task_id] = Reflection(
                    task_id=task_id,
                    quality_score=0.5,
                    issues=[f"Reflection failed: {str(e)}"],
                    needs_revision=False,
                )
        
        return reflections
    
    def _revise_plan(
        self,
        plan: TaskPlan,
        reflections: dict[int, Reflection],
        results: dict[int, ExecutionResult]
    ) -> TaskPlan:
        """修订任务计划.
        
        Args:
            plan: 原计划
            reflections: 反思结果
            results: 执行结果
            
        Returns:
            修订后的计划
        """
        # 找出需要修订的任务
        tasks_to_revise = [
            task_id for task_id, ref in reflections.items()
            if ref.needs_revision
        ]
        
        if not tasks_to_revise:
            return plan
        
        logger.info(f"📝 需要修订的任务: {tasks_to_revise}")
        
        # 创建新的子任务（基于修订计划）
        revised_tasks = []
        new_task_id = max(t.id for t in plan.tasks) + 1
        
        for task_id in tasks_to_revise:
            original_task = next((t for t in plan.tasks if t.id == task_id), None)
            if not original_task:
                continue
            
            reflection = reflections[task_id]
            
            # 创建修订任务
            revised_task = SubTask(
                id=new_task_id,
                task_type=original_task.task_type,
                description=f"[修订] {original_task.description}\n原因: {reflection.revision_plan}",
                dependencies=original_task.dependencies.copy(),
            )
            revised_tasks.append(revised_task)
            new_task_id += 1
        
        # 更新执行顺序
        new_execution_order = [t.id for t in revised_tasks]
        
        revised_plan = TaskPlan(
            tasks=revised_tasks,
            execution_order=new_execution_order,
        )
        
        logger.info(f"✅ 修订计划创建完成: {len(revised_tasks)} 个新任务")
        
        return revised_plan
    
    def _dependencies_met(
        self, 
        task: SubTask, 
        results: dict[int, ExecutionResult]
    ) -> bool:
        """检查任务依赖是否满足.
        
        Args:
            task: 任务
            results: 已执行结果
            
        Returns:
            True 如果所有依赖都成功完成
        """
        for dep_id in task.dependencies:
            if dep_id not in results:
                return False
            if not results[dep_id].success:
                return False
        return True
    
    def _generate_summary(
        self,
        results: dict[int, ExecutionResult],
        reflections: dict[int, Reflection],
        total_iterations: int
    ) -> dict[str, Any]:
        """生成执行摘要.
        
        Args:
            results: 执行结果
            reflections: 反思结果
            total_iterations: 总迭代次数
            
        Returns:
            摘要字典
        """
        successful = sum(1 for r in results.values() if r.success)
        total = len(results)
        
        quality_scores = [r.quality_score for r in reflections.values()]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        total_time = sum(r.execution_time for r in results.values())
        
        summary = {
            "total_tasks": total,
            "successful_tasks": successful,
            "failed_tasks": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_quality": avg_quality,
            "total_iterations": total_iterations,
            "total_execution_time": total_time,
            "results": {tid: r.to_dict() for tid, r in results.items()},
            "reflections": {tid: r.to_dict() for tid, r in reflections.items()},
            "timestamp": datetime.now().isoformat(),
        }
        
        # 记录到历史
        self.execution_history.append(summary)
        
        return summary
    
    def get_history(self) -> list[dict[str, Any]]:
        """获取执行历史."""
        return self.execution_history.copy()


# 全局单例
_loop_instance: PlanExecuteReflectLoop | None = None


def get_per_loop(max_iterations: int = 3, quality_threshold: float = 0.7) -> PlanExecuteReflectLoop:
    """获取全局 PER 循环实例."""
    global _loop_instance
    if _loop_instance is None:
        _loop_instance = PlanExecuteReflectLoop(
            max_iterations=max_iterations,
            quality_threshold=quality_threshold,
        )
    return _loop_instance


def reset_per_loop():
    """重置 PER 循环实例（用于测试）."""
    global _loop_instance
    _loop_instance = None
