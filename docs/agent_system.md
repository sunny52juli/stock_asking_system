# Agent System - 智能体系统

> 基于LLM的智能决策引擎，理解用户意图并生成可执行的量化策略。

## 📖 概述

Agent System 是系统的核心智能层，通过大语言模型（LLM）理解用户的自然语言查询，自动生成股票筛选策略，并协调各个组件完成数据加载、筛选执行和结果返回。

### 核心特性

- 🤖 **双模式架构**：Deep Thinking Mode（深度思考）和 Quick Mode（快速响应）
- 🧠 **长期记忆**：跨会话持久化，记住用户偏好和历史经验
- 🎯 **Skills 系统**：三层渐进式技能加载，按需激活专业知识
- 🛡️ **Harness 框架**：Hooks/Rules/Permissions 三层约束机制
- 🔄 **智能重试**：质量评估驱动的自动优化循环
- 🔧 **工具集成**：统一管理 MCP 远程工具和本地 Bridge 工具

## 🏗️ 架构设计

```
┌──────────────────────────────────────────┐
│         User Query (Natural Language)    │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│        Agent Factory                      │
│  • Deep Thinking Mode                     │
│  • Quick Mode                             │
└──────────────┬────────────────────────────┘
               │
┌──────────────▼────────────────────────────┐
│       Harness Framework                    │
│  • Hooks (PreToolUse/PostToolUse/Stop)   │
│  • Rules (.md → system prompt)           │
│  • Permissions (allow/deny)              │
└──────────────┬────────────────────────────┘
               │
┌──────────────▼────────────────────────────┐
│        Tool Layer                          │
│  • Bridge Tools (本地Python函数)          │
│  • MCP Server Tools (远程量化工具)        │
└──────────────┬────────────────────────────┘
               │
┌──────────────▼────────────────────────────┐
│      Quality & Retry System                │
│  • Quality Evaluator                      │
│  • Smart Retry Manager                    │
│  • Auto-fix Loop                          │
└──────────────────────────────────────────┘
```

## 📁 目录结构

```
src/agent/
├── __init__.py                     # 包入口
│
├── core/                           # 核心编排层 ⭐
│   ├── __init__.py
│   ├── orchestrator.py            # 主编排器 ScreenerOrchestrator
│   ├── agent_factory.py           # Agent 工厂
│   └── subagent.py                # 子 Agent
│
├── initialization/                 # 初始化模块 ⭐
│   ├── __init__.py
│   ├── component_initializer.py   # 组件初始化器
│   └── data_loader.py             # 数据加载器
│
├── execution/                      # 执行层 ⭐
│   ├── __init__.py
│   ├── query_executor.py          # 查询执行器
│   ├── agent_phases.py            # Agent 执行阶段
│   └── planner.py                 # 任务规划器
│
├── quality/                        # 质量管理 ⭐
│   ├── __init__.py
│   ├── evaluator.py               # 质量评估器
│   └── retry_manager.py           # 智能重试管理器
│
├── harness/                        # 约束框架 ⭐
│   ├── __init__.py
│   ├── hooks.py                   # Hooks 执行器
│   ├── rules.py                   # Rules 加载器
│   └── permissions.py             # 权限检查器
│
├── tools/                          # 工具提供者
│   ├── __init__.py
│   ├── bridge.py                  # Bridge 工具实现
│   └── provider.py                # 工具提供者
│
├── context/                        # 上下文管理
│   ├── __init__.py
│   ├── skills.py                  # Skills 注册表
│   └── prompts.py                 # Prompt 模板
│
├── memory/                         # 记忆系统
│   ├── __init__.py
│   ├── long_term.py               # 长期记忆 (SQLite)
│   └── short_term.py              # 短期记忆
│
├── models/                         # 数据模型
│   └── screening_logic.py         # 筛选逻辑模型
│
├── security/                       # 安全管理
│   ├── __init__.py
│   └── ...                        # 安全检查相关
│
├── services/                       # 服务层
│   └── stock_pool_service.py      # 股票池服务
│
├── generators/                     # 代码生成器
│   ├── __init__.py
│   └── screening_script_generator.py  # 筛选脚本生成器
│
├── config.py                       # Agent 配置模型
└── telemetry.py                    # 遥测监控
```

