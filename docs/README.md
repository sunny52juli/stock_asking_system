# stock_asking_system - AI 驱动的量化交易系统

基于 LLM 的股票筛选和回测系统，整合了 DeepAgents 框架、MCP 工具协议和多模块架构。

> 💡 **项目定位**：面向个人投资者的实战工具，尤其适合短线技术派投资者
>
> **核心功能**：
> 1. 🤖 **智能筛选** - 基于 LLM 理解自然语言，自动生成股票筛选策略，无需手动编写代码
> 2. 📊 **策略回测** - 对生成的策略进行历史回测，清晰展示收益情况，辅助投资决策

## 系统架构概览

```
stock_asking_system
├── datahub          # 数据层：统一的数据访问和管理
├── screener_deepagent  # AI Agent 层：股票筛选智能体
├── screener_mcp     # MCP 服务层：标准化的工具接口
├── backtest         # 回测层：策略收益率计算和报告
├── config           # 配置层：所有模块的配置管理
└── utils            # 工具层：通用的工具和异常处理
```

## 核心模块设计

### 1. DataHub（数据中心）

**职责**：统一的数据访问层，负责市场数据的加载、缓存和管理

**核心架构**：
- **域入口设计**：提供 `Stock`、`Fund`、`Index`、`Feature`、`News`、`Calendar` 六个域入口
- **数据源抽象**：通过 `DataSource` 协议支持多种数据源（如 Tushare）
- **分层加载器**：
  - `StockDataLoader`：股票价格、基本面数据
  - `FactorDataLoader`：因子数据
- **缓存机制**：Parquet 格式本地缓存，支持增量更新

**主要功能**：
- 股票行情数据（日线、分钟线）
- 财务指标和基本面数据
- 技术指标和自定义因子
- 交易日历管理
- 行业分类数据

**使用示例**：
```python
from datahub import Stock, Calendar, Feature

stock = Stock()
df = stock.price(date="20240301")  # 获取指定日期行情

cal = Calendar()
dates = cal.get_trade_dates("20240101", "20240131")  # 获取交易日历

fe = Feature()
snap = fe.snapshot(factors=["momentum_1m"], date="20240301")  # 获取因子快照
```

---

### 2. Screener DeepAgent（AI 筛选智能体）

**职责**：基于 LLM 的智能股票筛选系统，理解自然语言查询并生成筛选策略

**核心架构**：
- **Agent Factory**：使用 `create_deep_agent` 构建智能体
- **技能系统（Skill Registry）**：可插拔的技能模块，封装专业领域知识
- **记忆系统（Long-term Memory）**：SQLite 持久化存储用户偏好和历史记录
- **工具提供者（Tool Provider）**：整合 MCP 工具和本地 Bridge 工具
- **上下文工程**：动态注入领域知识和历史经验

**设计说明**：
- 简化版本专注于股票推荐功能
- 不包含收益率计算，仅执行筛选和脚本生成
- 收益率计算功能保留在独立的回测模块中

**核心组件**：
- **Bridge Tools**：连接 Agent 与本地数据的桥梁
  - `run_screening`：执行筛选
  - `get_available_industries`：获取行业列表
  - `save_screening_script`：保存策略
- **MCP Tools**：通过标准 MCP 协议提供的远程工具集
- **Generators**：策略脚本生成器，将筛选逻辑转为可执行代码

---

### 3. Screener MCP（工具服务协议层）

**职责**：基于 MCP（Model Context Protocol）协议提供标准化的工具服务

**核心架构**：
- **MCP Server**：独立进程运行，通过 stdio 与主程序通信
- **自动注册机制**：工具函数自动发现和注册
- **表达式工具集**：提供丰富的股票筛选表达式构建块
- **工具实现库**：具体的筛选逻辑实现

**设计理念**：
- **进程隔离**：MCP 工具在独立进程运行，避免污染主进程数据
- **标准化接口**：所有工具遵循统一的输入输出规范
- **可扩展性**：新增工具只需遵循注册规范即可自动集成

**与 Bridge Tools 的区别**：
- MCP Tools：独立进程，无状态，不持有 DataFrame
- Bridge Tools：宿主进程，有状态，可访问已加载的数据

