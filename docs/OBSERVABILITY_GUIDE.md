# 观测与记忆系统使用指南

## 📋 概述

观测与记忆系统（Observability & Memory System）为股票筛选系统提供了完整的可观测性和长期记忆能力。

### 核心功能

1. **Telemetry（遥测）**：性能追踪、查询统计、工具调用监控
2. **Long-term Memory（长期记忆）**：策略历史存储、智能推荐、经验学习

---

## 🚀 快速开始

### 1. 初始化

```python
from pathlib import Path
from src.agent.observability import get_observability

# 获取全局实例
obs = get_observability(
    enabled=True,  # 是否启用
    project_root=Path("/path/to/project")  # 项目根目录
)
```

### 2. 追踪查询执行

```python
query = "找出高波动且持续跑赢大盘的股票"

# 使用上下文管理器自动追踪
with obs.trace_query(query, query_id=1):
    result = execute_screening(query)
    
    # 记录工具调用
    obs.record_tool_call("beta_60", window=60)
    obs.record_tool_call("outperform_rate_60", index="000300.SH")

# 记录查询结果
obs.record_query_result(query, success=True)
```

### 3. 保存策略到长期记忆

```python
obs.record_strategy(
    query=query,
    strategy_name="high_volatility_outperform",
    screening_logic={
        "expression": "beta_60 > 1.2 and outperform_rate_60 > 0.5",
        "tools": [...]
    },
    candidates_count=15,
    success=True,
    notes="首次测试策略"
)
```

### 4. 搜索历史策略

```python
# 获取相似策略建议
suggestions = obs.get_strategy_suggestions("高波动", limit=3)
for strategy in suggestions:
    print(f"{strategy.strategy_name}: {strategy.query}")

# 获取最近策略
recent = obs.get_recent_strategies(limit=5)
```

### 5. 打印会话摘要

```python
obs.print_summary()
```

输出示例：
```
============================================================
[TELEMETRY] 会话统计摘要
============================================================
   总查询数：5
   成功数：4
   失败数：1
   成功率：80.0%
   平均耗时：28500.0ms
   工具调用次数：12
============================================================
[MEMORY] 最近保存的策略
============================================================
   1. high_volatility_outperform
      查询: 找出高波动且持续跑赢大盘的股票...
      候选: 15 只
============================================================
```

---

## 📊 数据存储

### Telemetry 数据

- **位置**：`.stock_asking/traces/`
- **格式**：JSON文件
- **内容**：
  - `trace_<timestamp>_<operation>.json` - 每次操作的详细记录
  - `session_stats.json` - 会话统计数据

**示例trace文件**：
```json
{
  "operation": "execute_query",
  "start_time": 1778413868.897,
  "end_time": 1778413921.414,
  "duration_ms": 52516.94,
  "status": "success",
  "metadata": {
    "query_id": 1,
    "query": "找出高波动股票"
  },
  "error": null
}
```

### Long-term Memory 数据

- **位置**：`.stock_asking/memory.db`
- **格式**：SQLite数据库
- **表结构**：
  ```sql
  CREATE TABLE strategy_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      query TEXT NOT NULL,
      strategy_name TEXT NOT NULL,
      screening_logic TEXT NOT NULL,
      candidates_count INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      success BOOLEAN DEFAULT 1,
      notes TEXT DEFAULT ''
  )
  ```

---

## 💡 最佳实践

### 1. 在查询前检查历史策略

```python
# 提取关键词
keyword = query.split()[0] if query.split() else query

# 查找相似策略
suggestions = obs.get_strategy_suggestions(keyword, limit=2)
if suggestions:
    print(f"[MEMORY] 发现 {len(suggestions)} 个相似历史策略:")
    for i, strategy in enumerate(suggestions, 1):
        print(f"   {i}. {strategy.strategy_name} - {strategy.query[:60]}")
```

### 2. 保存成功的策略

```python
if result.get("success") and candidates:
    # 保存脚本
    script_path = save_strategy_script(...)
    
    # 记录到长期记忆
    obs.record_strategy(
        query=query,
        strategy_name=strategy_name,
        screening_logic=last_logic,
        candidates_count=len(candidates),
        success=True
    )
    obs.record_query_result(query, success=True, script_path=script_path)
```

### 3. 记录失败的查询

```python
if not result.get("success"):
    obs.record_query_result(query, success=False)
```

### 4. 会话结束时打印摘要

```python
try:
    # 主循环
    while True:
        ...
finally:
    # 打印统计
    obs.print_summary()
    obs.close()
```

---

## 🔧 API参考

### ObservabilityManager

#### 初始化
```python
obs = ObservabilityManager(enabled=True, project_root=Path(...))
```

#### 方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `trace_query(query, **metadata)` | 追踪查询执行（上下文管理器） | query: 查询字符串, metadata: 额外元数据 |
| `record_strategy(...)` | 保存策略到长期记忆 | query, strategy_name, screening_logic, candidates_count, success, notes |
| `get_strategy_suggestions(keyword, limit)` | 获取相似策略建议 | keyword: 搜索关键词, limit: 返回数量 |
| `get_recent_strategies(limit)` | 获取最近策略 | limit: 返回数量 |
| `record_tool_call(tool_name, **metadata)` | 记录工具调用 | tool_name: 工具名称, metadata: 额外元数据 |
| `record_query_result(query, success, script_path)` | 记录查询结果 | query: 查询, success: 是否成功, script_path: 脚本路径 |
| `print_summary()` | 打印会话摘要 | - |
| `close()` | 关闭资源 | - |

---

## 🎯 实际应用场景

### 场景1：避免重复探索

用户输入："找低估值高分红的股票"

系统检测到历史有类似策略：
```
[MEMORY] 发现 2 个相似历史策略:
   1. value_dividend_strategy - 低估值高分红蓝筹股筛选
   2. dividend_yield_focus - 高股息率股票筛选
```

用户可以直接复用或基于历史策略优化。

### 场景2：性能分析

会话结束时显示：
```
[TELEMETRY] 会话统计摘要
   总查询数：10
   成功率：90.0%
   平均耗时：25秒
   
[TIP] 发现3次超时，建议简化查询条件
```

### 场景3：策略库积累

经过多次使用后，`.stock_asking/memory.db`中积累了大量策略：
- 可以按关键词搜索
- 可以查看历史成功率
- 可以分析哪些策略类型最有效

---

## ⚙️ 配置选项

### 启用/禁用

```python
# 完全禁用（零开销）
obs = get_observability(enabled=False)

# 生产环境启用
obs = get_observability(enabled=True)
```

### 自定义路径

```python
# 自定义项目根目录
obs = get_observability(
    enabled=True,
    project_root=Path("/custom/path")
)
```

---

## 🐛 故障排查

### 问题1：memory.db为空

**原因**：未调用`record_strategy()`

**解决**：确保在保存策略时调用：
```python
obs.record_strategy(...)
```

### 问题2：traces目录没有文件

**原因**：未使用`trace_query()`上下文管理器

**解决**：
```python
with obs.trace_query(query):
    result = execute_query()
```

### 问题3：搜索不到历史策略

**原因**：关键词不匹配

**解决**：使用更通用的关键词：
```python
# 不好
obs.get_strategy_suggestions("高波动beta大于1.2")

# 好
obs.get_strategy_suggestions("高波动")
```

---

## 📝 更新日志

### v1.0 (2026-05-10)
- ✅ 初始版本
- ✅ 集成Telemetry和Long-term Memory
- ✅ 自动追踪查询执行
- ✅ 智能推荐历史策略
- ✅ 会话统计摘要