## 🔧 核心组件

### 1. Agent Factory（Agent 工厂）

根据配置创建不同模式的 Agent。

#### 双模式架构

| 模式 | 配置 | 特点 | 适用场景 |
|------|------|------|----------|
| **Deep Thinking Mode** | `deep_thinking=true` | 使用 `deepagents` 框架，包含任务规划、Skills渐进加载、长期记忆 | 复杂策略挖掘场景 |
| **Quick Mode** | `deep_thinking=false` | 使用 LangGraph ReAct Agent，无任务规划，响应更快 | 简单查询场景 |

**使用示例**：

```python
from src.agent.core import create_screener_agent

# 创建深度思考模式的 Agent
agent = create_screener_agent(
    deep_thinking=True,
    model="deepseek-chat",
    temperature=0.7
)

# 创建快速模式的 Agent
agent = create_screener_agent(
    deep_thinking=False,
    model="gpt-4",
    temperature=0.5
)
```

### 2. Orchestrator（编排器）

ScreenerOrchestrator 是 Agent 系统的主控制器，负责协调所有组件。

**核心职责**：
- 初始化所有组件（数据加载、Harness、质量评估器等）
- 管理会话生命周期
- 协调查询执行流程
- 处理错误和重试

**使用示例**：

```python
from src.agent.core import ScreenerOrchestrator

# 创建编排器
orchestrator = ScreenerOrchestrator()

# 初始化
orchestrator.initialize()

# 执行查询
result = orchestrator.run_query("帮我找放量突破的股票")
```

### 3. Harness Framework（约束框架）

提供三层约束机制，确保 Agent 执行过程安全可控。

#### 3.1 Hooks Engine（钩子系统）

三阶段钩子拦截机制：

- **PreToolUse**：工具调用前验证
- **PostToolUse**：工具调用后验证
- **Stop**：结果返回前质量门禁

**Exit Code 协议**：

| Code | 含义 | 行为 |
|------|------|------|
| `0` | 通过 | 继续执行 |
| `1` | 警告 | 继续执行，记录警告 |
| `2` | 阻止 | 终止执行，错误信息返回给 Agent |

**配置示例**（`screening.yaml`）：

```yaml
harness:
  hooks:
    PreToolUse:
      - matcher: "run_screening"
        hooks:
          - type: command
            command: "python .stock_asking/hooks/validate-strategy.py"
    Stop:
      - hooks:
          - type: command
            command: "python .stock_asking/hooks/quality-gate.py"
```

**Hook 脚本示例**（`.stock_asking/hooks/validate-strategy.py`）：

```python
#!/usr/bin/env python3
import json
import sys

def validate_strategy(payload: dict) -> tuple[int, str]:
    tool_input = payload.get("tool_input", {})
    
    # 检查必需字段
    if "strategy_name" not in tool_input:
        return 2, "Missing required field: strategy_name"
    
    return 0, "Validation passed"

if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        exit_code, message = validate_strategy(payload)
        
        if exit_code != 0:
            print(message, file=sys.stderr)
        
        sys.exit(exit_code)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
```

#### 3.2 Rules Loader（规则引擎）

从 Markdown 文件加载业务规则并注入到 system prompt。

**规则文件位置**：`.stock_asking/rules/*.md`

**示例规则**：
- `data-quality.md`：数据质量规则（禁止未来函数、停牌过滤等）
- `risk-control.md`：风险控制规则（行业集中度、极端值过滤等）

**加载流程**：

```
RulesLoader.load() 
  ↓
读取 .stock_asking/rules/*.md
  ↓
格式化为 system prompt 片段
  ↓
合并到 Agent 初始提示词
```

**使用示例**：

