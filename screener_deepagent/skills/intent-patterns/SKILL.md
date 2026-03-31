---
name: intent-patterns
description: |
  意图识别模式 - 帮助 Deep Agent 理解用户查询的关键词、指标和时间周期。
  包含动量策略、反转策略、价值策略、波动率策略等常见模式的识别方法。
version: 1.0.0
author: Quant Team
---

# 意图识别模式

## 常见查询模式

### 动量策略
- 关键词: 放量、突破、强势、上涨、涨停
- 指标: volume, pct_change, rsi, macd
- 时间周期: 短期 (1-5天)

### 反转策略
- 关键词: 超卖、超买、回调、反弹、底部
- 指标: rsi, kdj, bollinger_position
- 时间周期: 中期 (5-20天)

### 价值策略
- 关键词: 低估、蓝筹、稳定、分红
- 指标: rank_normalize, zscore_normalize
- 时间周期: 长期 (20天以上)

### 波动率策略
- 关键词: 波动、震荡、区间
- 指标: volatility, atr, rolling_std
- 时间周期: 中期

## 行业识别

常见行业表达:
- 科技 → 电子、计算机、通信
- 医疗 → 医药生物
- 金融 → 银行、非银金融
- 消费 → 食品饮料、家用电器

## 数值条件提取

- "涨幅超过3%" → pct_change > 0.03
- "RSI低于30" → rsi < 30
- "成交量放大1.5倍" → volume / rolling_mean(volume, 5) > 1.5
- "市值大于100亿" → market_cap > 10000000000
