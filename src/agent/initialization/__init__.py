"""初始化模块 - 数据加载和组件初始化."""

# 注意：DataLoader 已移除，直接使用 StockPoolService 和 datahub loaders
from src.agent.initialization.component_initializer import ComponentInitializer

__all__ = ["ComponentInitializer"]
