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

### 数据流程

```
┌─────────────────────────────────────┐
│   初始化阶段                         │
│  • DataLoader: 加载原始市场数据      │
│  • StockPoolService: 执行股票池过滤  │
│    - ST/停牌/上市天数过滤            │
│    - 行业过滤（LLM智能匹配）         │
│    - 价格/成交量/市值过滤            │
│    - 数据完整性过滤                  │
└──────────────┬──────────────────────┘
               │ (过滤后的数据)
┌──────────────▼──────────────────────┐
│   Agent 执行阶段                     │
│  • Screening Logic (from Agent)     │
│    - expression: 筛选表达式          │
│    - tools: 指标计算工具列表         │
│    - confidence: 置信度公式          │
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

**关键优化**：
- **一次性过滤**：股票池过滤在主函数中执行一次，多个策略共享过滤后的数据
- **职责分离**：`StockPoolService` 独立处理过滤逻辑，`Orchestrator` 只负责流程编排

## 📁 目录结构

```
src/screening/
├── __init__.py                     # 模块入口
├── batch_calculator.py            # 批量计算器 BatchCalculator
├── executor.py                    # 筛选执行器 ScreeningExecutor
├── industry_matcher.py            # 行业匹配器 IndustryMatcher
├── prefilter.py                   # 预筛选引擎 PreFilterEngine
├── result_display.py              # 结果显示工具 ResultDisplayer
├── script_saver.py                # 脚本保存器 ScriptSaver
├── stock_pool_filter.py           # 股票池筛选器 StockPoolFilter
└── tool_implementations.py        # 工具实现

src/agent/services/
└── stock_pool_service.py          # 股票池服务（独立模块）

app/screening_scripts/              # 生成的筛选脚本
└── 放量突破/
    ├── 放量突破_20260413_235007.py
    └── 放量突破_20260414_002658.py
```

## 🔧 核心组件

### 1. ScreeningExecutor（筛选执行器）

主入口类，协调整个筛选流程。

**使用示例**：

```python
from src.screening import ScreeningExecutor
from infrastructure.config.settings import get_settings

settings = get_settings()
executor = ScreeningExecutor(settings=settings)

