# Backtest Engine - 回测引擎

> 对生成的策略进行历史回测,评估策略有效性。

## 📖 概述

Backtest Engine 提供完整的策略回测功能,支持多持有期测试、收益计算和统计分析,帮助投资者验证策略的历史表现。

### 核心特性

- 📊 **多持有期回测**:同时测试多个持有周期 (默认: 4日/10日/20日)
- 💰 **收益计算**:年化收益率、胜率、最大回撤等关键指标
- 📈 **组合统计**:投资组合层面的聚合分析
- 📋 **可视化报告**:结构化回测结果展示
- 🔍 **持仓明细**:查看每只股票的详细收益情况

## 🏗️ 架构设计

```
┌─────────────────────────────────────┐
│   Strategy Scripts                  │
│  (screening_scripts/*.py)           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     BacktestEngine                   │
│  • 加载历史数据                      │
│  • 执行股票池过滤                     │
│  • 加载指数数据                       │
│  • 执行策略脚本                      │
│  • 计算持有期收益                    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     ReturnsCalculator                │
│  • 单股收益计算                      │
│  • 组合收益统计                      │
│  • 风险指标计算                      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     ReportGenerator                  │
│  • 生成回测报告                      │
│  • 格式化输出                        │
└─────────────────────────────────────┘
```

### 数据流程图

```python
# 1. 加载原始数据（Polars DataFrame）
engine.load_raw_data()  # -> engine.data (Polars)

# 2. 执行股票池过滤 + 加载指数数据
filtered_data, filtered_codes, index_data = stock_pool_service.apply_filter(engine.data)

# 3. 设置引擎数据
engine.data = filtered_data          # Polars DataFrame
engine.index_data = index_data       # Polars DataFrame (包含 index_code 列)

# 4. 执行策略（注入指数数据）
results = engine.run_directory(scripts_dir)

# 5. 计算收益（自动转换为 Pandas MultiIndex）
results_with_returns = engine.calculate_returns(results)
# ↓ 内部转换逻辑
if data is Polars:
    data_pd = data.to_pandas()
    data_pd = data_pd.set_index(['ts_code', 'trade_date'])
    data_for_returns = data_pd  # Pandas MultiIndex
```

**关键点**：
- ✅ `StockPoolService.apply_filter()` 同时返回过滤后的数据和指数数据
- ✅ 指数数据必须包含 `index_code` 列（用于 beta/alpha 等工具）
- ✅ `ReturnsCalculator` 需要 Pandas MultiIndex 格式，引擎会自动转换

## 📁 目录结构

```
src/backtest/
├── __init__.py                     # 模块入口
├── engine.py                       # 回测主引擎 BacktestEngine
├── returns.py                      # 收益计算器 ReturnsCalculator
├── report.py                       # 报告生成器 ReportGenerator
└── utils.py                        # 工具函数

app/backtest_results/               # 回测结果存储
└── ...
```

## 🔧 核心组件

### 1. BacktestEngine（回测主引擎）

协调整个回测流程。

**主要职责**：
- 加载原始市场数据（Polars DataFrame）
- 执行股票池过滤（通过 `StockPoolService`）
- 加载指数数据（包含 `index_code` 列）
- 动态注入指数数据到策略脚本
- 计算持有期收益（自动转换数据格式）
- 生成回测报告

**使用示例**：

```python
from src.backtest import BacktestEngine
from pathlib import Path

# 创建引擎
engine = BacktestEngine(
    screening_date="20260201",
    holding_periods=[5, 10, 20],
    observation_days=80
)

# 加载数据
if not engine.load_raw_data():
    print("❌ 数据加载失败")
    return

# 执行股票池过滤 + 加载指数数据
from src.agent.services.stock_pool_service import StockPoolService
stock_pool_service = StockPoolService(settings)
filtered_data, filtered_codes, index_data = stock_pool_service.apply_filter(engine.data)

# 设置引擎数据
engine.data = filtered_data
engine.index_data = index_data

# 执行策略
results = engine.run_directory(Path("app/screening_scripts/跑赢大盘"))

# 计算收益
results_with_returns = engine.calculate_returns(results)

# 生成报告
report = engine.generate_report(results_with_returns)
print_backtest_report(report)
```

### 2. ReturnsCalculator(收益计算器)

计算单股和组合收益。

**核心方法**:

- `calculate_returns()`: 计算单只股票在持有期的收益
- `calculate_portfolio_stats()`: 计算投资组合统计指标
- `get_stock_info()`: 获取股票基本信息

**使用示例**:

```python
from src.backtest import ReturnsCalculator

calculator = ReturnsCalculator()

# 计算单股收益
returns = calculator.calculate_returns(
    entry_price=10.5,
    exit_price=11.2,
    holding_days=10
)

print(f"收益率: {returns:.2%}")

# 计算组合统计
stats = calculator.calculate_portfolio_stats([
    {"return": 0.05, "ts_code": "000001.SZ"},
    {"return": -0.03, "ts_code": "000002.SZ"},
    {"return": 0.08, "ts_code": "000003.SZ"}
])

print(f"平均收益: {stats['mean_return']:.2%}")
print(f"胜率: {stats['win_rate']:.2%}")
print(f"夏普比率: {stats['sharpe_ratio']:.2f}")
```

### 3. ReportGenerator(报告生成器)

生成格式化的回测报告。

**使用示例**:

```python
from src.backtest import ReportGenerator

generator = ReportGenerator()

# 生成报告
report = generator.generate_report(results)

# 打印报告
print(report)
```

## 💡 使用示例

### 示例 1:基础回测

```python
from src.backtest import BacktestEngine
from pathlib import Path

engine = BacktestEngine()

results = engine.run_backtest(
    strategy_dir=Path("app/screening_scripts/放量突破"),
    holding_periods=[4, 10, 20]
)

# 打印报告
for result in results:
    print(f"\n策略: {result['strategy_name']}")
    print(f"{'='*60}")
    
    for period, stats in result['period_stats'].items():
        print(f"\n{period}日持有期:")
        print(f"  平均收益: {stats['mean_return']:.2%}")
        print(f"  胜率: {stats['win_rate']:.2%}")
        print(f"  最大收益: {stats['max_return']:.2%}")
        print(f"  最大亏损: {stats['min_return']:.2%}")
```

### 示例 2:自定义回测参数

```python
results = engine.run_backtest(
    strategy_dir=Path("app/screening_scripts/我的策略"),
    holding_periods=[5, 10, 15, 20],  
    observation_days=60,               
    start_date="20240101",             
    end_date="20241231"                
)
```

## ⚙️ 配置说明

```yaml
backtest:
  holding_periods: [4, 10, 20]  
  observation_days: 80           
  default_top_n: 20              
  enable_report: true            
  output_dir: "app/backtest_results"
```

## ⚠️ 注意事项

### 1. 指数数据加载

回测中使用 beta、alpha 等指数相关工具时，需要正确加载指数数据：

```python
# ✅ 正确：StockPoolService 会自动加载指数数据
filtered_data, filtered_codes, index_data = stock_pool_service.apply_filter(engine.data)
engine.index_data = index_data  # 包含 index_code 列

# ❌ 错误：不要丢弃指数数据
filtered_data, filtered_codes, _ = stock_pool_service.apply_filter(engine.data)
```

**指数数据格式要求**：
- 必须是 Polars DataFrame
- 必须包含 `index_code` 列
- 必须包含 `trade_date` 和 `close` 列

### 2. 数据格式转换

`ReturnsCalculator` 需要 Pandas MultiIndex 格式，引擎会自动转换：

```python
# 引擎内部自动处理
if hasattr(self.data, 'filter'):  # Polars DataFrame
    data_pd = self.data.to_pandas()
    data_pd = data_pd.set_index(['ts_code', 'trade_date'])
    data_for_returns = data_pd
```

**无需手动转换**，但如果自定义收益计算逻辑，需确保数据格式正确。

### 3. 筛选日期与数据范围

确保加载的数据覆盖筛选日期 + 最大持有期：

```python
# 引擎自动计算日期范围
end_date = screening_date + max(holding_periods) * 2  # 考虑非交易日
start_date = screening_date - (observation_days + 60)
```

如果数据不足，会看到警告：
```
⚠️ 数据不足：需要到 2026-03-01，实际只到 2026-02-28
建议：使用更早的筛选日期或更新数据
```

### 4. 脚本执行约束

**重要**：回测过程中**不允许修改策略脚本**，这些脚本已经过 `screener.py` 验证。

回测引擎通过动态注入的方式传递指数数据：
```python
# 引擎包装 screen_with_data 函数
def patched_screen_with_data(data, top_n=20, screening_date=None):
    screener = StockScreener(data, screening_date=screening_date, index_data=index_data)
    return screener.execute_screening(...)

module.screen_with_data = patched_screen_with_data
```

## 🧪 测试

```bash
pytest tests/src/backtest/ -v
```

## 🔗 相关文档

- [主 README](../README.md)
- [Screening Engine](./screening_engine.md)
- [Agent System](./agent_system.md)
