# MCP Server - 模型上下文协议服务

> 提供标准化的量化工具服务接口,支持远程调用。

## 📖 概述

MCP (Model Context Protocol) Server 基于 FastMCP 框架构建,为 Agent 提供远程量化工具服务。它采用自动注册机制,通过装饰器即可将函数暴露为 MCP 工具。

### 核心特性

- 🔌 **FastMCP框架**:基于MCP协议的轻量级服务
- 🎯 **自动注册**:通过装饰器自动发现和注册工具函数
- 🌐 **多传输协议**:支持stdio和SSE两种传输方式
- 📦 **工具分类**:数据查询、指标计算、策略执行等
- ⚡ **高性能**:向量化计算,快速响应
- 🛡️ **智能参数验证**:Pydantic 自动验证 + 智能纠错建议

## 🏗️ 架构设计

```
┌─────────────────────────────────────┐
│       Agent (Client)                │
└──────────────┬──────────────────────┘
               │ MCP Protocol
┌──────────────▼──────────────────────┐
│      MCP Server                      │
│  • FastMCP                          │
│  • Tool Registry                    │
│  • Auto Register                    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Tool Executors                   │
│  • Data Query Tools                 │
│  • Indicator Calculation Tools      │
│  • Strategy Execution Tools         │
└─────────────────────────────────────┘
```

## 📁 目录结构

```
mcp_server/
├── __init__.py                     # 包入口
├── __main__.py                     # CLI 入口
├── server.py                       # 服务器主程序
├── auto_register.py                # 自动注册装饰器
├── registered_tools.py             # 已注册工具管理
├── pyproject.toml                  # MCP 项目配置
│
└── executors/                      # 工具执行器
    ├── __init__.py                 # 模块入口
    ├── math_tools.py               # 数学工具
    ├── other_tools.py              # 其他工具
    ├── technical_tools.py          # 技术指标工具
    └── time_series_tools.py       # 时间序列工具
```

## 🔧 核心组件

### 1. Server(服务器)

MCP 服务器主程序。

**启动方式**:

```bash
# stdio 模式(默认)
python -m mcp_server

# SSE 模式
python -m mcp_server --transport sse --host 127.0.0.1 --port 8000
```

**使用示例**:

```python
from mcp_server.server import create_server

# 创建服务器
server = create_server()

# 运行
server.run(transport="stdio")
```

### 2. Auto Register(自动注册)

通过装饰器自动注册工具函数，并提供智能参数验证。

**核心功能**：
1. **自动注册**：使用 `@tool_registry.register()` 装饰器
2. **Pydantic 验证**：从函数签名自动生成验证模型
3. **智能纠错建议**：识别常见参数错误并提供修正建议

**智能参数建议示例**：

当 Agent 调用工具时使用错误的参数名：
```python
# 错误调用
rank_normalize(values='beta_60')  # ❌ 错误参数名

# 系统返回的智能建议
❌ 缺少必需参数：'column'
⚠️  检测到你可能使用了 'values'
✅ 请改为使用：'column'
💡 示例：{'column': 'beta_60'}
```

**支持的参数映射**：
- `rank_normalize`: values → column
- `rolling_mean/rolling_std/rsi/kdj`: n/period → window
- `macd`: fast_period → fast, slow_period → slow, signal_period → signal

**实现位置**：
- `auto_register.py` 第 154-235 行：`_get_param_suggestion()` 方法
- `quality_evaluator.py` 第 120-160 行：`_handle_param_validation_error()` 方法

**使用示例**:

```python
from mcp_server.auto_register import register_tool
import pandas as pd

@register_tool
def rolling_mean(data: pd.DataFrame, column: str, window: int) -> pd.Series:
    """
    计算滚动均值
    
    Args:
        data: 股票数据
        column: 列名
        window: 窗口大小
        
    Returns:
        滚动均值 Series
    """
    return data[column].rolling(window=window).mean()
```

### 3. Tool Executors(工具执行器)

各类工具的具体实现。

**工具分类**:

| 分类 | 说明 | 示例 |
|------|------|------|
| 数据查询 | 获取股票、基金等数据 | `get_stock_daily` |
| 指标计算 | 计算技术指标 | `rolling_mean`, `rsi`, `macd` |
| 指数相关性 | 与指数对比分析 | `beta`, `alpha`, `correlation_with_index` |
| 策略执行 | 执行筛选策略 | `run_screening` |

## 💡 使用示例

### 示例 1:添加新工具

```python
# mcp_server/executors/my_tools.py
from mcp_server.auto_register import register_tool
import pandas as pd

@register_tool
def my_custom_indicator(data: pd.DataFrame, param: float) -> pd.Series:
    """
    我的自定义指标
    
    Args:
        data: 股票数据 DataFrame
        param: 参数
        
    Returns:
        指标值 Series
    """
    return data['close'].rolling(window=int(param)).mean()
```

工具会自动被注册,无需手动配置。

### 示例 1.5: 使用指数相关性工具

新增的指数相关性工具需要数据中包含股票和指数的价格列：

