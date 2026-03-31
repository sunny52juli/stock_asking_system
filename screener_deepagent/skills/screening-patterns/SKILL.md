---
name: screening-patterns
description: |
  筛选模式最佳实践 - 提供技术指标选择、表达式设计、置信度公式等的设计模式。
  帮助 Deep Agent 构建更有效的股票筛选逻辑。
version: 1.0.0
author: Quant Team
---

# 筛选模式最佳实践

## 工具选择原则

### 趋势类指标
- **MACD**: 中长期趋势，适合波段操作
- **EMA**: 平滑趋势线，减少噪音
- **ADX**: 趋势强度判断

### 超买超卖指标
- **RSI**: 14日为标准，< 30超卖，> 70超买
- **KDJ**: K线与D线交叉，快速反应
- **CCI**: 商品通道指标，识别极端值

### 成交量指标
- **OBV**: 能量潮，确认趋势
- **Volume Ratio**: 成交量比率，识别放量

### 波动率指标
- **ATR**: 真实波幅，衡量波动
- **Bollinger Bands**: 布林带，识别突破

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

### 取反
```python
~(condition)
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

### 条件分段
```python
1.0 if strong_signal else 0.5 if weak_signal else 0.0
```

## 常见错误

1. ❌ 使用未定义的 var
2. ❌ 参数名错误 (rsi 用 period 而非 window)
3. ❌ 百分比用整数 (5 而非 0.05)
4. ❌ 忘记添加行业/市场过滤器
5. ❌ expression 语法错误 (缺少括号)