```python
from src.agent.harness import RulesLoader
from pathlib import Path

config_dir = Path(".stock_asking")
rules = RulesLoader.load(config_dir)

# rules 是字典：{rule_name: rule_content}
for name, content in rules.items():
    print(f"Rule: {name}")
    print(content[:100])  # 打印前100字符
```

#### 3.3 Permissions（权限控制）

基于 fnmatch 通配符的工具白名单/黑名单机制。

**配置示例**：

```yaml
permissions:
  allow: ["*"]              # 允许所有工具
  deny: ["dangerous_tool_*"] # 禁止特定工具
```

> **优先级**：deny > allow

**使用示例**：

```python
from src.agent.harness import PermissionChecker
from src.agent.config import PermissionConfig

config = PermissionConfig(
    allow=["run_screening", "get_stock_data"],
    deny=["delete_*"]
)

checker = PermissionChecker.from_config(config)

# 检查权限
if checker.is_allowed("run_screening"):
    print("✅ 允许执行")
else:
    print("❌ 禁止执行")
```

### 4. Quality & Retry System（质量与重试系统）

#### 4.1 Quality Evaluator（质量评估器）

对 Agent 输出进行多维度评分。

**评估维度**：
- **结果完整性**：是否包含必需字段
- **数量合理性**：筛选结果数量是否在合理范围
- **逻辑一致性**：筛选条件与用户需求是否匹配
- **数据有效性**：是否存在异常值或缺失

**输出示例**：

```python
{
    "score": 0.85,
    "issues": ["结果数量过少"],
    "suggestions": ["放宽成交量阈值"],
    "should_retry": True
}
```

**使用示例**：

```python
from src.agent.quality import ScreeningQualityEvaluator

evaluator = ScreeningQualityEvaluator(rules_dir="app/setting/rules")

# 评估结果质量
quality = evaluator.evaluate(
    query="帮我找放量突破的股票",
    result={"stocks": [...], "logic": {...}}
)

print(f"质量评分: {quality['score']}")
print(f"问题: {quality['issues']}")
print(f"建议: {quality['suggestions']}")
```

#### 4.2 Smart Retry Manager（智能重试管理器）

基于错误类型识别的自适应重试机制。

**错误分类**：

| 类型 | 说明 | 是否可重试 |
|------|------|------------|
| **可重试错误** | 参数验证失败、超时、无结果、工具执行错误 | ✅ |
| **不可重试错误** | 配置错误、权限不足 | ❌ |

**自适应调整策略**：
- 参数验证失败 → 调整参数范围
- 无结果 → 放宽筛选条件（降低阈值、扩大时间窗口）
- 超时 → 减少数据量或简化计算

**持久化学习**：
- 重试记录存储到 SQLite (`memory.db`)
- Agent 可参考历史重试经验优化策略

**使用示例**：

```python
from src.agent.quality import get_retry_manager

retry_manager = get_retry_manager()

# 记录错误
adjusted_params = retry_manager.record_error(
    error=ValueError("参数无效"),
    tool_name="rolling_mean",
    original_params={"window": 100}
)

print(f"调整后参数: {adjusted_params}")
# {'window': 50}  # 自动减小窗口
```

#### 4.3 Auto-fix Loop（自动修复循环）

当检测到质量问题时，系统自动触发优化循环。

**工作流程**：

```python
result = agent.execute(query)
quality = quality_evaluator.evaluate(result)

if quality.should_retry:
    for attempt in range(max_retries):
        # 构建优化提示
        optimization_prompt = f"""
        原查询: {query}
        发现问题: {quality.issues}
        建议优化: {quality.suggestions}
        请调整筛选条件并重试
        """
        
        result = agent.execute(optimization_prompt)
        quality = quality_evaluator.evaluate(result)
        
        if not quality.should_retry:
            break
```

**实际效果**：
- ✅ 首次筛选结果为空 → 自动放宽条件重试
- ✅ 结果数量过多 → 自动增加过滤条件
- ✅ 逻辑不一致 → 重新生成筛选表达式

