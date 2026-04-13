"""智能任务分解器 - 将复杂筛选需求分解为多步骤子任务."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SubTask:
    """子任务."""
    
    id: int
    task_type: str  # screening/code_generation/validation
    description: str
    dependencies: list[int] = field(default_factory=list)
    status: str = "pending"  # pending/running/completed/failed
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "description": self.description,
            "dependencies": self.dependencies,
            "status": self.status,
        }


@dataclass
class TaskPlan:
    """任务计划."""
    
    tasks: list[SubTask]
    execution_order: list[int]  # 拓扑排序后的执行顺序
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "execution_order": self.execution_order,
            "total_tasks": len(self.tasks),
        }


class TaskPlanner:
    """任务规划器.
    
    功能：
    - 识别用户查询中的任务类型
    - 自动分解复杂查询为子任务
    - 分析任务依赖关系
    - 生成执行顺序（拓扑排序）
    
    支持的任务类型：
    - screening: 股票筛选
    - code_generation: 脚本生成
    - validation: 代码验证和优化
    """
    
    # 任务关键词模式
    TASK_PATTERNS = {
        "screening": {
            "keywords": [
                "找出", "筛选", "选择", "涨幅", "突破", "放量",
                "均线", "MACD", "RSI", "市盈率", "市净率",
                "成交量", "换手率", "市值", "行业",
            ],
            "title_template": "股票筛选：{context}",
        },
        "code_generation": {
            "keywords": [
                "生成", "创建", "编写", "脚本", "代码",
                "保存", "导出", "文件",
            ],
            "title_template": "脚本生成：{context}",
        },
        "validation": {
            "keywords": [
                "优化", "检查", "验证", "改进", "完善",
                "规范", "标准", "质量",
            ],
            "title_template": "代码验证：{context}",
        },
    }
    
    # 任务依赖规则
    TASK_DEPENDENCIES = {
        "code_generation": ["screening"],      # 脚本生成依赖筛选结果
        "validation": ["code_generation"],      # 验证依赖生成的代码
    }
    
    def decompose_query(self, query: str) -> TaskPlan:
        """将用户查询分解为子任务.
        
        Args:
            query: 用户查询
            
        Returns:
            任务计划
        """
        logger.info(f"🔍 开始分解查询：{query[:50]}...")
        
        # 1. 识别任务类型
        detected_tasks = self._detect_tasks(query)
        
        if not detected_tasks:
            # 如果没有检测到特定任务，默认为筛选任务
            logger.info("ℹ️  未检测到特定任务类型，使用默认筛选任务")
            detected_tasks = ["screening"]
        
        # 2. 创建子任务
        tasks = self._create_tasks(detected_tasks, query)
        
        # 3. 分析依赖关系
        self._analyze_dependencies(tasks)
        
        # 4. 拓扑排序
        execution_order = self._topological_sort(tasks)
        
        plan = TaskPlan(tasks=tasks, execution_order=execution_order)
        
        logger.info(f"✅ 任务分解完成：{len(tasks)} 个子任务")
        logger.info(f"   执行顺序：{execution_order}")
        
        return plan
    
    def _detect_tasks(self, query: str) -> list[str]:
        """检测查询中包含的任务类型.
        
        Args:
            query: 用户查询
            
        Returns:
            检测到的任务类型列表
        """
        detected = []
        
        for task_type, pattern in self.TASK_PATTERNS.items():
            if any(keyword in query for keyword in pattern["keywords"]):
                detected.append(task_type)
        
        return detected
    
    def _create_tasks(self, task_types: list[str], query: str) -> list[SubTask]:
        """创建子任务对象.
        
        Args:
            task_types: 任务类型列表
            query: 原始查询
            
        Returns:
            子任务列表
        """
        tasks = []
        task_id = 1
        
        for task_type in task_types:
            pattern = self.TASK_PATTERNS[task_type]
            title = pattern["title_template"].format(context=query[:30])
            
            task = SubTask(
                id=task_id,
                task_type=task_type,
                description=title,
            )
            tasks.append(task)
            task_id += 1
        
        return tasks
    
    def _analyze_dependencies(self, tasks: list[SubTask]):
        """分析任务依赖关系.
        
        Args:
            tasks: 子任务列表
        """
        for task in tasks:
            if task.task_type in self.TASK_DEPENDENCIES:
                required_deps = self.TASK_DEPENDENCIES[task.task_type]
                
                # 查找依赖任务
                for dep_type in required_deps:
                    for other_task in tasks:
                        if other_task.task_type == dep_type:
                            if other_task.id not in task.dependencies:
                                task.dependencies.append(other_task.id)
                                logger.debug(f"   添加依赖：任务 {task.id} 依赖任务 {other_task.id}")
    
    def _topological_sort(self, tasks: list[SubTask]) -> list[int]:
        """拓扑排序获取执行顺序.
        
        Args:
            tasks: 子任务列表
            
        Returns:
            执行顺序（任务ID列表）
        """
        # 构建邻接表
        graph = {task.id: [] for task in tasks}
        in_degree = {task.id: 0 for task in tasks}
        
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in graph:
                    graph[dep_id].append(task.id)
                    in_degree[task.id] += 1
        
        # Kahn 算法
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            # 按任务ID排序，确保确定性
            queue.sort()
            current = queue.pop(0)
            order.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否有环
        if len(order) != len(tasks):
            logger.warning("⚠️  检测到循环依赖，使用默认顺序")
            return [task.id for task in tasks]
        
        return order
    
    def is_simple_query(self, query: str) -> bool:
        """判断是否为简单查询（无需分解）.
        
        Args:
            query: 用户查询
            
        Returns:
            True 如果是简单查询
        """
        # 简单查询特征：
        # 1. 长度较短（< 30字符）
        # 2. 只包含一种任务类型
        # 3. 不包含连接词（然后、并且、同时）
        
        if len(query) < 30:
            return True
        
        connectors = ["然后", "并且", "同时", "再", "接着", "之后"]
        if any(connector in query for connector in connectors):
            return False
        
        detected_tasks = self._detect_tasks(query)
        return len(detected_tasks) <= 1
    
    def print_plan(self, plan: TaskPlan):
        """打印任务计划（用于调试）.
        
        Args:
            plan: 任务计划
        """
        logger.info("=" * 60)
        logger.info("📋 任务分解计划")
        logger.info("=" * 60)
        
        for task in plan.tasks:
            deps_str = f" (依赖: {task.dependencies})" if task.dependencies else ""
            logger.info(f"  [{task.id}] {task.task_type}: {task.description}{deps_str}")
        
        logger.info("-" * 60)
        logger.info(f"执行顺序：{' → '.join(str(tid) for tid in plan.execution_order)}")
        logger.info("=" * 60)


# 全局单例
_planner_instance: TaskPlanner | None = None


def get_planner() -> TaskPlanner:
    """获取全局任务规划器实例."""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = TaskPlanner()
    return _planner_instance


def reset_planner():
    """重置规划器实例（用于测试）."""
    global _planner_instance
    _planner_instance = None
