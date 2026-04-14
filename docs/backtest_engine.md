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

### 1. BacktestEngine(回测主引擎)

协调整个回测流程。

**使用示例**:

```python
from src.backtest import BacktestEngine
from pathlib import Path

engine = BacktestEngine()

# 回测指定目录下的所有策略
results = engine.run_backtest(
    strategy_dir=Path("app/screening_scripts/放量突破"),
    holding_periods=[4, 10, 20],
    observation_days=80
)

# 查看结果
for result in results:
    print(f"策略: {result['strategy_name']}")
    print(f"平均收益: {result['avg_return']:.2%}")
    print(f"胜率: {result['win_rate']:.2%}")
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

## 🧪 测试

```bash
pytest tests/src/backtest/ -v
```

## 🔗 相关文档

- [主 README](../README.md)
- [Screening Engine](./screening_engine.md)
- [Agent System](./agent_system.md)
