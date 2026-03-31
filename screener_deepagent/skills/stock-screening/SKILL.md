---
name: stock-screening
description: |
  股票筛选技能 - 指导 Deep Agent 如何将自然语言查询转换为技术指标筛选逻辑。
  包含 screening_logic JSON 结构规范、MCP 工具使用指南、可用数据字段说明、
  工作流程以及常见错误避免方法。
version: 1.0.0
author: Quant Team
---

# 股票筛选技能 (Stock Screening Skill)

## 概述

本技能提供将自然语言股票查询转换为可执行筛选逻辑的完整指导。
Deep Agent 通过本技能学会:
1. 理解用户查询意图并分解为技术指标条件
2. 使用本模块 MCP 工具计算技术指标
3. 构建符合规范的 screening_logic JSON
4. 调用 bridge 工具 `run_screening` 执行筛选

---

## 核心工作流程

```
用户查询 → 理解意图 → 分解条件 → 选择 MCP 工具 → 构建 screening_logic → 调用 run_screening → 返回结果
```

1. **理解查询意图**: 分析用户的自然语言查询,识别关键条件(行业、技术指标、价格形态等)
2. **分解查询条件**: 将查询拆解为具体的筛选条件,如"放量突破"→成交量放大+价格上涨
3. **选择 MCP 工具**: 根据条件选择适当的工具(如 pct_change、rolling_mean、rsi 等)
4. **构建 screening_logic**: 按照 JSON 格式规范构建筛选逻辑
5. **调用 bridge 工具**: 使用 `run_screening` 工具执行筛选

---

## screening_logic 结构规范

### 完整 JSON 结构

