#!/usr/bin/env python3
"""验证重构后的导入是否正确."""

import sys
from pathlib import Path

# 添加项目根目录到路径
from src.agent import ScreenerOrchestrator
from src.agent import create_screener_agent
from src.agent.config import AgentConfig
from src.agent.core.agent_factory import create_screener_agent
from src.agent.core.orchestrator import ScreenerOrchestrator
from src.agent.core.subagent import SubAgent
from src.agent.execution.agent_phases import execute_query_with_reflection
from src.agent.execution.planner import TaskPlanner, get_planner
from src.agent.execution.query_executor import QueryExecutor
from src.agent.initialization.component_initializer import ComponentInitializer
from src.agent.initialization.data_loader import DataLoader
from src.agent.quality.quality_evaluator import ScreeningQualityEvaluator
from src.agent.quality.retry_manager import RetryManager, get_retry_manager
project_root = Path(r"D:\code\QuantitativeSystem\stock_asking_system")
sys.path.insert(0, str(project_root))

print("=" * 60)
print("验证 Agent 模块重构后的导入")
print("=" * 60)
print()

# 测试核心编排层
try:
    print("✅ src.agent.src.orchestrator.ScreenerOrchestrator")
except ImportError as e:
    print(f"❌ src.agent.src.orchestrator.ScreenerOrchestrator: {e}")

try:
    print("✅ src.agent.src.agent_factory.create_screener_agent")
except ImportError as e:
    print(f"❌ src.agent.src.agent_factory.create_screener_agent: {e}")

try:
    print("✅ src.agent.src.subagent.SubAgent")
except ImportError as e:
    print(f"❌ src.agent.src.subagent.SubAgent: {e}")

print()

# 测试初始化模块
try:
    print("✅ src.agent.initialization.data_loader.DataLoader")
except ImportError as e:
    print(f"❌ src.agent.initialization.data_loader.DataLoader: {e}")

try:
    print("✅ src.agent.initialization.component_initializer.ComponentInitializer")
except ImportError as e:
    print(f"❌ src.agent.initialization.component_initializer.ComponentInitializer: {e}")

print()

# 测试执行层
try:
    print("✅ src.agent.execution.query_executor.QueryExecutor")
except ImportError as e:
    print(f"❌ src.agent.execution.query_executor.QueryExecutor: {e}")

try:
    print("✅ src.agent.execution.planner.TaskPlanner, get_planner")
except ImportError as e:
    print(f"❌ src.agent.execution.planner: {e}")

try:
    print("✅ src.agent.execution.agent_phases.execute_query_with_reflection")
except ImportError as e:
    print(f"❌ src.agent.execution.agent_phases.execute_query_with_reflection: {e}")

print()

# 测试质量管理
try:
    print("✅ src.agent.quality.quality_evaluator.ScreeningQualityEvaluator")
except ImportError as e:
    print(f"❌ src.agent.quality.quality_evaluator.ScreeningQualityEvaluator: {e}")

try:
    print("✅ src.agent.quality.retry_manager.RetryManager, get_retry_manager")
except ImportError as e:
    print(f"❌ src.agent.quality.retry_manager.RetryManager, get_retry_manager: {e}")

print()

# 测试顶层导出
try:
    print("✅ src.agent.ScreenerOrchestrator (顶层导出)")
except ImportError as e:
    print(f"❌ src.agent.ScreenerOrchestrator: {e}")

try:
    print("✅ src.agent.create_screener_agent (顶层导出)")
except ImportError as e:
    print(f"❌ src.agent.create_screener_agent: {e}")

print()

# 测试 config（未移动）
try:
    print("✅ src.agent.config.AgentConfig (未移动)")
except ImportError as e:
    print(f"❌ src.agent.config.AgentConfig: {e}")

print()
print("=" * 60)
print("验证完成！")
print("=" * 60)
