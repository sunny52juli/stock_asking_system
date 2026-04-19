# 筛选表达式设计规范

## 核心原则：避免硬编码绝对阈值

### ❌ 错误做法：硬编码绝对值

```python
# 错误：固定阈值无法适应不同市场环境
(volatility_20d < 0.02) & (return_20d > 0.01)
(close > ma20 * 1.05)
(pe_ttm < 30)
```

**问题**：
- 不同市场环境下波动率差异巨大（牛市 vs 熊市）
- 不同板块特性不同（科技股 vs 银行股）
- 固定阈值要么过于严格（无结果），要么过于宽泛（太多结果）

### ✅ 正确做法：使用相对指标

#### 1. 与历史均值比较
```python
# 当前波动率低于自身历史平均水平
volatility_20d < volatility_ma60

# 当前收益率高于自身历史平均
return_20d > return_ma60
```

#### 2. 使用分位数/排名
```python
# 波动率处于全市场最低 30%
volatility_rank < 0.3

# 收益率处于全市场最高 20%
return_rank > 0.8
```

#### 3. 相对于指数表现
```python
# 跑赢指数（超额收益为正）
excess_return > 0

# 波动率低于指数
volatility_20d < index_volatility

# Beta 值合理（不过于激进）
beta < 1.2
```

#### 4. 技术指标的相对位置
```python
# 价格在均线之上（趋势向上）
close > ma20

# RSI 处于合理区间（非超买超卖）
(rsii > 30) & (rsi < 70)

# 成交量放大
volume_ratio > 1.5
```

## ⚠️ 重要：表达式与工具的对应关系

### 表达式只能使用已定义的变量

**表达式中的每个变量必须在 `tools` 列表中有对应的定义！**

#### ❌ 错误示例

```json
{
  "expression": "rolling_mean(close, 20) > close",
  "tools": [
    {"var": "ma20", "tool": "rolling_mean", "params": {"column": "close", "window": 20}}
  ]
}
```

**错误原因**：
- 表达式中使用了 `rolling_mean(close, 20)`，但 `rolling_mean` 是工具函数名，不是变量
- `tools` 中定义了变量 `ma20`，但表达式中没有使用它

#### ✅ 正确示例

```json
{
  "expression": "ma20 > close",
  "tools": [
    {"var": "ma20", "tool": "rolling_mean", "params": {"column": "close", "window": 20}}
  ]
}
```

**正确做法**：
1. 在 `tools` 中定义变量：`{"var": "ma20", "tool": "rolling_mean", ...}`
2. 在表达式中使用变量名：`"expression": "ma20 > close"`

### 完整示例

#### 场景：低波动 + 跑赢大盘

```json
{
  "name": "低波动跑赢大盘",
  "expression": "(volatility_20d < volatility_ma60) & (excess_return > 0) & (close > ma20)",
  "confidence_formula": "rank_normalize(1 - volatility_rank) * 0.5 + rank_normalize(excess_return) * 0.5",
  "tools": [
    {"var": "volatility_20d", "tool": "volatility", "params": {"column": "close", "window": 20}},
    {"var": "volatility_ma60", "tool": "rolling_mean", "params": {"column": "volatility_20d", "window": 60}},
    {"var": "excess_return", "tool": "alpha", "params": {"window": 20}},
    {"var": "ma20", "tool": "rolling_mean", "params": {"column": "close", "window": 20}},
    {"var": "volatility_rank", "tool": "rank_normalize", "params": {"column": "volatility_20d"}}
  ]
}
```

**关键点**：
- 表达式中的 `volatility_20d`、`volatility_ma60`、`excess_return`、`ma20`、`volatility_rank` 都在 `tools` 中有定义
- 没有在表达式中直接使用工具函数名（如 `rolling_mean()`、`volatility()`）
- **工具执行顺序会自动调整**：系统会根据依赖关系进行拓扑排序，确保 `volatility_20d` 在 `volatility_ma60` 之前执行

### 🔀 工具依赖与自动排序

#### ⚠️ 重要：虽然系统会自动排序，但你仍应该按依赖顺序定义工具

**系统会自动进行拓扑排序**，但为了让 Agent 生成的代码更清晰、更易调试，**你应该在 `tools` 列表中按依赖顺序排列工具**。

#### 依赖关系识别规则

系统会检查工具参数中的字段（如 `column`）：
- **基础数据列**：`close`, `open`, `high`, `low`, `volume`, `pct_chg` 等 → 无依赖
- **工具生成变量**：如果参数值匹配其他工具的 `var` 名 → 存在依赖

```python
# 示例：volatility_ma60 依赖 volatility_20d
tools = [
    # ❌ 错误顺序：虽然系统会自动调整，但不符合人类阅读习惯
    {"var": "volatility_ma60", "tool": "rolling_mean", "params": {"column": "volatility_20d", "window": 60}},
    {"var": "volatility_20d", "tool": "volatility", "params": {"column": "close", "window": 20}},
]

# ✅ 正确顺序：先定义被依赖的工具
# 系统日志会显示：🔀 工具执行顺序调整：volatility_ma60 → volatility_20d 改为 volatility_20d → volatility_ma60
tools = [
    {"var": "volatility_20d", "tool": "volatility", "params": {"column": "close", "window": 20}},
    {"var": "volatility_ma60", "tool": "rolling_mean", "params": {"column": "volatility_20d", "window": 60}},
]
```