```json
{
    "name": "筛选逻辑名称(简洁描述筛选意图)",
    "tools": [
        {
            "tool": "工具名称",
            "params": {"参数名": "参数值"},
            "var": "变量名(用于 expression 中引用)"
        }
    ],
    "expression": "布尔表达式(使用 tools 中定义的 var)",
    "confidence_formula": "置信度计算公式(数值表达式)",
    "rationale": "筛选理由说明"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 筛选逻辑名称,简洁描述筛选意图 |
| tools | array | 是 | 工具调用步骤列表,按执行顺序排列 |
| expression | string | 是 | 最终筛选条件,布尔表达式,引用 tools 中的 var |
| confidence_formula | string | 否 | 置信度计算公式,数值越大表示越符合条件 |
| rationale | string | 是 | 筛选理由说明,解释为何这样设计筛选逻辑 |

### tools 数组项结构

```json
{
    "tool": "工具名称(如 rolling_mean, rsi, pct_change)",
    "params": {
        "参数1": "值1",
        "参数2": "值2"
    },
    "var": "变量名(在 expression 中引用)"
}
```

---

## 可用 MCP 工具参考

### 数学变换工具

| 工具 | 描述 | 参数 | 示例表达式 |
|------|------|------|-----------|
| abs_value | 绝对值 | values | `abs(close - open)` |
| log_transform | 对数变换 log(1+x) | values | `log(1 + field)` |
| sqrt_transform | 平方根变换(保留符号) | values | `sqrt(abs(field)) * sign(field)` |
| power_transform | 幂次变换 | values, power | `(field) ** 2` |
| rank_normalize | 横截面排名归一化到[0,1] | values | `rank(field)` |
| zscore_normalize | Z-score标准化 | values | `zscore(field)` |

### 时间序列工具

| 工具 | 描述 | 参数 | 表达式示例 |
|------|------|------|-----------|
| rolling_mean | 移动平均 | values, window | `ma_5(close)` |
| rolling_std | 移动标准差 | values, window | `std_20(close)` |
| rolling_max | 移动最大值 | values, window | `max_20(high)` |
| rolling_min | 移动最小值 | values, window | `min_20(low)` |
| pct_change | 百分比变化 | values, periods | `pct_5(close)` |
| ewm | 指数加权移动平均 | values, span | `ema_12(close)` |

**参数说明**:
- `values`: 字段名,必须使用英文(如 "close", "vol")
- `window`: 窗口大小(天数),常用 5, 10, 20, 60
- `periods`: 时间间隔(天数),如 1(日涨跌), 5(周涨跌)
- `span`: 时间跨度,EMA 计算用

### 技术指标工具

| 工具 | 描述 | 参数 | 表达式示例 |
|------|------|------|-----------|
| rsi | 相对强弱指标 | values, window | `rsi_14(close)` |
| macd | MACD指标 | values, fast, slow, signal | `macd(close)` |
| kdj | KDJ随机指标 | high, low, close, window | `kdj_9` |
| atr | 平均真实波幅 | high, low, close, window | `atr_14` |
| obv | 能量潮 | close, vol | `obv` |

**参数说明**:
- `window`: RSI 默认 14, KDJ 默认 9, ATR 默认 14
- `values`: 通常是价格字段 "close"

### 统计工具

| 工具 | 描述 | 参数 | 表达式示例 |
|------|------|------|-----------|
| correlation | 滚动相关系数 | x, y, window | `corr_20(close, vol)` |
| skewness | 偏度 | values, window | `skew_20(close)` |
| kurtosis | 峰度 | values, window | `kurt_20(close)` |

### 特征工程工具

| 工具 | 描述 | 参数 | 表达式示例 |
|------|------|------|-----------|
| ts_rank | 时间序列排名 | values, window | `ts_rank_10(close)` |
| ts_argmax | 时间序列最大值位置 | values, window | `ts_argmax_10(high)` |
| ts_argmin | 时间序列最小值位置 | values, window | `ts_argmin_10(low)` |
| decay_linear | 线性衰减加权平均 | values, window | `decay_linear_10(close)` |

### 风险指标工具

| 工具 | 描述 | 参数 | 表达式示例 |
|------|------|------|-----------|
| volatility | 波动率(年化标准差) | values, window | `vol_20(returns)` |
| max_drawdown | 最大回撤 | values, window | `mdd_60(close)` |

### 筛选专用工具

| 工具 | 描述 | 参数 | 表达式示例 | 注意事项 |
|------|------|------|-----------|----------|
| filter_by_industry | 按行业筛选 | industry | `filter_by_industry('通信设备')` | **必须从实际行业列表复制完整名称** |
| filter_by_market | 按市场筛选 | market | `filter_by_market('科创板')` | 市场名: 主板/创业板/科创板/北交所 |

---

## 可用数据字段 (重要约束)

### 标准字段(必须使用这些字段,不得编造)

**基础价格字段**:
- `open` / `开盘价` - 当日开盘价
- `high` / `最高价` - 当日最高价
- `low` / `最低价` - 当日最低价
- `close` / `收盘价` - 当日收盘价
- `pre_close` / `前收盘` - 前一交易日收盘价
- `change` / `涨跌额` - 涨跌额(元)
- `pct_chg` / `涨跌幅` - 涨跌幅(%)

**成交量字段**:
- `vol` / `成交量` - 当日成交量(手) ⚠️ **注意:字段名是 vol 不是 volume**
- `amount` / `成交额` - 当日成交金额(千元)

**基础信息字段**:
- `ts_code` / `code` - 股票代码(如: 000001.SZ)
- `name` - 股票名称
- `industry` - 所属行业
- `market` - 所属市场(主板/创业板/科创板等)

**常用技术指标字段**:
- `turnover_rate` - 换手率(%)
- `pe` / `pe_ttm` - 市盈率
- `pb` - 市净率
- `total_mv` - 总市值(万元)
- `circ_mv` - 流通市值(万元)

### 字段使用规则

1. **严格约束**: 只能使用上述列出的字段,**禁止编造或假设其他字段**
2. **中英文支持**: 价格和成交量字段支持中英文名称
3. **字段组合**: 可以通过表达式组合字段(如 `(high+low)/2`)
4. **单位注意**: 注意字段单位差异(成交额单位为千元,市值单位为万元)

---

## Bridge 工具说明

### run_screening (必须)

**用途**: 在本地数据上执行筛选逻辑

**参数**:
- `screening_logic_json`: screening_logic JSON 字符串
- `top_n`: 返回的股票数量上限(默认 20)

**返回值**: JSON 字符串,包含:
- `status`: "success" 或 "error"
- `candidates`: 候选股票列表
- `count`: 候选股票数量

**使用时机**: 构建完 screening_logic 后,调用此工具执行筛选

### get_available_industries (建议)

**用途**: 获取当前数据中的可用行业列表

**参数**: 无

**返回值**: JSON 字符串,包含 `industries` 数组

**使用时机**: 当用户查询涉及行业筛选时,先调用此工具获取实际行业列表

### calculate_holding_returns (可选)

**用途**: 计算候选股票的持有期收益率

**参数**:
- `candidates_json`: 候选股票列表 JSON 字符串
- `periods_str`: 持有期列表 JSON 字符串(如 "[1, 5]")

**返回值**: JSON 字符串,包含收益率统计信息

**使用时机**: 执行完筛选后,如需评估筛选效果,调用此工具计算收益率

### save_screening_script (可选)

**用途**: 将筛选逻辑保存为可重复使用的 Python 脚本

**参数**:
- `screening_logic_json`: screening_logic JSON 字符串
- `query`: 原始用户查询

**返回值**: JSON 字符串,包含保存的脚本路径

**使用时机**: 筛选逻辑验证有效后,可选择保存以便后续复用

---

## 完整示例

### 示例 1: 放量突破

**用户查询**: "找出最近放量突破的股票,要求成交量较前期放大至少 1.5 倍,涨幅>3%"

**Screening Logic**:

```json
{
    "name": "放量突破股票",
    "tools": [
        {"tool": "rolling_mean", "params": {"values": "vol", "window": 20}, "var": "vol_ma20"},
        {"tool": "pct_change", "params": {"values": "close", "periods": 1}, "var": "pct_1d"}
    ],
    "expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03)",
    "confidence_formula": "(vol / vol_ma20) * pct_1d",
    "rationale": "成交量较20日均量放大1.5倍以上,且当日涨幅超过3%的放量突破股票"
}
```

### 示例 2: 行业强势股

**用户查询**: "通信设备行业中,5日涨幅超过3%的股票"

**步骤 1**: 调用 `get_available_industries` 获取实际行业列表

**步骤 2**: 从返回的行业列表中找到 "通信设备"(或最接近的完整名称)

**步骤 3**: 构建 Screening Logic:

```json
{
    "name": "通信设备强势股",
    "tools": [
        {"tool": "filter_by_industry", "params": {"industry": "通信设备"}, "var": "ind_filter"},
        {"tool": "pct_change", "params": {"values": "close", "periods": 5}, "var": "pct_5d"}
    ],
    "expression": "ind_filter & (pct_5d > 0.03)",
    "confidence_formula": "pct_5d",
    "rationale": "通信设备行业中5日涨幅超过3%的强势股票"
}
```

### 示例 3: 均线多头排列

**用户查询**: "找出均线多头排列的股票,要求短期均线在长期均线之上"

**Screening Logic**:

```json
{
    "name": "均线多头排列",
    "tools": [
        {"tool": "rolling_mean", "params": {"values": "close", "window": 5}, "var": "ma5"},
        {"tool": "rolling_mean", "params": {"values": "close", "window": 10}, "var": "ma10"},
        {"tool": "rolling_mean", "params": {"values": "close", "window": 20}, "var": "ma20"}
    ],
    "expression": "(ma5 > ma10) & (ma10 > ma20)",
    "confidence_formula": "(ma5 - ma20) / ma20",
    "rationale": "5日均线上穿10日均线,且10日均线上穿20日均线的多头排列股票"
}
```

### 示例 4: RSI 超卖反弹

**用户查询**: "找出RSI超卖反弹的股票,RSI在30-50之间"

**说明**: 精确的「从30以下回升」需时序工具(如 ts_rank/前日值); 当前 MCP 无 `lag` 工具, 以下用 RSI 区间做等价筛选。

**Screening Logic**:

```json
{
    "name": "RSI超卖反弹",
    "tools": [
        {"tool": "rsi", "params": {"values": "close", "window": 14}, "var": "rsi14"}
    ],
    "expression": "(rsi14 > 30) & (rsi14 < 50)",
    "confidence_formula": "(rsi14 - 30) / 20",
    "rationale": "RSI(14)处于30-50区间的超卖反弹候选(更精细的前日RSI<30 需时序工具)"
}
```

---

## 常见错误与正确做法

### ❌ 错误 1: 使用不存在的字段名

```json
// 错误: volume 不是有效字段名
{"tool": "rolling_mean", "params": {"values": "volume", "window": 20}}