---

### 4. Backtest（回测引擎）

**职责**：策略回测执行和收益率计算

**核心架构**：
- **两阶段设计**：
  1. **筛选阶段**：执行策略脚本，获取候选股票
  2. **收益计算阶段**：计算不同持有期的收益率
  
- **模块化组件**：
  - `ScriptLoader`：动态加载策略脚本
  - `DataProvider`：加载和管理市场数据
  - `ScreeningExecutor`：执行筛选逻辑
  - `ReturnCalculator`：计算持仓收益率
  - `ReportDisplay`：生成回测报告

**核心功能**：
- 多持有期收益率计算（如 1 日、5 日、10 日）
- 胜率和年化收益统计
- 持仓股票详细信息追踪
- 投资组合统计分析

**配置管理**：
- `backtest_config.py`：回测参数配置
- `data_config.py`：数据缓存路径和 API Token

---

### 5. Config（配置中心）

**职责**：统一管理所有模块的配置信息

**模块划分**：
- **API 配置** (`api_config.py`)：LLM API 密钥、模型、URL
- **数据配置** (`data_config.py`)：Tushare Token、缓存路径
- **回测配置** (`backtest_config.py`)：观察期长度、持有期列表
- **DeepAgent 配置** (`screener_deepagent_config.py`)：Agent 行为参数
- **提示词配置** (`screener_deepagent_prompts.py`)：系统提示词模板
- **数据字段** (`data_fields.py`)：数据列名映射和定义

**环境变量管理**：
- `.env` 文件存储敏感信息（API Key、Token）
- `.env.example` 提供配置模板
- 通过 `dotenv` 自动加载

---

### 6. Utils（工具库）

**职责**：提供跨模块的通用工具和基础设施

**核心组件**：
- **Logger**：统一的日志系统
- **异常体系**：
  - `DataLoadError`：数据加载失败
  - `ScreeningError`：筛选执行错误
  - `ToolExecutionError`：工具调用失败
- **Path Manager**：路径管理工具
- **Prompt Manager**：提示词模板管理
- **Stock Screener**：筛选逻辑执行引擎
- **Screening Tools**：筛选相关的辅助工具

---

## 系统工作流

### 典型使用场景

#### 场景 1：AI 股票筛选
```
用户查询 → DeepAgent → Bridge Tools → DataHub 数据
              ↓
        MCP Tools (可选)
              ↓
        返回候选股票 → 显示结果
              ↓
        用户确认保存 → 生成策略脚本
```

#### 场景 2：策略回测（独立运行）
```
python backtest_runner.py → 加载策略脚本 → DataHub 加载数据
                                    ↓
                          ScreeningExecutor 筛选
                                    ↓
                          ReturnCalculator 计算收益
                                    ↓
                              生成回测报告
```

#### 场景 3：数据查询
```
Stock/Fund/Index 等域入口 → DataLoader → DataSource(Tushare)
                                              ↓
                                        本地缓存 (Parquet)
```

---

## 技术栈

- **核心框架**：Python 3.12+
- **AI/LLM**：
  - DeepAgents 框架
  - LangChain + MCP Adapters
  - 支持多种 LLM 提供商（DeepSeek 等）
- **数据处理**：
  - Pandas + NumPy
  - PyArrow (Parquet 格式)
- **数据源**：Tushare Pro
- **持久化**：SQLite (记忆系统)
- **开发工具**：
  - UV (包管理)
  - Ruff + Black (代码质量)
  - Mypy (类型检查)
  - Pytest (单元测试)

---

## 快速开始

### 1. 环境准备
```bash
# 安装依赖
uv sync

# 复制环境变量配置
cp .env.example .env

# 编辑 .env 填入 API Key
# DEFAULT_API_KEY=your-api-key
# DATA_SOURCE_TOKEN=your-tushare-token
```

### 2. 运行 AI 股票筛选
```bash
# 使用 DeepAgent 进行股票筛选
python run.py

# 或使用命令行入口
quant-query-deepagent
```

### 3. 运行策略回测
```bash
# 回测 screening_scripts 目录中的所有策略
python backtest_runner.py
```