#### 📋 Agent 生成工具列表的检查清单

在生成 `tools` 列表时，请遵循以下顺序：

1. **基础指标**（无依赖）：直接从原始数据计算
   - `volatility_20d`, `return_20d`, `ma20`, `rsi`, `macd` 等
   
2. **派生指标**（依赖基础指标）：基于步骤1的结果
   - `volatility_ma60` (依赖 `volatility_20d`)
   - `return_ma60` (依赖 `return_20d`)
   
3. **标准化指标**（依赖前两步）：排名、归一化等
   - `volatility_rank` (依赖 `volatility_20d`)
   - `return_rank` (依赖 `return_20d`)

#### 实际示例

```json
{
  "name": "低波动跑赢大盘",
  "expression": "(volatility_20d < volatility_ma60) & (excess_return > 0) & (close > ma20)",
  "confidence_formula": "rank_normalize(1 - volatility_rank) * 0.5 + rank_normalize(excess_return) * 0.5",
  "tools": [
    // 第1层：基础指标（无依赖）
    {"var": "volatility_20d", "tool": "volatility", "params": {"column": "close", "window": 20}},
    {"var": "ma20", "tool": "rolling_mean", "params": {"column": "close", "window": 20}},
    {"var": "excess_return", "tool": "alpha", "params": {"window": 20}},
    
    // 第2层：派生指标（依赖第1层）
    {"var": "volatility_ma60", "tool": "rolling_mean", "params": {"column": "volatility_20d", "window": 60}},
    
    // 第3层：标准化指标（依赖第1层）
    {"var": "volatility_rank", "tool": "rank_normalize", "params": {"column": "volatility_20d"}}
  ]
}
```

#### 循环依赖检测

如果检测到循环依赖，系统会发出警告并尝试恢复：

```python
# ❌ 循环依赖示例（应避免）
tools = [
    {"var": "a", "tool": "rolling_mean", "params": {"column": "b", "window": 20}},
    {"var": "b", "tool": "rolling_mean", "params": {"column": "a", "window": 20}},
]
# 警告：⚠️ 检测到循环依赖或未解析的依赖：{'a', 'b'}
```

**Agent 应避免的错误**：
- ❌ 不要让两个工具相互依赖
- ❌ 不要在表达式中使用未定义的变量
- ✅ 确保依赖图是有向无环图（DAG）
- ✅ 按依赖层次组织工具列表

### 推荐的表达式模式

#### 模式 1：低波动 + 正收益
```python
(volatility_20d < volatility_ma60) & (return_20d > 0) & (close > ma20)
```

#### 模式 2：相对强势
```python
(return_rank > 0.7) & (volatility_rank < 0.4) & (excess_return > 0)
```

#### 模式 3：趋势跟随
```python
(close > ma20) & (ma20 > ma60) & (volume_ratio > 1.2)
```

#### 模式 4：估值合理 + 动量
```python
(pe_rank < 0.5) & (return_20d > 0) & (rsi > 40) & (rsi < 70)
```

### 置信度公式设计

#### ❌ 错误：直接使用原始值
```python
# 错误：不同量纲的值不能直接加权
volatility_20d * 0.6 + return_20d * 0.4
```

#### ✅ 正确：先标准化再加权
```python
# 使用 rank_normalize 转换为 0-1 范围
rank_normalize(1 - volatility_rank) * 0.6 + rank_normalize(return_rank) * 0.4

# 或使用相对指标
rank_normalize(1 - volatility_20d/volatility_ma60) * 0.6 + rank_normalize(excess_return) * 0.4
```

### 检查清单

在生成筛选逻辑前，请自检：

- [ ] 是否避免了硬编码绝对阈值（如 `< 0.02`、`> 0.01`）？
- [ ] 是否使用了相对指标（与历史比、与指数比、分位数）？
- [ ] **表达式中的所有变量是否都在 `tools` 列表中有定义？**
- [ ] **是否没有在表达式中直接使用工具函数名（如 `rolling_mean()`）？**
- [ ] 置信度公式是否使用了 `rank_normalize` 进行标准化？
- [ ] 表达式是否能在不同市场环境下自适应？
- [ ] 是否考虑了多个维度（波动、收益、趋势、估值）？

### 示例对比

#### 场景：寻找“稳健上涨”的股票

❌ **差的设计**：
```python
(volatility_20d < 0.03) & (return_20d > 0.01)
# 问题：0.03 和 0.01 是拍脑袋的值
```

✅ **好的设计**：
```python
(volatility_20d < volatility_ma60) & (return_20d > 0) & (close > ma20)
# 优势：自适应市场，波动低于自身历史，收益为正，趋势向上
```

✅ **更好的设计**：
```python
(volatility_rank < 0.4) & (return_rank > 0.6) & (excess_return > 0)
# 优势：使用分位数，自动适应市场分布，相对指数有超额收益
```
