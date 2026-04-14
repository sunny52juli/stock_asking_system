# Infrastructure - 基础设施层

> 提供配置管理、日志系统、会话管理等通用组件。

## 📖 概述

Infrastructure 层为整个系统提供基础支撑服务,包括配置管理、日志记录、会话管理、错误处理等通用功能。

### 核心特性

- ⚙️ **配置管理**:多层配置(YAML + 环境变量 + 默认值)
- 📝 **日志系统**:结构化日志记录
- 💾 **会话管理**:会话状态持久化
- 🔒 **错误处理**:统一的异常体系
- 📊 **遥测监控**:OpenTelemetry集成(可选)

## 📁 目录结构

```
infrastructure/
├── __init__.py                     
│
├── config/                         # 配置管理
│   ├── __init__.py                 
│   ├── settings.py                 # 配置模型和加载器
│   └── ...
│
├── logging/                        # 日志系统
│   ├── __init__.py                 
│   └── logger.py                   # 日志配置
│
├── session/                        # 会话管理
│   ├── __init__.py                 
│   └── manager.py                  # 会话管理器
│
├── errors/                         # 错误处理
│   ├── __init__.py                 
│   └── exceptions.py               # 自定义异常
│
├── paths/                          # 路径管理
│   ├── __init__.py                 
│   └── paths.py                    # 路径工具
│
├── retry/                          # 重试机制
│   ├── __init__.py                 
│   └── manager.py                  # 重试管理器
│
└── telemetry/                      # 遥测监控
    ├── __init__.py                 
    └── monitor.py                  # 监控器
```

## 🔧 核心组件

### 1. Config(配置管理)

基于 Pydantic 的类型安全配置管理。

**配置层级**:

1. **默认值**:代码中定义的默认值
2. **YAML 文件**:`setting/` 目录下的配置文件（screening.yaml、stock_pool.yaml、backtest.yaml）
3. **环境变量**:通过 `.env` 文件设置
4. **命令行参数**:最高优先级

**使用示例**:

```python
from infrastructure.config.settings import get_settings

# 获取配置
settings = get_settings()

# 访问配置
print(settings.llm.model)           # "deepseek-chat"
print(settings.data.cache_root)     # "./data_cache"
print(settings.backtest.holding_periods)  # [4, 10, 20]
```

**配置模型**(`infrastructure/config/settings.py`):

```python
from pydantic import BaseModel, Field
from pathlib import Path

class LLMConfig(BaseModel):
    """LLM 配置"""
    model: str = Field(default="deepseek-chat")
    api_key: str = Field(default="${DEFAULT_API_KEY}")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, gt=0)

class DataConfig(BaseModel):
    """数据配置"""
    cache_root: Path = Field(default=Path("./data_cache"))
    source_token: str = Field(default="${DATA_SOURCE_TOKEN}")

class Settings(BaseModel):
    """全局配置"""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
```

**环境变量配置**(`.env`):

```bash
# LLM API Key
DEFAULT_API_KEY=sk-xxx

# 数据源 Token
DATA_SOURCE_TOKEN=your_tushare_token

# 其他配置
LOG_LEVEL=INFO
ENABLE_TELEMETRY=false
```

### 2. Logging(日志系统)

结构化日志记录。

**使用示例**:

```python
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# 不同级别的日志
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 带上下文信息
logger.info("处理股票数据", extra={
    "ts_code": "000001.SZ",
    "date": "20260413"
})
```

**日志配置**(`setting/screening.yaml`):

```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5
```

### 3. Session Management(会话管理)

会话状态持久化。

**使用示例**:

```python
from infrastructure.session import get_session_manager

manager = get_session_manager()

# 创建新会话
session = manager.create_session()
print(f"会话ID: {session.id}")

# 保存会话数据
manager.save_data(session.id, {
    "query": "帮我找放量突破的股票",
    "result": {...}
})

# 加载会话数据
data = manager.load_data(session.id)

# 获取当前会话
current_session = manager.get_current_session()
```

### 4. Error Handling(错误处理)

统一的异常体系。

**自定义异常**:

```python
from infrastructure.errors.exceptions import (
    DataLoadError,
    ScreeningError,
    ToolExecutionError,
    ConfigError
)

# 使用示例
try:
    data = load_stock_data("000001.SZ")
except DataLoadError as e:
    logger.error(f"数据加载失败: {e}")
    raise
except ScreeningError as e:
    logger.error(f"筛选执行失败: {e}")
    raise
```

**异常层次**:

```
BaseError
├── DataLoadError          # 数据加载错误
├── ScreeningError         # 筛选执行错误
├── ToolExecutionError     # 工具执行错误
├── ConfigError            # 配置错误
└── ValidationError        # 验证错误
```

### 5. Retry Manager(重试管理器)

智能重试机制。

**使用示例**:

```python
from infrastructure.retry import get_retry_manager

manager = get_retry_manager()

# 检查是否应该重试
should_retry, adjusted_params = manager.check_and_prepare_retry(
    error=ValueError("参数无效"),
    tool_name="rolling_mean",
    params={"window": 100}
)

if should_retry:
    # 使用调整后的参数重试
    result = execute_tool("rolling_mean", **adjusted_params)
    manager.record_success("rolling_mean")
```

### 6. Telemetry(遥测监控)

OpenTelemetry 集成(可选)。

**使用示例**:

```python
from infrastructure.telemetry import get_telemetry

telemetry = get_telemetry(enabled=True)

# 记录事件
telemetry.record_event("screening_started", {
    "strategy": "放量突破",
    "stock_count": 5000
})

# 记录指标
telemetry.record_metric("screening_duration", 1.5)

# 追踪操作
with telemetry.trace("execute_screening"):
    result = run_screening(...)
```

## 💡 使用示例

### 示例 1:完整配置流程

```python
from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import setup_logging
from infrastructure.session import get_session_manager

# 1. 加载配置
settings = get_settings()

# 2. 初始化日志
setup_logging(settings.logging)

# 3. 创建会话
session_manager = get_session_manager()
session = session_manager.create_session()

print(f"系统初始化完成,会话ID: {session.id}")
```

### 示例 2:错误处理和重试

```python
from infrastructure.retry import get_retry_manager
from infrastructure.errors.exceptions import ToolExecutionError

retry_manager = get_retry_manager()

def execute_with_retry(tool_name: str, params: dict):
    """带重试的执行"""
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            result = execute_tool(tool_name, **params)
            retry_manager.record_success(tool_name)
            return result
            
        except Exception as e:
            should_retry, adjusted_params = retry_manager.check_and_prepare_retry(
                e, tool_name, params
            )
            
            if not should_retry:
                raise ToolExecutionError(
                    f"工具 {tool_name} 执行失败",
                    details={"error": str(e)}
                )
            
            params = adjusted_params
            logger.warning(f"第 {attempt + 1} 次重试...")
    
    raise ToolExecutionError(f"重试 {max_attempts} 次后仍失败")
```

## ⚙️ 配置说明

完整配置示例分布在 `setting/` 目录的多个文件中：

```yaml
# LLM 配置
llm:
  model: "deepseek-chat"
  api_key: "${DEFAULT_API_KEY}"
  temperature: 0.7
  max_tokens: 4096

# 数据配置
data:
  cache_root: "./data_cache"
  source_token: "${DATA_SOURCE_TOKEN}"

# 回测配置
backtest:
  holding_periods: [4, 10, 20]
  observation_days: 80

# Harness 配置
harness:
  max_iterations: 25
  deep_thinking: false

# 日志配置
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/app.log"

# 会话配置
session:
  storage_type: "sqlite"
  db_path: ".stock_asking/sessions.db"

# 遥测配置
telemetry:
  enabled: false
  endpoint: "http://localhost:4317"
```

## 🧪 测试

```bash
# 运行所有基础设施测试
pytest tests/infrastructure/ -v

# 运行特定测试
pytest tests/infrastructure/test_config.py -v
pytest tests/infrastructure/test_exceptions.py -v
```

## 🔌 扩展开发

### 添加新的配置项

1. 在 `infrastructure/config/settings.py` 中定义模型:

```python
class MyConfig(BaseModel):
    """我的配置"""
    param1: str = Field(default="value1")
    param2: int = Field(default=100, gt=0)

class Settings(BaseModel):
    # ...
    my: MyConfig = Field(default_factory=MyConfig)
```

2. 在相应的 YAML 配置文件中添加配置（如 `screening.yaml`）:

```yaml
my:
  param1: "custom_value"
  param2: 200
```

### 添加新的异常类型

```python
from infrastructure.errors.exceptions import BaseError

class MyCustomError(BaseError):
    """我的自定义异常"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            error_code="MY_CUSTOM_ERROR",
            recoverable=True,
            details=details
        )
```

## 🔗 相关文档

- [主 README](../README.md)
- [Agent System](./agent_system.md)
- [DataHub](./datahub.md)

## 📝 更新日志

- **2024-01**: 初始版本,实现基础配置和日志
- **2024-02**: 添加会话管理
- **2024-03**: 完善错误处理体系
- **2024-04**: 添加遥测监控支持