### 5. Tool Layer（工具层）

#### 5.1 Bridge Tools（桥接工具）

在宿主进程中运行的本地 Python 函数，可以访问已加载的数据。

**核心工具**：

- **run_screening**: 在本地数据上执行筛选
- **get_available_industries**: 获取当前数据中的行业列表
- **save_screening_script**: 保存筛选脚本

**使用示例**：

```python
from src.agent.tools.bridge import run_screening

# 执行筛选
result = run_screening(
    screening_logic={
        "expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03)",
        "tools": [
            {"name": "rolling_mean", "params": {"column": "vol", "window": 20}},
            {"name": "pct_change", "params": {"column": "close", "periods": 1}}
        ]
    },
    top_n=20
)

print(f"筛选出 {len(result['stocks'])} 只股票")
```

#### 5.2 MCP Server Tools（MCP 工具）

通过 MCP 协议调用的远程量化工具服务。

**工具分类**：
- 数据查询工具
- 指标计算工具
- 策略执行工具

### 6. Memory System（记忆系统）

#### 6.1 Long-term Memory（长期记忆）

基于 SQLite 的跨会话持久化记忆。

**存储内容**：
- 用户偏好
- 历史查询记录
- 重试经验
- 成功案例

**使用示例**：

```python
from src.agent.memory import get_long_term_memory

memory = get_long_term_memory()

# 保存记忆
memory.save({
    "type": "preference",
    "content": "用户偏好短线技术面分析",
    "timestamp": "2024-01-01T00:00:00"
})

# 检索相关记忆
memories = memory.search("技术分析", limit=5)
```

#### 6.2 Short-term Memory（短期记忆）

会话级别的临时记忆，会话结束后自动清除。

### 7. Skills System（技能系统）

三层渐进式技能加载系统，按需激活专业知识。

**技能层级**：
1. **基础技能**：始终加载（如数据访问、基本筛选）
2. **领域技能**：根据查询类型加载（如技术分析、基本面分析）
3. **高级技能**：按需加载（如复杂策略、回测验证）

**技能文件位置**：`src/agent/skills/*/SKILL.md`

**使用示例**：

```markdown
# SKILL.md - 技术分析技能

## 适用场景
- 用户询问技术指标相关策略
- 需要分析量价关系

## 可用指标
- MA (移动平均线)
- MACD (指数平滑异同移动平均线)
- RSI (相对强弱指标)
- VOL (成交量)

## 使用示例
...
```

## 💡 使用示例

### 示例 1：执行简单查询

```python
from src.agent.core import ScreenerOrchestrator

# 创建并初始化编排器
orchestrator = ScreenerOrchestrator()
orchestrator.initialize()

# 执行查询
result = orchestrator.run_query("帮我找放量突破的股票")

# 查看结果
print(f"筛选出 {len(result['stocks'])} 只股票")
for stock in result['stocks'][:5]:
    print(f"- {stock['name']} ({stock['ts_code']})")
```

### 示例 2：自定义 Agent 配置

```python
from src.agent.core import create_screener_agent

# 创建深度思考模式的 Agent
agent = create_screener_agent(
    deep_thinking=True,
    model="deepseek-chat",
    temperature=0.7,
    max_iterations=25
)

# 使用自定义配置
result = agent.invoke({
    "messages": [{"role": "user", "content": "找出低估值高分红的股票"}]
})
```

### 示例 3：使用 Hooks 验证策略

```python
# .stock_asking/hooks/validate-strategy.py
#!/usr/bin/env python3
import json
import sys

def validate_strategy(payload: dict) -> tuple[int, str]:
    tool_input = payload.get("tool_input", {})
    
    # 检查必需字段
    if "strategy_name" not in tool_input:
        return 2, "Missing strategy_name"
    
    if len(tool_input.get("strategy_name", "")) > 100:
        return 2, "Strategy name too long"
    
    return 0, "OK"

if __name__ == "__main__":
    payload = json.load(sys.stdin)
    exit_code, message = validate_strategy(payload)
    
    if exit_code != 0:
        print(message, file=sys.stderr)
    
    sys.exit(exit_code)
```