// 正确: 使用 vol
{"tool": "rolling_mean", "params": {"values": "vol", "window": 20}}
```

### ❌ 错误 2: 百分比使用错误格式

```json
// 错误: 5% 写成 5(会被理解为500%)
"expression": "pct_5d > 5"

// 正确: 5% 写成 0.05
"expression": "pct_5d > 0.05"
```

### ❌ 错误 3: 行业名称凭记忆填写

```json
// 错误: 凭记忆缩写行业名
{"tool": "filter_by_industry", "params": {"industry": "通信"}}

// 正确: 从 get_available_industries 返回的列表中复制完整名称
{"tool": "filter_by_industry", "params": {"industry": "通信设备"}}
```

### ❌ 错误 4: 参数名错误

```json
// 错误: rsi 使用 period 参数
{"tool": "rsi", "params": {"values": "close", "period": 14}}

// 正确: rsi 使用 window 参数
{"tool": "rsi", "params": {"values": "close", "window": 14}}
```

### ❌ 错误 5: 条件过于严格

```json
// 错误: 条件过于严格导致无结果
"expression": "(vol > vol_ma20 * 10) & (pct_1d > 0.1)"

// 正确: 合理阈值
"expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03)"
```

### ❌ 错误 6: filter_by_industry 位置不当

```json
// 错误: 筛选工具放在后面,浪费计算资源
{"tools": [
    {"tool": "pct_change", ...},
    {"tool": "filter_by_industry", ...}
]}

