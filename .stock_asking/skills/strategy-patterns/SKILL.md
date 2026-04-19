---
name: strategy-patterns
description: |
  策略模式与模板 - 常见筛选策略的 JSON 模板和设计模式。
  包括动量突破、RSI超卖、MACD金叉等经典策略的快速参考。
version: 2.0.0
author: Quant Team
---

# 策略模式与模板

## 意图识别模式

### 动量策略
- **关键词**: 放量、突破、强势、上涨、涨停
- **指标**: vol, pct_change, rsi, macd
- **时间周期**: 短期 (1-5天)

### 反转策略
- **关键词**: 超卖、超买、回调、反弹、底部
- **指标**: rsi, kdj, bollinger_position
- **时间周期**: 中期 (5-20天)

### 价值策略
- **关键词**: 低估、蓝筹、稳定、分红
- **指标**: rank_normalize, zscore_normalize
- **时间周期**: 长期 (20天以上)

### 波动率策略
- **关键词**: 波动、震荡、区间
- **指标**: volatility, atr, rolling_std
- **时间周期**: 中期

## 行业识别
常见行业表达:
- 科技 → 电子、计算机、通信
- 医疗 → 医药生物
- 金融 → 银行、非银金融
- 消费 → 食品饮料、家用电器

## 数值条件提取
- "涨幅超过3%" → pct_change > 0.03
- "RSI低于30" → rsi < 30
- "成交量放大1.5倍" → vol / rolling_mean(vol, 5) > 1.5
- **注意**: 行业/ST/市值过滤已由 StockPoolService 统一处理，无需在策略中指定

## 策略模板库

### 1. 动量突破
```json
{
  "name": "放量突破策略",
  "tools": [
    {"tool": "rolling_mean", "params": {"values": "vol", "window": 20}, "var": "vol_ma20"},
    {"tool": "pct_change", "params": {"values": "close", "periods": 1}, "var": "pct_1d"}
  ],
  "expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03)",
  "confidence_formula": "(vol / vol_ma20) * pct_1d",
  "rationale": "成交量较20日均量放大1.5倍以上，且当日涨幅超过3%的放量突破股票"
}
```

### 2. RSI 超卖反弹
```json
{
  "name": "RSI超卖反弹",
  "tools": [
    {"tool": "rsi", "params": {"values": "close", "window": 14}, "var": "rsi14"}
  ],
  "expression": "(rsi14 > 30) & (rsi14 < 50)",
  "confidence_formula": "(rsi14 - 30) / 20",
  "rationale": "RSI(14)处于30-50区间的超卖反弹候选"
}
```

### 3. MACD 金叉
```json
{
  "name": "MACD金叉",
  "tools": [
    {"tool": "macd", "params": {"values": "close", "fast": 12, "slow": 26, "signal": 9}, "var": "macd_result"}
  ],
  "expression": "(macd_result['macd'] > macd_result['signal']) & (macd_result['macd'] > 0)",
  "confidence_formula": "macd_result['macd'] / 10",
  "rationale": "MACD快线上穿慢线且大于0的金叉信号"
}
```

### 4. 均线多头排列
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
  "rationale": "5日、10日、20日均线呈多头排列的上升趋势股票"
}
```

### 5. 多指标综合
```json
{
  "name": "多指标综合筛选",
  "tools": [
    {"tool": "rsi", "params": {"values": "close", "window": 14}, "var": "rsi_val"},
    {"tool": "macd", "params": {"values": "close"}, "var": "macd_result"},
    {"tool": "pct_change", "params": {"values": "close", "periods": 1}, "var": "daily_return"}
  ],
  "expression": "(rsi_val > 30) & (rsi_val < 70) & (macd_result['macd'] > macd_result['signal']) & (daily_return > 0)",
  "confidence_formula": "(rsi_val / 100) * 0.3 + (daily_return * 10) * 0.7",
  "rationale": "结合RSI、MACD和日涨幅的多维度综合筛选"
}
```

## 表达式设计模式

### 多条件AND组合
```python
(condition1) & (condition2) & (condition3)
```

### 多条件OR组合
```python
(condition1) | (condition2)
```

### 复杂逻辑
```python
((condition1) & (condition2)) | ((condition3) & (condition4))
```

## 置信度公式设计

### 线性组合
```python
indicator1 * 0.5 + indicator2 * 0.3 + indicator3 * 0.2
```

### 归一化
```python
(indicator - min_val) / (max_val - min_val)
```

## 注意事项
1. 每个 var 必须唯一
2. expression 中引用的 var 必须在 tools 中定义
3. 参数名严格遵循工具定义
4. 百分比用小数表示
5. **重要**: 行业、ST、停牌、市值等过滤已由 StockPoolService 统一处理，不要在 screening_logic 中重复