**运行示例**：
```
开始测试回测功能
------------------------------------------------------------
2026-03-31 20:36:08 - backtest.backtest - INFO - ============================================================
2026-03-31 20:36:08 - backtest.backtest - INFO - 加载市场数据...
2026-03-31 20:36:08 - backtest.backtest - INFO - 配置的筛选日期：20260201
回测目录：screening_scripts/放量突破策略
筛选日期：20260201 (配置默认值)
观察期长度：80 个交易日
持有期：[4, 10, 20] 天
数据起止日期：20251009 ~ 20260310
缓存目录：D:\code\QuantitativeSystem\stock_asking_system\data_cache
正在检查本地缓存...
...
已加载市场数据：418754 条记录

  找到 1 个脚本
    执行：放量突破策略_20260331_165317.py
2026-03-31 21:20:29 - utils.stock_screener - WARNING - 数据历史不足：筛选日期前有 50 个交易日，建议至少 80 个交易日以确保指标计算准确
数据历史不足：筛选日期前有 50 个交易日，建议至少 80 个交易日以确保指标计算准确
    筛选器初始化完成
      筛选日期：2026-01-30
      股票总数：5244

    步骤 1: 预筛选股票池...
      未检测到预筛选条件，使用全部股票池
      预筛选后：5244 只股票

    步骤 2: 计算技术指标并筛选...

       筛选逻辑:
         表达式：(daily_return > 0.03) & (vol / avg_volume_5d > 1.5) & (rsi_14 < 75)
         置信度：daily_return * 100 * 0.5 + (vol / avg_volume_5d - 1) * 100 * 0.5
         工具步骤:
            daily_return = pct_change({'column': 'close', 'periods': 1})
            avg_volume_5d = rolling_mean({'column': 'vol', 'window': 5})
            rsi_14 = rsi({'column': 'close', 'window': 14})

       向量化批量筛选模式 (5244 只股票)
      数据过滤：5244  5231 只有效股票
         无最新数据：13 只
       执行 3 个主工具...
         [1/3]  pct_change  daily_return
         [2/3]  rolling_mean  avg_volume_5d
         [3/3]  rsi  rsi_14
       工具执行完成，成功：3, 失败：0

       筛选统计:
         候选股票数：5244
         无最新数据：13 只
         表达式为 False: 5107 只
          成功匹配：124 只
         ️ 耗时：12.05s
      成功筛选：124 只
       筛选出 20 只股票

 回测完成！
总脚本数：1
成功：1
失败：0

====================================================================================================
 回测报告详情 - 持仓股票及收益
====================================================================================================

【放量突破策略_20260331_165317】

前 20 大持仓股票：
股票名称         行业              4 日收益率      10 日收益率      20 日收益率     
------------------------------------------------------------------
深圳华强         元器件                 -6.87%     -7.14%    -10.12%
西部创业         铁路                  -4.39%     -6.11%     -4.01%
惠天热电         供气供热                 0.53%      2.38%     10.58%
罗牛山          农业综合                -7.46%     -9.59%     -9.94%
凯撒旅业         旅游服务                 4.84%     -1.87%    -15.60%
中水渔业         渔业                   1.65%      7.88%     -3.81%
德展健康         化学制药                -8.35%    -10.21%    -16.01%
桂林旅游         旅游景点                 1.09%     -3.27%     -3.55%
农心科技         农药化肥                -0.48%      0.92%      1.20%
一彬科技         汽车配件                10.82%     11.48%      4.77%
天顺风能         电气设备                 9.66%     20.20%     36.21%
兄弟科技         化学制药                -2.02%     -2.96%     -8.74%
世纪华通         互联网                 -1.72%     -2.78%    -10.37%
华锋股份         汽车配件                -0.07%     24.00%     11.97%
金逸影视         影视音像                 9.71%      1.40%    -16.63%
润都股份         化学制药                 9.17%      8.48%      9.73%
宏川智慧         仓储物流                 6.97%      9.18%     24.64%
亚世光电         元器件                  0.63%     -3.83%      9.14%
北摩高科         航空                  16.90%     10.05%     -1.57%
北陆药业         化学制药                 4.60%      2.25%     12.16%

持仓统计：
| 持有期  |  有效样本 |    平均收益    |    最大收益    |    最大亏损    |    胜率    |
|-----|------|-----------|-----------|-----------|---------|
|  4 日  |  20 只  |     2.26%  |    16.90%  |    -8.35%  |   60.0%  |
| 10 日  |  20 只  |     2.52%  |    24.00%  |   -10.21%  |   55.0%  |
| 20 日  |  20 只  |     1.00%  |    36.21%  |   -16.63%  |   45.0%  |
|-----|------|-----------|-----------|-----------|---------|
```

