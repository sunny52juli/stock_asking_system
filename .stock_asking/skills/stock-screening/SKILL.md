---
name: stock-screening
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
  - **示例**: `{"tool": "rolling_mean", "params": {"column": "close", "window": 20}, "var": "ma20"}`
- `rolling_std(values, window)` - 移动标准差（波动率）
  - **示例**: `{"tool": "rolling_std", "params": {"column": "close", "window": 20}, "var": "volatility_20"}`
  - **⚠️ 重要**: rolling_std返回的是**绝对标准差**（单位：元）
  - **❌ 禁止用法**: 
    - `(volatility_20 < 0.03)` → 量纲错误，0.03元无意义
    - `(volatility_20 / close < 0.10)` → **禁止随意除法**，变异系数需要明确的金融含义
  - **✅ 正确用法**: 
    - 直接使用绝对值排序: 按 `volatility_20` 从小到大筛选低波动股票
    - 使用专业指标: `beta` (系统性风险), `atr` (平均真实波幅), `information_ratio` (信息比率)
    - 如需相对波动率，应使用: `volatility_20` 的**分位数排名**或**Z-score标准化**
- `pct_change(values, periods)` - 百分比变化，periods=1(日)/5(周)
  - **示例**: `{"tool": "pct_change", "params": {"column": "close", "periods": 20}, "var": "return_20d"}`
- `ewm(values, span)` - 指数加权平均

### 技术指标
- `rsi(values, window=14)` - 相对强弱指标
- `macd(values, fast=12, slow=26, signal=9)` - MACD
- `kdj(high, low, close, window=9)` - KDJ
- `atr(high, low, close, window=14)` - 平均真实波幅

### 指数相关性工具（需配合Bridge自动加载指数数据）
- `beta(stock_col='close', index_col='index_close', window=60)` - Beta系数（系统性风险），Beta<1为低波动
- `alpha(stock_col='close', index_col='index_close', window=60)` - Alpha超额收益，Alpha>0表示跑赢大盘
- `outperform_rate(stock_col='close', index_col='index_close', window=60)` - 窗口内跑赢指数的天数
- `correlation_with_index(stock_col='close', index_col='index_close', window=60)` - 与指数的相关系数
- `tracking_error(stock_col='close', index_col='index_close', window=60)` - 跟踪误差（主动风险）
- `information_ratio(stock_col='close', index_col='index_close', window=60)` - 信息比率（IR>0.5为优秀）

**⚠️ 重要提示**：
- 使用指数相关性工具时，Bridge会**自动检测并加载对应指数数据**
- 指数选择规则：科创板→科创50，创业板→创业板指，上交所→上证指数，深交所→深证成指，北交所→北证50
- 无需手动指定指数代码，系统会根据股票代码自动选择

### 筛选工具
- `filter_by_industry(industry)` - ⚠️ 行业过滤已由 StockPoolService 统一处理，无需在 screening_logic 中调用
- `filter_by_market(market)` - ⚠️ 市场板块过滤已由 StockPoolService 统一处理

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

### 5. 低波动策略（正确用法）
**关键词**: 低波动、稳健  
**❌ 错误示例**: 
- `(volatility_20 < 0.03)` → 量纲错误
- `(volatility_20 / close < 0.10)` → **禁止随意除法**

**✅ 正确示例1 - 使用绝对值排序**:
```json
{
  "name": "low_volatility_absolute",
  "tools": [
    {"tool": "rolling_std", "params": {"column": "close", "window": 20}, "var": "volatility_20"}
  ],
  "expression": "volatility_20 > 0",  // 筛选出有数据的股票
  "confidence_formula": "1.0 / (volatility_20 + 0.01)"  // 波动率越低，置信度越高
}
```

**✅ 正确示例2 - 使用Z-score标准化**:
```json
{
  "name": "low_volatility_zscore",
  "tools": [
    {"tool": "rolling_std", "params": {"column": "close", "window": 20}, "var": "volatility_20"},
    {"tool": "zscore_normalize", "params": {"values": "volatility_20"}, "var": "vol_zscore"}
  ],
  "expression": "(vol_zscore < -1.0)",  // Z-score < -1，表示低于均值1个标准差
  "confidence_formula": "-vol_zscore"  // Z-score越小，置信度越高
}
```

**✅ 正确示例3 - 使用专业指标Beta**:
```json
{
  "name": "low_beta",
  "tools": [
    {"tool": "beta", "params": {"window": 60}, "var": "beta_60"}
  ],
  "expression": "(beta_60 < 1.0)",  // Beta < 1，系统性风险低于市场
  "confidence_formula": "1.0 / (beta_60 + 0.1)"
}
```

### 6. 低波动高阿尔法策略
**关键词**: 低波动、跑赢大盘、Beta、Alpha  
**示例**: `(beta < 1.0) & (alpha > 0)`  
**工具**: `beta(window=60)`, `alpha(window=60)`

### 7. 信息比率选股
**关键词**: 信息比率、风险调整后收益  
**示例**: `(information_ratio > 0.5) & (tracking_error < 0.1)`  
**工具**: `information_ratio(window=60)`, `tracking_error(window=60)`

### 8. 跑赢大盘天数
**关键词**: 跑赢大盘、超额收益天数  
**示例**: `(outperform_rate > 40)`  （60天内跑赢40天以上）  
**工具**: `outperform_rate(window=60)`

## 关键规则

**⚠️ 重要提示**：详细的规范和标准请参考以下文档：
- **表达式设计规范**：`.stock_asking/rules/expression-design.md`
- **工具返回值范围**：`.stock_asking/rules/tool-value-ranges.md`
- **质量标准**：`.stock_asking/rules/quality-criteria.md`
- **数据质量规则**：`.stock_asking/rules/data-quality.md`

**核心要点**：
1. **参数命名**: 所有工具第一个参数必须是 `values` 或 `column`
2. **变量一致性**: expression 中的变量名必须与 tools 定义的 `var` 完全一致
3. **百分比**: 用小数表示 (3% = 0.03)
4. **质量标准**: 候选数量 10-30 个为最佳
5. **注意**: 行业、ST、停牌、市值等过滤已由 StockPoolService 统一处理，无需在策略中重复

## 常见错误
- ❌ 使用不存在的字段 (`volume` → 应为 `vol`)
- ❌ 百分比用整数 (5 → 应为 0.05)
- ❌ 参数名错误 (`period` → 应为 `window`)
- ❌ **量纲错误**: 
  - `(volatility_20 < 0.03)` → 绝对标准差单位是元，0.03元无意义
  - `(volatility_20 / close < 0.10)` → **禁止随意除法**，变异系数需要明确的金融含义
  - **正确做法**: 使用 `zscore_normalize`、`rank_normalize` 或专业指标如 `beta`
- ❌ 在 screening_logic 中重复行业/ST/市值过滤（已由 StockPoolService 处理）
- ❌ **工具返回值范围错误**: 详见 `.stock_asking/rules/tool-value-ranges.md`

## 相关资源

- **策略模式参考**：`.stock_asking/skills/strategy-patterns/SKILL.md`
- **质量评估标准**：`.stock_asking/rules/quality-criteria.md`
- **数据质量规则**：`.stock_asking/rules/data-quality.md`
- **表达式设计规范**：`.stock_asking/rules/expression-design.md`
- **工具返回值范围**：`.stock_asking/rules/tool-value-ranges.md`
