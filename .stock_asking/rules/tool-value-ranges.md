---
name: tool-value-ranges
description: 所有工具的返回值范围和合理阈值设置指南。当需要设置筛选条件阈值时必须参考此文档。
tags:
  - 工具
  - 阈值
  - 范围
---

# 工具返回值范围指南

## ⚠️ 关键规则：必须根据工具的取值范围设置合理的阈值！

### 指数相关指标

| 工具 | 返回值范围 | 合理阈值示例 | 说明 |
|------|-----------|------------|------|
| `outperform_rate` | **0-1** | `>0.5` | 跑赢比例，0.7表示70%时间跑赢 |
| `beta` | 通常 0-2 | `<1.2` | <1低波动，>1高波动 |
| `alpha` | 小数 | `>-0.01` | 0.01表示1%超额收益 |
| `correlation` | **-1 到 1** | `>0.5` | 相关系数 |
| `tracking_error` | 0-0.5 | `<0.15` | 年化跟踪误差 |
| `information_ratio` | -2 到 2 | `>0.5` | 信息比率 |

### 技术指标

| 工具 | 返回值范围 | 合理阈值示例 | 说明 |
|------|-----------|------------|------|
| `rsi` | **0-100** | `30-70` | 相对强弱指标 |
| `macd` | 可正可负 | `>0` | 取决于趋势 |
| `volatility` | 0-1 | `<0.3` | 年化波动率 |
| `rolling_mean` | 同输入列 | - | 移动平均 |
| `pct_change` | 小数 | `>0.03` | 3%涨跌幅 |

### ❌ 常见错误

```python
# 错误：outperform_rate 不可能大于1
(outperform_60 > 30)

# 错误：RSI 不可能超过100
(rsi > 150)

# 错误：相关系数不可能超过1
(correlation > 1.5)
```

### ✅ 正确示例

```python
# 正确：使用0-1范围
(outperform_60 > 0.5)

# 正确：RSI在合理区间
(rsi > 30) & (rsi < 70)

# 正确：相关系数在-1到1之间
(correlation > 0.5)
```

## 与其他规则的关联

- **表达式设计规范**: 见 `.stock_asking/rules/expression-design.md`
- **质量标准**: 见 `.stock_asking/rules/quality-criteria.md`

## 🔧 自动化验证

系统会在 `run_screening` 工具执行后自动验证阈值合理性：

1. **Hook 脚本**: `.stock_asking/hooks/validate-thresholds.py`
2. **触发时机**: PostToolUse 阶段（工具执行后立即检查）
3. **验证规则**: 基于本文档定义的工具返回值范围
4. **退出码**:
   - `0`: 验证通过 ✅
   - `1`: 警告（阈值接近边界）⚠️
   - `2`: 阻止（阈值明显错误）❌

### 验证示例

```bash
# ❌ 错误：outperform_rate > 1.5（超过最大值1）
# Hook 会返回 exit code 2，阻止执行

# ✅ 正确：outperform_rate > 0.5（在合理范围内）
# Hook 会返回 exit code 0，允许继续
```

### 配置位置

Hook 配置在 `app/setting/screening.yaml`:

```yaml
harness:
  hooks:
    PostToolUse:
      - matcher: "run_screening"
        hooks:
          - type: command
            command: "python .stock_asking/hooks/validate-thresholds.py"
```
