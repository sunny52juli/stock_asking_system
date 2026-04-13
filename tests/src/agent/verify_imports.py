#!/usr/bin/env python3
"""验证重构后的导入是否正确."""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(r"D:\code\QuantitativeSystem\stock_asking_system")
sys.path.insert(0, str(project_root))

print("=" * 60)
print("验证 Agent 模块重构后的导入")
print("=" * 60)
print()

# 测试核心编排层
try:
    from src.agent.core.orchestrator import ScreenerOrchestrator
    print("✅ src.agent.src.orchestrator.ScreenerOrchestrator")
except ImportError as e:
    print(f"❌ src.agent.src.orchestrator.ScreenerOrchestrator: {e}")

try:
    from src.agent.core.agent_factory import create_screener_agent
    print("✅ src.agent.src.agent_factory.create_screener_agent")
except ImportError as e:
    print(f"❌ src.agent.src.agent_factory.create_screener_agent: {e}")

try:
    from src.agent.core.subagent import SubAgent
    print("✅ src.agent.src.subagent.SubAgent")
except ImportError as e:
    print(f"❌ src.agent.src.subagent.SubAgent: {e}")

print()

# 测试初始化模块
try:
    from src.agent.initialization.data_loader import DataLoader
    print("✅ src.agent.initialization.data_loader.DataLoader")
except ImportError as e:
    print(f"❌ src.agent.initialization.data_loader.DataLoader: {e}")

try:
    from src.agent.initialization.component_initializer import ComponentInitializer
    print("✅ src.agent.initialization.component_initializer.ComponentInitializer")
except ImportError as e:
    print(f"❌ src.agent.initialization.component_initializer.ComponentInitializer: {e}")

print()

# 测试执行层
try:
    from src.agent.execution.query_executor import QueryExecutor
    print("✅ src.agent.execution.query_executor.QueryExecutor")
except ImportError as e:
    print(f"❌ src.agent.execution.query_executor.QueryExecutor: {e}")

try:
    from src.agent.execution.planner import TaskPlanner, get_planner
    print("✅ src.agent.execution.planner.TaskPlanner, get_planner")
except ImportError as e:
    print(f"❌ src.agent.execution.planner: {e}")

try:
    from src.agent.execution.agent_phases import execute_query_with_reflection
    print("✅ src.agent.execution.agent_phases.execute_query_with_reflection")
except ImportError as e:
    print(f"❌ src.agent.execution.agent_phases.execute_query_with_reflection: {e}")

print()

# 测试质量管理
try:
    from src.agent.quality.quality_evaluator import ScreeningQualityEvaluator
    print("✅ src.agent.quality.quality_evaluator.ScreeningQualityEvaluator")
except ImportError as e:
    print(f"❌ src.agent.quality.quality_evaluator.ScreeningQualityEvaluator: {e}")

try:
    from src.agent.quality.retry_manager import RetryManager, get_retry_manager
    print("✅ src.agent.quality.retry_manager.RetryManager, get_retry_manager")
except ImportError as e:
    print(f"❌ src.agent.quality.retry_manager.RetryManager, get_retry_manager: {e}")

print()

# 测试顶层导出
try:
    from src.agent import ScreenerOrchestrator
    print("✅ src.agent.ScreenerOrchestrator (顶层导出)")
except ImportError as e:
    print(f"❌ src.agent.ScreenerOrchestrator: {e}")

try:
    from src.agent import create_screener_agent
    print("✅ src.agent.create_screener_agent (顶层导出)")
except ImportError as e:
    print(f"❌ src.agent.create_screener_agent: {e}")

print()

# 测试 config（未移动）
try:
    from src.agent.config import AgentConfig
    print("✅ src.agent.config.AgentConfig (未移动)")
except ImportError as e:
    print(f"❌ src.agent.config.AgentConfig: {e}")

print()
print("=" * 60)
print("验证完成！")
print("=" * 60)
