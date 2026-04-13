# AI驱动的量化交易系统

> **v2.0 全面重构版** - 基于原 [stock_asking_system](https://github.com/sunny52juli/stock_asking_system) 的架构升级版本

基于LLM的智能股票筛选与回测框架，通过自然语言交互实现因子挖掘、策略生成和回测验证。

## ✨ 核心特性

- 🤖 **双模式Agent**：深度思考模式（复杂策略）+ 快速模式（简单查询，响应快6倍）
- 📊 **智能筛选引擎**：向量化计算，全市场筛选从60s优化至12s
- 🔬 **专业回测系统**：多持有期并行测试，完整统计指标（胜率/回撤/年化收益）
- 🗄️ **统一数据层**：Repository Pattern + Parquet缓存，支持股票/基金/指数/新闻
- 🔧 **Harness约束框架**：Hooks/Rules/Permissions三层质量门禁
- ⚙️ **企业级配置**：YAML + Pydantic类型安全，支持热重载

## 🚀 快速开始

### 环境准备

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 和 Tushare Token
```

### AI股票筛选

```python
from src.agent import create_screener_agent
from infrastructure.config.settings import get_settings

settings = get_settings()
# 创建Agent并执行筛选...
```

### 策略回测

```python
from src.backtest import run_backtest

report = run_backtest(
    scripts_dir="./screening_scripts",
    screening_date="20260201",
    holding_periods=[4, 10, 20]
)
```

## 📚 文档

- [详细架构说明](docs/README.md) - 完整的框架设计和模块说明
- [版本改进说明](docs/VERSION_IMPROVEMENTS.md) - v1.0 → v2.0 的详细对比
- [旧版架构参考](docs/old_README.md) - 原始版本的设计文档

## 🏗️ 系统架构

```
Agent Layer (智能体层 - DeepAgents/LangGraph)
    ↓
Tool Layer (工具层 - MCP/Bridge Tools)
    ↓
Core Logic Layer (核心逻辑 - Screening/Backtest)
    ↓
DataHub Layer (数据层 - Repository Pattern)
    ↓
Infrastructure Layer (基础设施 - Config/Logging/Retry)
```

## 📈 性能提升

| 指标 | v1.0 | v2.0 | 提升 |
|------|------|------|------|
| 全市场筛选 | ~60s | ~12s | **5倍** |
| Agent响应(快速模式) | ~30s | ~5s | **6倍** |
| 内存占用 | ~2GB | ~800MB | **降低60%** |
| 批量回测效率 | 基准 | **2.5倍** | - |

## 🛠️ 技术栈

- **AI框架**: deepagents, LangGraph, LangChain
- **数据处理**: Pandas, NumPy, PyArrow
- **数据源**: Tushare Pro
- **通信协议**: MCP (Model Context Protocol)
- **配置管理**: Pydantic, YAML, dotenv
- **代码质量**: black, ruff, mypy, pytest
- **包管理**: uv

## 📂 项目结构

```
stock_asking_system/
├── src/                      # 核心业务逻辑
│   ├── agent/               # Agent智能体系统
│   ├── screening/           # 股票筛选引擎
│   └── backtest/            # 回测引擎
├── datahub/                 # 统一数据访问层
├── mcp_server/             # MCP服务
├── infrastructure/         # 基础设施层
├── setting/                # 配置文件
└── docs/                   # 文档
```

## 📝 主要改进点

相比原始版本，v2.0 的核心改进：

1. **架构分层**：从6个平级模块 → 6层清晰架构
2. **模块化设计**：筛选引擎从单文件800行 → 5个独立模块
3. **双模式Agent**：支持深度思考和快速两种运行模式
4. **性能优化**：向量化计算 + 智能缓存，整体性能提升5-50倍
5. **工程化**：完整测试体系、类型安全、CI/CD工具链

详见 [VERSION_IMPROVEMENTS.md](docs/VERSION_IMPROVEMENTS.md)

## ⚠️ 注意事项

1. **API配置**：需要配置 LLM API Key 和 Tushare Token
2. **数据缓存**：首次运行会自动下载数据，后续使用本地缓存
3. **Python版本**：要求 Python >= 3.12

## 📄 许可证

MIT License

## 🙏 致谢

- **参考项目**：[stock_asking_system](https://github.com/sunny52juli/stock_asking_system) - 原始版本
- **开源框架**：LangChain, deepagents, Tushare
