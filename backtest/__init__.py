"""
回测模块 - Backtest Module

本模块提供完整的回测功能，包括：
1. 筛选脚本加载器 (ScriptLoader)
2. 数据提供者 (DataProvider) 
3. 筛选执行器 (ScreeningExecutor)
4. 收益计算器 (ReturnCalculator)
5. 收益率计算 (calculate_holding_returns)

主要功能:
- 批量加载和执行筛选脚本
- 计算不同持有期的收益率
- 生成回测报告

使用示例:
```python
from backtest import DataProvider, ScreeningExecutor, ReturnCalculator

# 阶段 1: 数据加载 + 筛选
data_provider = DataProvider(screening_date="20260201", holding_periods=[4,10,20], observation_days=80)
if data_provider.load_data():
    screener = ScreeningExecutor(data_provider.data, data_provider.screening_date, data_provider.holding_periods)
    candidates = screener.execute_script(module, "test_strategy")
    
    # 阶段 2: 收益计算
    calculator = ReturnCalculator(data_provider.data, data_provider.holding_periods)
    returns = calculator.calculate_returns(candidates, "20260201")
```

配置:
日期范围通过 config.backtest_config.StockConfig 配置:
- BACKTEST_SCREENING_DATE: 筛选日期（以该交易日执行策略）
- BACKTEST_LOOKBACK_DAYS: 持有期列表

数据开始日期会自动计算：data_start_date = screening_date - max(LOOKBACK_DAYS)
"""

from backtest.backtest import (
    DataProvider,
    ScreeningExecutor,
    ReturnCalculator,
    BacktestResult,
    ScreeningResult,
    ScriptLoader,
    backtest_screening_scripts,
)

from backtest.returns import calculate_holding_returns

from datahub import load_market_data_for_backtest, get_available_industries

__all__ = [
    # 核心类
    "DataProvider",
    "ScreeningExecutor",
    "ReturnCalculator",
    "BacktestResult",
    "ScreeningResult",
    "ScriptLoader",
    
    # 函数
    "backtest_screening_scripts",
    "calculate_holding_returns",
    "load_market_data_for_backtest",
    "get_available_industries",
]