// 正确: 筛选工具放在最前面
{"tools": [
    {"tool": "filter_by_industry", ...},
    {"tool": "pct_change", ...}
]}
```

---

## 最佳实践

### 1. 性能优化

- **预筛选优先**: 先执行行业/市场筛选,再计算技术指标
- **合理窗口**: 窗口大小建议在 5-60 天范围内
- **避免重复**: 同一指标只需计算一次,在 expression 中复用

### 2. 置信度设计

- **基于指标强度**: 如涨幅越大置信度越高
- **多维度考虑**: 结合量价、技术指标综合计算
- **合理范围**: 结果在 0-1 之间,避免极端值

### 3. 条件设计

- **合理阈值**: 不要过于严格(如成交量放大 10 倍)
- **渐进筛选**: 从宽松条件开始,逐步收紧
- **容错设计**: 考虑数据缺失情况,避免硬边界

---

## 故障排除

**Q: 筛选结果为空?**
A: 检查条件是否过于严格,逐步放宽条件测试

**Q: 工具调用失败?**
A: 检查参数格式,确保使用正确的参数名(如 window 不是 period)

**Q: 行业筛选无效?**
A: 确保行业名称从 `get_available_industries` 返回的列表中完整复制

**Q: 置信度计算异常?**
A: 检查置信度公式,避免除零,使用安全常数(如 `/(std + 1e-8)`)

---

## 更新日志

- v1.0.0: 初始版本,支持基础股票筛选功能