```python
# 准备数据：包含股票和指数价格
data = pd.DataFrame({
    'close': stock_prices,        # 股票收盘价
    'index_close': index_prices,  # 指数收盘价（如沪深300）
})

# 1. 计算 Beta（系统性风险）
beta_values = beta(data, stock_col='close', index_col='index_close', window=60)
# Beta > 1: 高波动性; Beta < 1: 低波动性

# 2. 计算 Alpha（超额收益）
alpha_values = alpha(data, stock_col='close', index_col='index_close', window=60)
# Alpha > 0: 跑赢市场

# 3. 计算跑赢指数天数
outperform = outperform_rate(data, stock_col='close', index_col='index_close', window=60)
# 过去60天中有多少天跑赢指数

# 4. 计算与指数的相关系数
corr = correlation_with_index(data, stock_col='close', index_col='index_close', window=60)
# -1 到 1，越接近1表示与指数走势越一致

# 5. 计算跟踪误差
tracking_err = tracking_error(data, stock_col='close', index_col='index_close', window=60)
# 越小表示跟随指数越紧密

# 6. 计算信息比率
ir = information_ratio(data, stock_col='close', index_col='index_close', window=60)
# IR > 0.5: 良好; IR > 1.0: 优秀
```

**实际应用场景**：

```python
# 筛选低 Beta、高 Alpha 的优质股票
screening_logic = {
    "name": "稳健阿尔法策略",
    "tools_definition": [
        {"name": "beta", "params": {"window": 60}},
        {"name": "alpha", "params": {"window": 60}},
    ],
    "expression": "(beta < 1.0) & (alpha > 0)",
    "confidence": "rank_normalize(alpha) * 0.7 + rank_normalize(1/beta) * 0.3"
}

# 筛选高信息比率的股票
screening_logic = {
    "name": "高信息比率策略",
    "tools_definition": [
        {"name": "information_ratio", "params": {"window": 60}},
    ],
    "expression": "information_ratio > 0.5",
    "confidence": "rank_normalize(information_ratio)"
}
```

### 示例 2:从 Agent 调用 MCP 工具

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

# 创建 MCP 客户端
client = MultiServerMCPClient({
    "quant-tools": {
        "command": "python",
        "args": ["-m", "mcp_server"]
    }
})

# 获取工具
tools = await client.get_tools()

# 调用工具
result = await tools["rolling_mean"].ainvoke({
    "data": stock_data,
    "column": "close",
    "window": 5
})
```

### 示例 3:查看已注册工具

```python
from mcp_server.registered_tools import get_all_tools

tools = get_all_tools()
print(f"已注册 {len(tools)} 个工具:")
for tool_name in sorted(tools):
    print(f"  - {tool_name}")
```

## ⚙️ 配置说明

MCP Server 的配置在 `mcp_server/pyproject.toml` 中:

```toml
[project]
name = "stock-asking-mcp"
version = "0.1.0"
description = "MCP Server for Stock Asking System"

[project.scripts]
mcp-server = "mcp_server.server:main"
```

Agent 中的 MCP 配置在 `setting/settings.yaml`:

```yaml
mcp:
  enabled: true
  transport: "stdio"  
  host: "127.0.0.1"
  port: 8000
  timeout: 30
```

## 🧪 测试

```bash
# 运行所有 MCP 测试
pytest tests/mcp_server/ -v

# 运行特定测试
pytest tests/mcp_server/test_executors.py -v
pytest tests/mcp_server/test_mcp_core.py -v
```

## 🔌 扩展开发

### 添加工具分类

1. 在 `mcp_server/executors/` 下创建新文件:

```python
# mcp_server/executors/risk_tools.py
from mcp_server.auto_register import register_tool

@register_tool
def calculate_var(returns: list[float], confidence: float = 0.95) -> float:
    """计算风险价值(VaR)"""
    import numpy as np
    return np.percentile(returns, (1 - confidence) * 100)
```

2. 在 `mcp_server/executors/__init__.py` 中导入:

```python
from . import risk_tools  # 自动注册
```

### 自定义工具注册

```python
from mcp_server.auto_register import tool_registry

# 手动注册工具
tool_registry.register(
    name="my_tool",
    func=my_function,
    description="My custom tool",
    parameters={...}
)
```

## 📊 性能优化建议

1. **向量化计算**:使用 Pandas/NumPy 向量化操作
2. **缓存结果**:对频繁调用的工具实现缓存
3. **异步处理**:对于耗时操作使用异步执行
4. **批量处理**:支持批量输入,减少调用次数

## 🔗 相关文档

- [主 README](../README.md)
- [Agent System](./agent_system.md)
- [MCP 官方文档](https://modelcontextprotocol.io/)

## 📝 更新日志

- **2026-04**: 新增指数相关性工具（beta, alpha, tracking_error等）
- **2024-04**: 完善工具分类和文档
- **2024-03**: 支持 SSE 传输协议
- **2024-02**: 添加自动注册机制
- **2024-01**: 初始版本,实现基础 MCP 服务
