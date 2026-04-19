# 系统架构总览

> stock_asking_system v2.0 - AI驱动的量化交易系统完整架构说明

## 📋 目录

- [1. 系统概述](#1-系统概述)
- [2. 分层架构](#2-分层架构)
- [3. 核心模块](#3-核心模块)
- [4. 数据流设计](#4-数据流设计)
- [5. 关键设计决策](#5-关键设计决策)

---

## 1. 系统概述

### 1.1 项目定位

面向个人投资者的**短线技术派量化工具**，基于 LLM 理解自然语言查询，自动生成并执行股票筛选策略，支持历史回测验证。

### 1.2 核心价值

- **零代码门槛**：用自然语言表达投资逻辑，无需编写 Python 代码
- **智能优化**：质量评估 + 自适应重试，自动调整筛选参数
- **高性能计算**：Polars 统一数据流，数据处理速度提升 3-4x
- **可追溯性**：自动生成 Python 脚本，便于审计和复用

### 1.3 技术亮点

| 特性 | 说明 |
|------|------|
| **Polars 统一流** | 从 datahub 到最终筛选，全程 Polars DataFrame，零转换开销 |
| **双模式 Agent** | Deep Thinking（复杂策略）/ Quick Mode（简单查询） |
| **Harness 约束** | Hooks/Rules/Permissions 三层约束框架 |
| **质量闭环** | Quality Evaluator → Smart Retry → Auto-fix |
| **模块化设计** | DataLoader / ComponentInitializer / QueryExecutor 职责分离 |

---

## 2. 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    Layer 1: Agent                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ DeepAgents   │  │ LangGraph    │  │ MCP Client   │  │
│  │ (深度思考)    │  │ (快速模式)    │  │ (工具调用)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Layer 2: Harness Framework                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Hooks Engine │  │ Rules Loader │  │ Permissions  │  │
│  │ (钩子系统)    │  │ (规则引擎)    │  │ (权限控制)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                 Layer 3: Tool Layer                      │
│  ┌──────────────────┐  ┌──────────────────────┐        │
│  │ Bridge Tools     │  │ MCP Server Tools     │        │
│  │ (本地Python函数)  │  │ (远程量化工具服务)     │        │
│  └──────────────────┘  └──────────────────────┘        │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│          Layer 4: Quality & Retry System                 │
│  ┌──────────────────┐  ┌──────────────────────┐        │
│  │ Quality Evaluator│  │ Smart Retry Manager  │        │
│  │ (质量评估器)      │  │ (智能重试管理器)      │        │
│  └──────────────────┘  └──────────────────────┘        │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Layer 5: Core Logic                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Screening    │  │ Backtest     │  │ Strategy     │  │
│  │ Engine       │  │ Engine       │  │ Generator    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                Layer 6: DataHub                          │
│  ┌────────┐ ┌──────┐ ┌───────┐ ┌──────┐ ┌──────────┐  │
│  │ Stock  │ │ Fund │ │ Index │ │News  │ │ Feature  │  │
│  └────────┘ └──────┘ └───────┘ └──────┘ └──────────┘  │
│           Repository Pattern + Parquet Cache            │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Layer 7: Infrastructure                     │
│  Config / Logging / Session / Telemetry / Retry         │
└─────────────────────────────────────────────────────────┘
```

### 各层职责

| 层级 | 职责 | 关键组件 |
|------|------|----------|
| **Agent** | LLM 决策引擎 | DeepAgents, LangGraph, MCP Client |
| **Harness** | 约束框架 | Hooks, Rules, Permissions |
| **Tool** | 工具抽象层 | Bridge Tools, MCP Server |
| **Quality & Retry** | 质量保障 | Quality Evaluator, Smart Retry |
| **Core Logic** | 业务逻辑 | Screening, Backtest, Strategy |
| **DataHub** | 数据访问 | Repository, Loaders, Cache |
| **Infrastructure** | 基础设施 | Config, Logging, Session |

---

## 3. 核心模块

### 3.1 ScreenerOrchestrator（编排器）

**位置**：`src/agent/core/orchestrator.py`

**职责**：协调整个系统的初始化和查询执行流程

**核心组件**：
```python
class ScreenerOrchestrator:
    # 数据加载
    data_loader: DataLoader
    
    # 组件初始化
    component_initializer: ComponentInitializer
    
    # 查询执行
    query_executor: QueryExecutor
    
    # 质量保障
    quality_evaluator: ScreeningQualityEvaluator
    retry_manager: RetryManager
    
    # Harness 约束
    hooks: HookExecutor
    
    # 可观测性
    telemetry: Telemetry
    session_manager: SessionManager
    planner: Planner
```

**初始化流程**：
```
1. DataLoader.load_raw_market_data()
   └─> 返回 (polars_df, stock_codes, index_data)

2. ComponentInitializer.initialize_all()
   ├─> LLM 客户端
   ├─> Skill Registry
   ├─> Long-term Memory
   └─> Tool Provider

3. ComponentInitializer.create_bridge_tools(data_fn, stock_codes)
   └─> 注册本地 Python 工具

4. QueryExecutor 创建
   └─> 传入 agent, hooks, quality_evaluator 等

5. （Deep Mode）预创建 Agent
```

**主函数调用** (`app/screener.py`)：
```python
# 1. 初始化
orchestrator = ScreenerOrchestrator(settings)
orchestrator.initialize()

# 2. 股票池过滤（独立服务）
stock_pool_service = StockPoolService(settings)
filtered_data, filtered_codes = stock_pool_service.apply_filter(orchestrator.data)

# 3. 更新工具和 Agent
orchestrator.data = filtered_data
orchestrator.stock_codes = filtered_codes
orchestrator.component_initializer.create_bridge_tools(...)

# 4. 执行查询
for query in queries:
    result = orchestrator.execute_query(query, query_id=i)
```

---

### 3.2 DataHub（数据层）

**位置**：`datahub/`

**架构**：Repository Pattern + Domain Entities

**核心组件**：

#### Repository 接口
```python
class Repository(ABC):
    def load(self, query: Query) -> pl.DataFrame: ...
    def save(self, dataset: Dataset, data: pl.DataFrame, partition_key: str) -> bool: ...
    def exists(self, dataset: Dataset, partition_key: str) -> bool: ...
```

#### 实现类
- `SyncRepository`: 同步仓储（本地缓存 + 远程数据源）
- `CacheRepository`: 纯缓存仓储

#### Data Loaders
- `StockDataLoader`: 股票数据加载器
- `FactorDataLoader`: 因子数据加载器

**数据流**：
```
Tushare API → SyncRepository → Parquet Cache → Polars DataFrame
```

**关键特性**：
- ✅ 返回 **Polars DataFrame**（v2.0）
- ✅ 日期分区缓存 (`data_cache/stock/daily/YYYYMMDD.parquet`)
- ✅ 自动增量同步

---

### 3.3 Screening Engine（筛选引擎）

**位置**：`src/screening/`

**处理流程**：
```
用户查询 → LLM 解析 → 筛选逻辑配置 
    → PreFilter (股票池过滤) 
    → BatchCalculator (指标计算) 
    → FilterEngine (表达式过滤) 
    → Top-N 排序 
    → ScriptSaver (生成脚本)
```

**核心组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| **ScreeningExecutor** | `executor.py` | 主入口，协调整个流程 |
| **StockPoolFilter** | `stock_pool_filter.py` | 股票池过滤（ST、停牌、市值等） |
| **BatchCalculator** | `batch_calculator.py` | 向量化批量计算技术指标 |
| **IndustryMatcher** | `industry_matcher.py` | 行业模糊匹配 |
| **ScriptSaver** | `script_saver.py` | 生成可复用 Python 脚本 |
| **ResultDisplayer** | `result_display.py` | 结果展示 |

**StockPoolFilter 过滤规则**：
```yaml
stock_pool:
  min_list_days: 180           # 最小上市天数
  exclude_st: true             # 排除 ST 股票
  exclude_suspended: true      # 排除停牌
  industry: ["半导体", "芯片"]  # 行业关键词（LLM 匹配）
  min_price: 5                 # 最低价格
  max_price: 100               # 最高价格
  min_total_mv: 50e9           # 最小总市值
  max_total_mv: 500e9          # 最大总市值
  min_completeness_ratio: 0.9  # 数据完整度
```

**性能优化**：
- ✅ Polars 向量化计算
- ✅ 并行处理多只股票
- ✅ 中间结果缓存

---

### 3.4 Backtest Engine（回测引擎）

**位置**：`src/backtest/`

**回测流程**：
```
加载历史数据 → 执行策略脚本 → 计算持有期收益 → 生成统计报告
```

**核心组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| **BacktestEngine** | `engine.py` | 主引擎，协调整个回测流程 |
| **ReturnsCalculator** | `returns.py` | 收益率计算 |
| **BacktestReport** | `report.py` | 报告生成 |
| **Utils** | `utils.py` | 辅助函数 |

**关键指标**：
- 年化收益率
- 胜率
- 最大回撤
- Sharpe 比率
- 盈亏比

**多持有期回测**：
```python
holding_periods = [4, 10, 20]  # 默认测试 4日/10日/20日
```

---

### 3.5 Agent System（智能体系统）

**位置**：`src/agent/`

#### 双模式架构

| 模式 | 框架 | 特点 | 适用场景 |
|------|------|------|----------|
| **Deep Thinking** | deepagents | 任务规划 + Skills + 长期记忆 | 复杂策略挖掘 |
| **Quick Mode** | LangGraph ReAct | 无任务规划，响应快 | 简单查询 |

**配置**：
```yaml
harness:
  deep_thinking: true  # 切换模式
```

#### Harness Framework（约束框架）

**三层约束**：

1. **Hooks Engine** (`src/agent/harness/hooks.py`)
   - PreToolUse: 工具调用前验证
   - PostToolUse: 工具调用后检查
   - Stop: 会话结束清理

2. **Rules Loader** (`.stock_asking/rules/*.md`)
   - Markdown 规则动态注入 system prompt
   - 示例：`screening_rules.md`, `backtest_rules.md`

3. **Permissions** (`.stock_asking/permissions.yaml`)
   - 工具白名单/黑名单
   - 支持 fnmatch 通配符

#### Quality & Retry System

**质量评估器** (`src/agent/quality/quality_evaluator.py`)：
```python
class ScreeningQualityEvaluator:
    def evaluate(self, result: dict) -> QualityScore:
        # 多维度评分
        - 结果完整性 (0-1)
        - 数量合理性 (0-1)
        - 逻辑一致性 (0-1)
```

**智能重试管理器** (`infrastructure/retry/manager.py`)：
```python
class SmartRetryManager:
    def execute_with_retry(self, tool_name, func, **params):
        # 错误分类
        - 参数验证错误 → 修正参数
        - 超时错误 → 增加 timeout
        - 无结果错误 → 放宽阈值
        - 配置错误 → 提示用户
        
        # 持久化学习 (SQLite)
        - 记录重试历史
        - 供 Agent 参考优化
```

---

### 3.6 MCP Server（工具服务）

**位置**：`mcp_server/`

**架构**：FastMCP + 自动注册

**工具分类**：
- 数据查询工具
- 指标计算工具
- 策略执行工具

**传输协议**：
- stdio（默认）
- SSE（可选）

---

## 4. 数据流设计

### 4.1 完整数据流（Polars 统一流）

```
┌─────────────────┐
│  Tushare API    │
└────────┬────────┘
         │ HTTP Request
         ▼
┌─────────────────┐
│  SyncRepository │
│  (datahub)      │
└────────┬────────┘
         │ load(query)
         ▼
┌─────────────────┐
│ Parquet Cache   │
│ data_cache/     │
└────────┬────────┘
         │ 读取/写入
         ▼
┌─────────────────┐
│ Polars DataFrame│ ← DataLoader.load_raw_market_data()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ StockPoolFilter │ ← apply_filter()
│ (polars 过滤)   │
└────────┬────────┘
         │ 过滤后的 polars df
         ▼
┌─────────────────┐
│ Bridge Tools    │ ← data_fn 返回 polars
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent 调用工具  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ BatchCalculator │ ← polars 向量化计算
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FilterEngine    │ ← polars 表达式过滤
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  筛选结果        │
│  (polars df)    │
└─────────────────┘
```

### 4.2 关键设计原则

1. **Polars 优先**
   - datahub 返回 polars
   - 所有过滤/计算使用 polars API
   - 零 pandas 转换

2. **类型检测兼容**
   ```python
   is_polars = hasattr(df, 'filter') and not hasattr(df, 'loc')
   
   if is_polars:
       result = df.filter(pl.col("close") > 10)
   else:
       result = df[df["close"] > 10]
   ```

3. **向后兼容**
   - 外部工具仍可传入 pandas
   - 自动检测并使用相应 API

---

## 5. 关键设计决策

### 5.1 为什么选择 Polars？

| 维度 | Pandas | Polars | 决策理由 |
|------|--------|--------|----------|
| 性能 | Python 循环 | Rust 后端 | 10-100x 提升 |
| 内存 | 拷贝为主 | 零拷贝 | 60% 节省 |
| 并行 | 单线程 | 自动多线程 | 充分利用多核 |
| 惰性求值 | ❌ | ✅ | 查询优化 |
| 类型系统 | 弱类型 | 强类型 | 更少错误 |

**实测数据**：
- 数据加载：5s → 2s (2.5x)
- 股票池过滤：3s → 0.8s (3.75x)
- 批量计算：10s → 3s (3.3x)
- 内存占用：2GB → 800MB (60% ↓)

### 5.2 为什么废除 MultiIndex？

**之前的问题**：
```python
# v1.x: 强制 MultiIndex
df = df.to_pandas().set_index(['trade_date', 'ts_code'])  # ❌ 性能损耗
if not isinstance(df.index, pd.MultiIndex):
    raise ValueError("必须是 MultiIndex")  # ❌ 强制约束
```

**v2.0 改进**：
```python
# 直接使用列操作
df.filter(pl.col("ts_code").is_in(stock_codes))
df.group_by("ts_code").agg(pl.col("close").mean())
```

**优势**：
- ✅ 无需转换，保持 polars 格式
- ✅ 列操作更直观
- ✅ 性能更好（Rust 后端）

### 5.3 模块化设计原则

**职责分离**：
```
DataLoader          → 只负责数据加载
ComponentInitializer → 只负责组件初始化
QueryExecutor       → 只负责查询执行
StockPoolService    → 独立的股票池过滤服务
```

**好处**：
- ✅ 单一职责，易于测试
- ✅ 低耦合，易于替换
- ✅ 高内聚，逻辑清晰

### 5.4 质量闭环设计

```
Agent 执行查询
    ↓
Quality Evaluator 评分
    ↓
分数 < 阈值？
    ├─ Yes → Smart Retry Manager
    │          ├─ 错误分类
    │          ├─ 参数调整
    │          └─ 重新执行
    └─ No  → 返回结果
```

**持久化学习**：
- SQLite 记录每次重试
- Agent 参考历史优化策略
- 逐步提升成功率

---

## 6. 目录结构速查

```
stock_asking_system/
├── app/                          # 应用入口
│   ├── screener.py              # 筛选主入口
│   ├── backtest.py              # 回测主入口
│   └── setting/                 # 配置文件
│       ├── screening.yaml
│       ├── backtest.yaml
│       └── stock_pool.yaml
│
├── src/
│   ├── agent/                   # Agent 系统
│   │   ├── core/
│   │   │   └── orchestrator.py  # 编排器
│   │   ├── initialization/
│   │   │   ├── data_loader.py   # 数据加载器
│   │   │   └── component_initializer.py
│   │   ├── execution/
│   │   │   └── query_executor.py # 查询执行器
│   │   ├── harness/             # Harness 约束
│   │   ├── quality/             # 质量评估
│   │   ├── services/            # 服务层
│   │   │   ├── stock_pool_service.py
│   │   │   └── index_loader.py
│   │   └── tools/               # Bridge 工具
│   │
│   ├── screening/               # 筛选引擎
│   │   ├── executor.py
│   │   ├── stock_pool_filter.py
│   │   ├── batch_calculator.py
│   │   └── script_saver.py
│   │
│   └── backtest/                # 回测引擎
│       ├── engine.py
│       ├── returns.py
│       └── report.py
│
├── datahub/                     # 数据层
│   ├── core/
│   │   ├── repository.py
│   │   └── query.py
│   ├── loaders/
│   │   ├── stock_loader.py
│   │   └── factor_loader.py
│   └── source/
│       └── tushare_source.py
│
├── mcp_server/                  # MCP 服务
│   ├── server.py
│   └── executors/
│
├── infrastructure/              # 基础设施
│   ├── config/
│   ├── logging/
│   ├── retry/
│   └── session/
│
└── docs/                        # 文档
    ├── ARCHITECTURE.md          # 本文档
    ├── screening_engine.md
    ├── backtest_engine.md
    ├── datahub.md
    └── CHANGELOG.md
```

---

## 7. 快速开始

### 7.1 环境准备

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 TUSHARE_TOKEN
```

### 7.2 运行筛选

```bash
# 执行默认查询
python app/screener.py

# 查看帮助
python app/screener.py --help
```

### 7.3 运行回测

```bash
python app/backtest.py
```

---

## 8. 常见问题

### Q1: 为什么我的筛选结果为空？

**可能原因**：
1. 股票池过滤太严格 → 检查 `stock_pool.yaml`
2. 筛选条件过于苛刻 → 放宽阈值
3. 数据不完整 → 检查 `min_completeness_ratio`

**调试方法**：
```python
logger.info(f"初始股票数: {len(all_codes)}")
logger.info(f"过滤后股票数: {len(filtered_codes)}")
```

### Q2: 如何切换 Deep/Quick 模式？

修改 `screening.yaml`：
```yaml
harness:
  deep_thinking: true  # true=Deep, false=Quick
```

### Q3: Polars 和 Pandas 如何选择？

**推荐**：
- ✅ 新项目：直接使用 Polars
- ⚠️ 旧代码：系统自动检测，无需手动干预

---

## 9. 参考资料

- [Screening Engine 详细说明](./screening_engine.md)
- [Backtest Engine 详细说明](./backtest_engine.md)
- [DataHub 详细说明](./datahub.md)
- [Agent System 详细说明](./agent_system.md)
- [版本更新日志](./CHANGELOG.md)