result = executor.execute_screening(
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

### 2. StockPoolService（股票池服务）

独立的股票池过滤服务模块，在主函数中执行一次，多个策略共享过滤后的数据。

**职责**：
- 从 `stock_pool.yaml` 读取配置
- 执行完整的股票池过滤流程
- 返回过滤后的数据和股票代码列表

**过滤规则**：

| 规则 | 说明 | 配置项 |
|------|------|--------|
| ST 股票 | 排除 ST、*ST 股票 | `stock_pool.exclude_st` |
| 停牌股票 | 排除当日停牌股票 | `stock_pool.exclude_suspended` |
| 上市天数 | 排除上市不足 N 天的股票 | `stock_pool.min_list_days` |
| 行业过滤 | 模糊匹配指定行业关键词 | `stock_pool.industry` |
| 价格过滤 | 观察期内最高价 >= min_price | `stock_pool.min_price` |
| 价格过滤 | 观察期内最低价 <= max_price | `stock_pool.max_price` |
| 成交量过滤 | 观察期内最大成交量 >= min_vol | `stock_pool.min_vol` |
| 成交额过滤 | 观察期内最大成交额 >= min_amount | `stock_pool.min_amount` |
| 换手率过滤 | 观察期内最大换手率 >= min_turnover | `stock_pool.min_turnover` |
| 市值过滤 | 最新交易日总市值 >= min_total_mv | `stock_pool.min_total_mv` |
| 市值过滤 | 最新交易日总市值 <= max_total_mv | `stock_pool.max_total_mv` |
| 数据完整性 | 完整度 >= min_completeness_ratio | `stock_pool.min_completeness_ratio` |
| 数据完整性 | 缺失天数 <= max_missing_days | `stock_pool.max_missing_days` |

**使用示例**：

```python
from src.agent.services.stock_pool_service import StockPoolService
from infrastructure.config.settings import get_settings

# 1. 加载配置
settings = get_settings()
service = StockPoolService(settings)

# 2. 执行过滤
filtered_data, filtered_codes = service.apply_filter(
    raw_data=raw_market_data,
    raw_codes=all_stock_codes
)

print(f"初始股票数: {len(all_stock_codes)}")
print(f"筛选后股票数: {len(filtered_codes)}")
```

**主函数调用** (`app/screener.py`)：

```python
# 初始化 Orchestrator（加载原始数据）
orchestrator = ScreenerOrchestrator(settings=settings)
orchestrator.initialize()

# 执行股票池过滤（独立服务模块）
from src.agent.services.stock_pool_service import StockPoolService
stock_pool_service = StockPoolService(settings)
filtered_data, filtered_codes = stock_pool_service.apply_filter(
    orchestrator.data, 
    orchestrator.stock_codes
)

# 更新 Orchestrator 的数据
orchestrator.data = filtered_data
orchestrator.stock_codes = filtered_codes
```

**配置文件** (`app/setting/stock_pool.yaml`)：

```yaml
stock_pool:
  min_list_days: 180           # 最小上市天数
  exclude_st: true             # 排除ST股票
  exclude_suspended: true      # 排除停牌股票
  industry:                    # 行业过滤列表（支持模糊匹配），null表示全市场
    - '通信'
    - '芯片'
  
  # 数据质量参数
  min_completeness_ratio: 0.8  # 最小数据完整度 (0.0-1.0)
  max_missing_days: 5          # 最大缺失天数
  min_price: 2                 # 最低价格过滤
  max_price: 1000              # 最高价格过滤
  min_amount: 100000           # 最小成交量金额（单位千元）
  min_turnover_rate_f: 2       # 最小自由换手率过滤
  min_total_mv: 1e+5           # 最小总市值过滤（单位万元）
  max_total_mv: 1e+8           # 最大总市值过滤（单位万元）
```

### 3. BatchCalculator（批量计算器）

向量化批量计算技术指标和自定义因子。

**支持的指标类型**：

| 指标类型 | 函数名 | 示例 |
|---------|--------|------|
| 移动平均 | `rolling_mean` | `rolling_mean({"column": "close", "window": 5})` |
| 最大值 | `rolling_max` | `rolling_max({"column": "high", "window": 20})` |
| 最小值 | `rolling_min` | `rolling_min({"column": "low", "window": 20})` |
| 涨跌幅 | `pct_change` | `pct_change({"column": "close", "periods": 1})` |
| RSI | `rsi` | `rsi({"column": "close", "window": 14})` |
| MACD | `macd` | `macd({"column": "close"})` |

### 4. PreFilterEngine（预筛选引擎）

基于股票池规则快速过滤无效股票。

**过滤规则**：
- ST 股票过滤
- 停牌股票过滤
- 上市天数过滤
- 行业过滤（模糊匹配）

### 5. ScriptSaver（脚本保存器）

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

### 示例 1：基础筛选

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

result = executor.execute_screening(
    screening_logic=screening_logic,
    top_n=20,
    screening_date="20260413"
)
```

### 示例 2：复杂筛选（放量突破）

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

result = executor.execute_screening(screening_logic=screening_logic, top_n=20)
```

## ⚙️ 配置说明

### 股票池配置 (`app/setting/stock_pool.yaml`)

```yaml
stock_pool:
  min_list_days: 180           # 最小上市天数
  exclude_st: true             # 排除ST股票
  exclude_suspended: true      # 排除停牌股票
  industry: null               # 行业过滤列表，null表示全市场
  
  # 数据质量参数
  min_completeness_ratio: 0.8  # 最小数据完整度 (0.0-1.0)
  max_missing_days: 5          # 最大缺失天数
  min_price: 2                 # 最低价格过滤
  max_price: 1000              # 最高价格过滤
  min_vol: 0                   # 最小成交量过滤，0表示不过滤
  min_amount: 100000           # 最小成交额过滤（单位千元）
  min_turnover: 0              # 最小换手率过滤，0表示不过滤
  min_total_mv: 1e+5           # 最小总市值过滤（单位万元）
  max_total_mv: 1e+8           # 最大总市值过滤（单位万元）
```

### 筛选引擎配置

```yaml
screening:
  max_candidates: 100         # 最大候选股票数
  default_top_n: 20           # 默认返回Top-N数量
  enable_script_save: true    # 是否启用脚本保存
  script_output_dir: "app/screening_scripts"  # 脚本输出目录
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
