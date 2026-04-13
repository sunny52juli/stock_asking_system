---
name: stock-screening-src
description: |
  股票筛选核心指南 - 字段规范、MCP工具参考、工作流程和完整示例。
  指导 Deep Agent 将自然语言查询转换为可执行的 screening_logic JSON。
version: 2.0.0
author: Quant Team
---

# 股票筛选核心指南

## 工作流程
用户查询 → 理解意图 → 选择指标 → 构建 screening_logic → 调用 run_screening → 返回结果

## screening_logic 结构
```json
{
  "name": "策略名称",
  "tools": [
    {"tool": "工具名", "params": {"参数": "值"}, "var": "变量名"}
  ],
  "expression": "(var1 > 值) & (var2 < 值)",
  "confidence_formula": "var1 * 0.5 + var2 * 0.5",
  "rationale": "筛选理由"
}
```

## 可用字段（严格约束）
**价格**: `close`, `open`, `high`, `low`, `pre_close`, `change`, `pct_chg`  
**成交量**: `vol` (⚠️ 不是 volume), `amount`  
**信息**: `ts_code`, `name`, `industry`, `market`  
**指标**: `turnover_rate`, `pe`, `pb`, `total_mv`, `circ_mv`

## MCP 工具参考

### 时间序列工具
- `rolling_mean(values, window)` - 移动平均，window常用5/10/20/60
- `rolling_std(values, window)` - 移动标准差
- `pct_change(values, periods)` - 百分比变化，periods=1(日)/5(周)
- `ewm(values, span)` - 指数加权平均

### 技术指标
- `rsi(values, window=14)` - 相对强弱指标
- `macd(values, fast=12, slow=26, signal=9)` - MACD
- `kdj(high, low, close, window=9)` - KDJ
- `atr(high, low, close, window=14)` - 平均真实波幅

### 筛选工具
- `filter_by_industry(industry)` - ⚠️ 必须从 get_available_industries 获取完整名称
- `filter_by_market(market)` - 主板/创业板/科创板/北交所

### 数学变换
- `rank_normalize(values)` - 排名归一化[0,1]
- `zscore_normalize(values)` - Z-score标准化
- `abs_value(values)`, `log_transform(values)`, `sqrt_transform(values)`

## Bridge 工具
- `run_screening(screening_logic_json, top_n=20)` - 执行筛选
- `get_available_industries()` - 获取行业列表
- `save_screening_script(screening_logic_json, query)` - 保存脚本

## 常见策略模式

### 1. 动量突破
**关键词**: 放量、突破、强势  
**示例**: `(vol > vol_ma20 * 1.5) & (pct_1d > 0.03)`

### 2. RSI 超卖反弹
**关键词**: 超卖、底部、反弹  
**示例**: `(rsi14 > 30) & (rsi14 < 50)`

### 3. MACD 金叉
**关键词**: 金叉、趋势转强  
**示例**: `(macd['macd'] > macd['signal']) & (macd['macd'] > 0)`

### 4. 均线多头排列
**关键词**: 多头、上升趋势  
**示例**: `(ma5 > ma10) & (ma10 > ma20)`

## 关键规则
1. **参数命名**: 所有工具第一个参数必须是 `values` 或 `column`
2. **变量一致性**: expression 中的变量名必须与 tools 定义的 `var` 完全一致
3. **百分比**: 用小数表示 (3% = 0.03)
4. **行业筛选**: 必须先调用 `get_available_industries` 获取完整行业名
5. **质量标准**: 候选数量 1-50 个为最佳

## 常见错误
- ❌ 使用不存在的字段 (`volume` → 应为 `vol`)
- ❌ 百分比用整数 (5 → 应为 0.05)
- ❌ 行业名凭记忆填写 (应从列表复制)
- ❌ 参数名错误 (`period` → 应为 `window`)
- ❌ filter_by_industry 放在后面 (应放最前以优化性能)