### 4. 数据管理
```bash
# 使用 CLI 工具管理数据
python -m datahub download --date 20240301
python -m datahub check
```

---

## 目录结构说明

```
stock_asking_system/
├── datahub/                  # 数据层
│   ├── core/                 # 核心抽象（Source, Repository, Query）
│   ├── domain/               # 域入口实现（Stock, Fund, Index...）
│   ├── loaders/              # 数据加载器
│   ├── registry/             # 数据集注册表
│   └── source/               # 数据源实现
│
├── screener_deepagent/       # AI Agent 层
│   ├── context/              # 上下文管理
│   ├── generators/           # 策略脚本生成器
│   ├── memory/               # 长期记忆系统
│   ├── skills/               # 技能模块
│   └── tools/                # 工具提供者
│
├── screener_mcp/             # MCP 服务层
│   ├── server.py             # MCP 服务器入口
│   ├── tool_implementations.py  # 工具实现
│   └── expression_tools.py   # 表达式工具集
│
├── backtest/                 # 回测层
│   ├── backtest.py           # 回测执行器
│   ├── returns.py            # 收益率计算
│   └── report_display.py     # 报告展示
│
├── config/                   # 配置层
│   ├── api_config.py         # API 配置
│   ├── data_config.py        # 数据配置
│   ├── backtest_config.py    # 回测配置
│   └── screener_deepagent_config.py  # Agent 配置
│
├── utils/                    # 工具层
│   ├── logger.py             # 日志
│   ├── exceptions.py         # 异常定义
│   ├── stock_screener.py     # 筛选引擎
│   └── path_manager.py       # 路径管理
│
├── data_cache/               # 数据缓存（Parquet 文件）
│   └── stock/
│       ├── basic/            # 基础信息
│       └── daily/            # 日线数据
│
├── screening_scripts/        # 生成的策略脚本
├── docs/                     # 文档
├── run.py                    # 主入口
└── backtest_runner.py        # 回测入口
```

---

## 设计理念

### 1. 分层架构
- **数据层**：专注数据获取和缓存，对上层透明
- **服务层**：MCP 协议提供标准化工具接口
- **应用层**：DeepAgent 整合各模块完成用户任务
- **配置层**：集中管理所有配置项

### 2. 进程隔离
- MCP 工具在独立进程运行，避免数据污染
- Bridge 工具在主进程运行，高效访问数据

### 3. 可扩展性
- 技能系统支持热插拔
- 数据源支持多后端
- MCP 协议便于集成第三方工具

### 4. 配置驱动
- 所有关键参数可通过配置文件或环境变量调整
- 支持不同场景的预设配置

---

## 注意事项

1. **API 配置**：需要配置 LLM API Key 和 Tushare Token 才能正常运行
2. **数据缓存**：首次运行会自动下载数据，后续使用本地缓存
3. **MCP 服务**：DeepAgent 启动时会自动加载 MCP 工具，需确保 Python 环境正确
4. **回测数据**：回测时需要确保有足够的历史数据来计算收益率

---

## 开发规范

- **代码风格**：Black 格式化，Ruff Lint 检查
- **类型注解**：完整的 Type Hints，Mypy 严格检查
- **测试覆盖**：核心模块需包含单元测试
- **提交规范**：遵循 Conventional Commits

---

## 许可证

MIT License

---

## 致谢

- **参考项目**：[QuantitativeSystem](https://github.com/luocheng812/QuantitativeSystem/tree/develop)
- **开源框架**：
  - [LangChain](https://python.langchain.com/) - 提供强大的 LLM 应用开发框架和 MCP 集成支持
- **数据服务**：
  - [Tushare](https://tushare.pro/) - 提供全面的中国金融市场数据
