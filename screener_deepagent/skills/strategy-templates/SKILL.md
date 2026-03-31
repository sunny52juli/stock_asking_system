---
name: strategy-templates
description: |
  筛选策略模板库 - 提供常见的股票筛选策略 JSON 模板，包括动量突破、RSI 超卖、MACD 金叉等。
  Deep Agent 可以参考这些模板快速构建 screening_logic。
version: 1.0.0
author: Quant Team
---

# 筛选策略模板

## 动量突破策略

```json
{
  "name": "放量突破策略",
  "tools": [
    {"tool": "pct_change", "params": {"periods": 1}, "var": "daily_return"},
    {"tool": "rolling_mean", "params": {"window": 5, "column": "volume"}, "var": "avg_volume"},
    {"tool": "rsi", "params": {"window": 14}, "var": "rsi_val"}
  ],
  "expression": "(daily_return > 0.03) & (volume / avg_volume > 1.5) & (rsi_val < 70)",
  "confidence_formula": "daily_return * 10"
}
```

## RSI超卖策略

```json
{
  "name": "RSI超卖反弹",
  "tools": [
    {"tool": "rsi", "params": {"window": 14}, "var": "rsi_val"},
    {"tool": "pct_change", "params": {"periods": 1}, "var": "daily_return"}
  ],
  "expression": "(rsi_val < 30) & (daily_return > -0.05)",
  "confidence_formula": "(30 - rsi_val) / 30"
}
```

## MACD金叉策略

```json
{
  "name": "MACD金叉",
  "tools": [
    {"tool": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "var": "macd_result"}
  ],
  "expression": "(macd_result['macd'] > macd_result['signal']) & (macd_result['macd'] > 0)",
  "confidence_formula": "macd_result['macd'] / 10"
}
```

## 多指标综合策略

```json
{
  "name": "多指标综合筛选",
  "tools": [
    {"tool": "rsi", "params": {"window": 14}, "var": "rsi_val"},
    {"tool": "macd", "params": {}, "var": "macd_result"},
    {"tool": "kdj", "params": {}, "var": "kdj_result"},
    {"tool": "pct_change", "params": {"periods": 1}, "var": "daily_return"}
  ],
  "expression": "(rsi_val > 30) & (rsi_val < 70) & (macd_result['macd'] > macd_result['signal']) & (kdj_result['k'] > kdj_result['d']) & (daily_return > 0)",
  "confidence_formula": "(rsi_val / 100) * 0.3 + (daily_return * 10) * 0.7"
}
```

## 注意事项

1. filter_by_industry / filter_by_market 必须放在 tools 数组最前面
2. 每个 var 必须唯一
3. expression 中引用的 var 必须在 tools 中定义
4. 参数名严格遵循工具定义
5. 百分比用小数表示