## ⚙️ 配置说明

Agent 的配置分布在 `setting/` 目录下的多个配置文件中：

```yaml
# LLM 配置
llm:
  model: "deepseek-chat"
  api_key: "${DEFAULT_API_KEY}"
  temperature: 0.7
  max_tokens: 4096

# Harness 配置
harness:
  max_iterations: 25
  max_consecutive_errors: 3
  max_execution_time: 300
  deep_thinking: false
  
  hooks:
    PreToolUse:
      - matcher: "run_screening"
        hooks:
          - type: command
            command: "python .stock_asking/hooks/validate-strategy.py"
    Stop:
      - hooks:
          - type: command
            command: "python .stock_asking/hooks/quality-gate.py"

# 权限配置
permissions:
  allow: ["*"]
  deny: []

# 回测配置
backtest:
  holding_periods: [4, 10, 20]
  observation_days: 80
```

## 🧪 测试

运行 Agent 相关测试：

```bash
# 运行所有 Agent 测试
pytest tests/src/agent/ -v

# 运行特定模块测试
pytest tests/src/agent/test_config.py -v
pytest tests/src/agent/test_agent_phases.py -v

# 带覆盖率报告
pytest tests/src/agent/ --cov=src.agent --cov-report=html
```

## 🔌 扩展开发

### 添加新的 Hook

1. 创建 Hook 脚本（`.stock_asking/hooks/my_hook.py`）：

```python
#!/usr/bin/env python3
import json
import sys

def my_hook(payload: dict) -> tuple[int, str]:
    # 实现验证逻辑
    return 0, "OK"

if __name__ == "__main__":
    payload = json.load(sys.stdin)
    exit_code, message = my_hook(payload)
    
    if exit_code != 0:
        print(message, file=sys.stderr)
    
    sys.exit(exit_code)
```

2. 在 `screening.yaml` 中配置：

```yaml
harness:
  hooks:
    PreToolUse:
      - matcher: "my_tool"
        hooks:
          - type: command
            command: "python .stock_asking/hooks/my_hook.py"
```

### 添加新的 Rule

1. 创建规则文件（`.stock_asking/rules/my_rule.md`）：

```markdown
# 我的规则

## 规则描述
...

## 具体要求
- 要求1
- 要求2
```

2. 规则会自动被 RulesLoader 加载并注入到 system prompt。

### 添加新的 Skill

1. 创建技能目录（`src/agent/skills/my_skill/`）
2. 创建 `SKILL.md` 文件
3. 在技能文件中定义使用场景和示例

### 自定义质量评估器

```python
from src.agent.quality import BaseQualityEvaluator

class MyQualityEvaluator(BaseQualityEvaluator):
    def evaluate(self, query: str, result: dict) -> dict:
        # 实现自定义评估逻辑
        return {
            "score": 0.9,
            "issues": [],
            "suggestions": [],
            "should_retry": False
        }
```

## 📊 性能优化建议

1. **选择合适的模式**：简单查询使用 Quick Mode，复杂策略使用 Deep Thinking Mode
2. **限制迭代次数**：设置合理的 `max_iterations`，避免无限循环
3. **利用缓存**：启用长期记忆，减少重复计算
4. **优化 Prompts**：精简 system prompt，减少 Token 消耗

## 🔗 相关文档

- [主 README](../README.md)
- [DataHub](./datahub.md)
- [Screening Engine](./screening_engine.md)
- [Backtest Engine](./backtest_engine.md)
- [MCP Server](./mcp_server.md)

## 📝 更新日志

- **2024-01**: 初始版本，实现基础 Agent 功能
- **2024-02**: 添加 Harness 框架（Hooks/Rules/Permissions）
- **2024-03**: 实现质量评估与智能重试系统
- **2024-04**: 重构为模块化架构（core/execution/quality/harness）
