# Screening Engine - 股票筛选引擎

> 高效执行股票筛选逻辑,支持动态指标计算和多条件过滤。

## 📖 概述

Screening Engine 是系统的核心执行引擎,负责将 Agent 生成的筛选逻辑转化为实际的股票筛选操作。它采用向量化批量计算技术,能够在秒级时间内完成数千只股票的复杂指标计算和筛选。

### 核心特性

- ⚡ **高性能**:向量化批量计算,秒级处理数千只股票
- 🎯 **智能预筛选**:基于股票池规则快速过滤无效股票
- 🔧 **动态指标**:支持任意技术指标和自定义因子计算
- 📊 **多条件过滤**:支持复杂的布尔表达式和置信度排序
- 💾 **脚本生成**:自动生成可复用的 Python 筛选脚本
- 🏭 **行业匹配**:模糊匹配引擎,支持自然语言行业查询

## 🏗️ 架构设计

```
┌─────────────────────────────────────┐
│   Screening Logic (from Agent)      │
│  • expression: 筛选表达式            │
│  • tools: 指标计算工具列表           │
│  • confidence: 置信度公式            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     PreFilterEngine                 │
│  • 排除 ST 股票                      │
│  • 排除停牌股票                      │
│  • 上市天数过滤                      │
│  • 行业过滤                          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     BatchCalculator                  │
│  • 向量化计算技术指标                 │
│  • 并行处理多只股票                   │
│  • 缓存中间结果                       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     FilterEngine                     │
│  • 执行布尔表达式                    │
│  • 计算置信度                        │
│  • Top-N 排序                        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     ScriptSaver                      │
│  • 生成 Python 脚本                  │
│  • 保存到 screening_scripts/         │
└─────────────────────────────────────┘
```

## 📁 目录结构

```
src/screening/
├── __init__.py                     
├── executor.py                     # 筛选执行器 StockScreener
├── prefilter.py                    # 预筛选引擎 PreFilterEngine
├── batch_calculator.py             # 批量计算器 BatchCalculator
├── industry_matcher.py             # 行业匹配器 IndustryMatcher
└── script_saver.py                 # 脚本保存器 ScriptSaver

utils/screening/
├── __init__.py
├── stock_screener.py               # 股票筛选器
├── result_display.py               # 结果显示工具
└── indicators.py                   # 技术指标计算

app/screening_scripts/              # 生成的筛选脚本
└── 放量突破/
    ├── 放量突破_20260413_235007.py
    └── 放量突破_20260414_002658.py
```

## 🔧 核心组件

### 1. StockScreener(股票筛选器)

主入口类,协调整个筛选流程。

**使用示例**:

```python
from utils.screening import StockScreener
from infrastructure.config.settings import get_settings

settings = get_settings()
screener = StockScreener(settings=settings)

result = screener.run_screening(
    screening_logic={
        "expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03)",
        "tools": [
            {
                "name": "rolling_mean",
                "params": {"column": "vol", "window": 20},
                "output": "vol_ma20"
            },
            {
                "name": "pct_change",
                "params": {"column": "close", "periods": 1},
                "output": "pct_1d"
            }
        ],
        "confidence": "rank_normalize(vol / vol_ma20) * 0.6 + rank_normalize(pct_1d) * 0.4"
    },
    top_n=20,
    screening_date="20260413"
)

print(f"筛选出 {len(result['stocks'])} 只股票")
```

### 2. PreFilterEngine(预筛选引擎)

基于股票池规则快速过滤无效股票。

**过滤规则**:

| 规则 | 说明 | 配置项 |
|------|------|--------|
| ST 股票 | 排除 ST、*ST 股票 | `stock_pool.exclude_st` |
| 停牌股票 | 排除当日停牌股票 | 自动检测 `vol == 0` |
| 上市天数 | 排除上市不足 N 天的股票 | `stock_pool.min_list_days` |
| 行业过滤 | 只保留指定行业的股票 | `stock_pool.industry` |

**配置示例**(`settings.yaml`):

```yaml
stock_pool:
  min_list_days: 180          
  exclude_st: true            
  exclude_star: false         
  industry: null              
```

### 3. BatchCalculator(批量计算器)

向量化批量计算技术指标和自定义因子。

**支持的指标类型**:

| 指标类型 | 函数名 | 示例 |
|---------|--------|------|
| 移动平均 | `rolling_mean` | `rolling_mean({"column": "close", "window": 5})` |
| 最大值 | `rolling_max` | `rolling_max({"column": "high", "window": 20})` |
| 最小值 | `rolling_min` | `rolling_min({"column": "low", "window": 20})` |
| 涨跌幅 | `pct_change` | `pct_change({"column": "close", "periods": 1})` |
| RSI | `rsi` | `rsi({"column": "close", "window": 14})` |
| MACD | `macd` | `macd({"column": "close"})` |

### 4. ScriptSaver(脚本保存器)

自动生成可复用的 Python 筛选脚本。

**使用示例**:

```python
from src.screening import ScriptSaver
from pathlib import Path

saver = ScriptSaver(output_dir=Path("app/screening_scripts"))

script_path = saver.save_script(
    strategy_name="放量突破",
    screening_logic=screening_logic,
    screening_date="20260413"
)

print(f"脚本已保存: {script_path}")
```

## 💡 使用示例

### 示例 1:基础筛选

```python
screening_logic = {
    "expression": "(close > ma5) & (ma5 > ma10) & (ma10 > ma20)",
    "tools": [
        {"name": "rolling_mean", "params": {"column": "close", "window": 5}, "output": "ma5"},
        {"name": "rolling_mean", "params": {"column": "close", "window": 10}, "output": "ma10"},
        {"name": "rolling_mean", "params": {"column": "close", "window": 20}, "output": "ma20"}
    ],
    "confidence": "rank_normalize(close / ma20)"
}

result = screener.run_screening(
    screening_logic=screening_logic,
    top_n=20,
    screening_date="20260413"
)
```

### 示例 2:复杂筛选(放量突破)

```python
screening_logic = {
    "expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03) & (close >= high_20 * 0.95)",
    "tools": [
        {"name": "rolling_mean", "params": {"column": "vol", "window": 20}, "output": "vol_ma20"},
        {"name": "pct_change", "params": {"column": "close", "periods": 1}, "output": "pct_1d"},
        {"name": "rolling_max", "params": {"column": "high", "window": 20}, "output": "high_20"}
    ],
    "confidence": "rank_normalize(vol / vol_ma20) * 0.4 + rank_normalize(pct_1d) * 0.3"
}

result = screener.run_screening(screening_logic=screening_logic, top_n=20)
```

## ⚙️ 配置说明

```yaml
stock_pool:
  min_list_days: 180          
  exclude_st: true            
  exclude_star: false         
  industry: null              

screening:
  max_candidates: 100         
  default_top_n: 20           
  enable_script_save: true    
  script_output_dir: "app/screening_scripts"
```

## 🧪 测试

```bash
pytest tests/src/screening/ -v
```

## 🔗 相关文档

- [主 README](../README.md)
- [DataHub](./datahub.md)
- [Agent System](./agent_system.md)
- [Backtest Engine](./backtest_engine.md)
