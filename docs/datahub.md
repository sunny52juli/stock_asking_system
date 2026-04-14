# DataHub - 统一数据访问层

> 提供标准化的金融数据访问接口，支持股票、基金、指数、新闻、特征等多维数据。

## 📖 概述

DataHub 是系统的统一数据访问层，采用 **Repository Pattern**（仓储模式）设计，屏蔽底层数据源差异，为上层应用提供一致的数据访问接口。

### 核心特性

- ✅ **统一接口**：无论数据来自本地缓存还是远程 API，调用方式一致
- ✅ **多数据源支持**：股票、基金、指数、新闻、特征数据等
- ✅ **高效缓存**：基于 Parquet 的日期分区缓存机制
- ✅ **领域驱动**：清晰的领域实体模型（Stock, Fund, Index 等）
- ✅ **自动切换**：本地/远程数据源智能切换

## 🏗️ 架构设计

```
┌─────────────────────────────────────┐
│      Application Layer              │
│  (Agent / Screening / Backtest)     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Data Loaders                  │
│  • StockDataLoader                  │
│  • FactorDataLoader                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Repository Layer               │
│  • SyncRepository                   │
│  • CacheRepository                  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Data Sources                  │
│  • TushareSource                    │
│  • LocalCacheSource                 │
└─────────────────────────────────────┘
```

## 📁 目录结构

```
datahub/
├── __init__.py                 # 包入口，导出公共 API
├── __main__.py                 # CLI 入口
├── entries.py                  # 数据条目定义
├── factory.py                  # 工厂类
├── protocols.py                # 协议定义
├── data_fields.py              # 数据字段定义
│
├── cli/                        # 命令行工具
│   ├── __init__.py
│   ├── args.py
│   └── handlers.py
│
├── core/                       # 核心抽象层
│   ├── __init__.py
│   ├── dataset.py             # Dataset 元数据和配置
│   ├── exceptions.py          # 异常定义
│   ├── query.py               # 查询对象
│   ├── repository.py          # Repository 接口
│   └── storage.py             # 存储接口
│
├── domain/                     # 领域实体
│   ├── __init__.py
│   ├── stock.py               # 股票实体
│   ├── fund.py                # 基金实体
│   ├── index.py               # 指数实体
│   ├── news.py                # 新闻实体
│   ├── feature.py             # 特征实体
│   └── calendar.py            # 交易日历
│
├── loaders/                    # 数据加载器
│   ├── __init__.py
│   ├── stock_loader.py        # 股票数据加载器
│   └── factor_loader.py       # 因子数据加载器
│
├── registry/                   # 注册中心
│   ├── __init__.py
│   ├── dataset_registry.py    # Dataset 注册表
│   ├── source_registry.py     # 数据源注册表
│   └── ...
│
├── service/                    # 服务层
│   ├── __init__.py
│   └── data_service.py        # 数据服务
│
├── source/                     # 数据源实现
│   ├── __init__.py
│   ├── tushare_source.py      # Tushare 数据源
│   └── local_source.py        # 本地缓存源
│
├── store/                      # 存储实现
│   ├── __init__.py
│   └── parquet_store.py       # Parquet 存储
│
└── sync/                       # 同步层
    ├── __init__.py
    └── sync_repo.py           # 同步仓储
```

## 🔧 核心组件

### 1. Domain Entities（领域实体）

领域实体定义了数据的结构和行为，是 DataHub 的核心抽象。

#### Stock（股票实体）

```python
from datahub.domain import Stock

# 获取股票基本信息
stock = Stock(ts_code="000001.SZ")
print(stock.name)      # 平安银行
print(stock.industry)  # 银行
```

**主要属性**：
- `ts_code`: 股票代码
- `name`: 股票名称
- `industry`: 所属行业
- `list_date`: 上市日期
- `market`: 市场类型

#### 其他实体

- **Fund**: 基金实体
- **Index**: 指数实体
- **News**: 新闻实体
- **Feature**: 特征实体
- **Calendar**: 交易日历

### 2. Repository Pattern（仓储模式）

Repository 提供了统一的数据访问接口，隐藏了数据来源的复杂性。

```python
from datahub.core.repository import Repository
from datahub.core.query import Query

# 创建查询
query = Query(
    dataset="stock_daily",
    filters={"ts_code": "000001.SZ"},
    date_range=("20240101", "20241231")
)

# 通过 Repository 获取数据
repo = get_repository()
data = repo.query(query)
```

**核心方法**：
- `query(query: Query)`: 执行查询
- `load(dataset: str, **kwargs)`: 加载数据集
- `save(dataset: str, data: DataFrame)`: 保存数据

### 3. Data Loaders（数据加载器）

Data Loader 提供了更高级的数据访问接口，封装了常见的数据加载场景。

#### StockDataLoader

**职责**: 纯粹的数据加载器，只负责从 Tushare 获取数据，不处理业务逻辑。

```python
from datahub.loaders import StockDataLoader

loader = StockDataLoader(
    exclude_st=True,        # 基础ST过滤
    min_list_days=180,      # 基础上市天数过滤
    index_code='000300.SH'  # 可选：指定指数成分股
)

# 加载股票日线数据
df = loader.load_market_data(
    trade_date_for_pool="20240301",  # 股票池筛选基准日期
    start_date="20240101",
    end_date="20240301"
)

print(df.shape)  # (行数, 列数)
print(df.columns.tolist())
# ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', ...]
```

**主要方法**：
- `load_market_data()`: 加载市场数据（包含行业信息）
- `get_available_industries()`: 获取可用行业列表
- `get_stock_codes()`: 获取股票代码列表

**注意**: 
- StockDataLoader 只提供基础的数据加载和简单的 ST/上市天数过滤
- **复杂的业务筛选规则（价格、市值、行业等）应使用 `StockPoolFilter`**
- 参见 [Screening Engine - StockPoolFilter](./screening_engine.md#2-stockpoolfilter股票池筛选器)

#### FactorDataLoader

用于加载因子数据，支持自定义因子计算。

### 4. Parquet Cache（Parquet 缓存）

基于日期的 Parquet 文件缓存机制，大幅提升数据加载速度。

**缓存结构**：
```
data_cache/stock/daily/
├── 20240101.parquet
├── 20240102.parquet
├── ...
└── 20241231.parquet
```

**优势**：
- ⚡ **快速读取**：Parquet 列式存储，读取速度快
- 💾 **节省空间**：压缩率高，占用空间小
- 📅 **日期分区**：按日期分区，支持增量更新
- 🔄 **自动管理**：缓存失效和更新自动化

### 5. Data Sources（数据源）

#### TushareSource

Tushare Pro API 数据源实现。

```python
from datahub.source import TushareSource

source = TushareSource(token="your_token")

# 调用 Tushare API
data = source.call("daily", {
    "ts_code": "000001.SZ",
    "start_date": "20240101",
    "end_date": "20241231"
})
```

**特性**：
- 自动重试机制
- 速率限制控制
- 错误处理和日志记录

#### LocalCacheSource

本地缓存数据源，优先从缓存读取数据。

## 💡 使用示例

### 示例 1：加载股票日线数据

```python
from datahub.loaders import StockDataLoader

# 创建加载器
loader = StockDataLoader()

# 加载多只股票的日线数据（包含行情、估值、资金流向等完整字段）
df = loader.load_daily(
    ts_codes=["000001.SZ", "600000.SH", "000858.SZ"],
    start_date="20240101",
    end_date="20241231"
)

print(df.columns.tolist())
# ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'pre_close', 
#  'change', 'pct_chg', 'vol', 'amount',           # 基础行情
#  'name', 'industry', 'market', 'list_date',      # 基本信息
#  'turnover_rate', 'volume_ratio', 'pe', 'pb',    # 估值指标
#  'total_mv', 'circ_mv',                          # 市值
#  'adj_factor',                                   # 复权因子
#  'buy_sm_vol', 'net_mf_amount', ...             # 资金流向
#  'rzye', 'rqye', ... ]                          # 融资融券

print(df.head())
#    ts_code trade_date   open   high    low  close     vol  turnover_rate    pe
# 0  000001.SZ   20240102  10.50  10.80  10.45  10.75  100000          1.25  8.50
# 1  000001.SZ   20240103  10.75  11.00  10.70  10.90   95000          1.18  8.62
```

### 示例 2：查询特定条件的数据

```python
from datahub.core.query import Query
from datahub.core.repository import get_repository

# 构建查询
query = Query(
    dataset="stock_daily",
    filters={
        "ts_code": "000001.SZ",
        "close": {"gt": 10.0}  # 收盘价大于 10
    },
    date_range=("20240101", "20241231"),
    columns=["ts_code", "trade_date", "close", "vol"]
)

# 执行查询
repo = get_repository()
result = repo.query(query)
```

### 示例 3：获取可用行业列表

```python
from datahub import get_available_industries

industries = get_available_industries()
print(industries)
# ['银行', '房地产', '电气设备', '半导体', ...]
```

### 示例 4：使用领域实体

```python
from datahub.domain import Stock, Calendar

# 获取股票信息
stock = Stock(ts_code="000001.SZ")
print(f"{stock.name} ({stock.ts_code})")
print(f"行业: {stock.industry}")
print(f"上市日期: {stock.list_date}")

# 检查交易日
calendar = Calendar()
is_trading_day = calendar.is_trading_day("20240101")
print(f"20240101 是否交易日: {is_trading_day}")
```

## 🔌 扩展开发

### 添加新的数据源

1. 实现 `DataSource` 接口：

```python
from datahub.protocols import DataSource

class MyDataSource(DataSource):
    def call(self, api_name: str, params: dict) -> DataFrame | None:
        # 实现数据获取逻辑
        pass
    
    def ping(self) -> bool:
        # 健康检查
        pass
```

2. 在 `datahub/source/__init__.py` 中注册：

```python
from .my_source import MyDataSource

__all__ = ["TushareSource", "MyDataSource"]
```

### 添加新的领域实体

1. 在 `datahub/domain/` 下创建实体类：

```python
from dataclasses import dataclass

@dataclass
class Bond:
    """债券实体"""
    bond_code: str
    name: str
    issue_date: str
    maturity_date: str
    coupon_rate: float
```

2. 在 `datahub/domain/__init__.py` 中导出：

```python
from .bond import Bond

__all__ = ["Stock", "Fund", "Index", "Bond"]
```

### 自定义数据加载器

```python
from datahub.loaders import BaseDataLoader

class CustomDataLoader(BaseDataLoader):
    def load_custom_data(self, **kwargs) -> DataFrame:
        # 实现自定义数据加载逻辑
        pass
```

## ⚙️ 配置说明

DataHub 的配置在 `setting/screening.yaml` 中：

```yaml
data:
  cache_root: "./data_cache"          # 缓存根目录
  source_token: "${DATA_SOURCE_TOKEN}" # 数据源 Token
  cache_ttl: 86400                     # 缓存有效期（秒）
  
  # 数据源配置
  sources:
    - type: tushare
      enabled: true
    - type: local_cache
      enabled: true
```

## 🧪 测试

运行 DataHub 相关测试：

```bash
# 运行所有 DataHub 测试
pytest tests/datahub/ -v

# 运行特定模块测试
pytest tests/datahub/test_loaders.py -v
pytest tests/datahub/test_domain.py -v
pytest tests/datahub/test_core.py -v
```

## 📊 性能优化建议

1. **利用缓存**：优先从本地缓存读取数据
2. **批量加载**：一次性加载多只股票数据，减少 API 调用次数
3. **按需查询**：只查询需要的列和日期范围
4. **预加载常用数据**：如股票基本信息、行业列表等

## 📊 可用数据字段

DataHub 通过 Tushare API 提供以下标准化字段，**所有字段名与 Tushare 官方保持一致**：

### 基础行情字段 (daily)
- `open`, `high`, `low`, `close` - 开高低收
- `pre_close`, `change`, `pct_chg` - 前收盘、涨跌额、涨跌幅
- `vol`, `amount` - 成交量（手）、成交额（千元）

### 基本信息字段 (stock_basic)
- `ts_code`, `name` - 股票代码、名称
- `area`, `industry`, `market` - 地域、行业、市场
- `list_date` - 上市日期

### 估值指标字段 (daily_basic)
- `turnover_rate`, `turnover_rate_f` - 换手率、自由流通换手率 (%)
- `volume_ratio` - 量比
- `pe`, `pe_ttm` - 市盈率、市盈率(TTM)
- `pb`, `ps`, `ps_ttm` - 市净率、市销率、市销率(TTM)
- `dv_ratio`, `dv_ttm` - 股息率、股息率(TTM) (%)
- `total_share`, `float_share`, `free_share` - 总股本、流通股本、自由流通股本 (万股)
- `total_mv`, `circ_mv` - 总市值、流通市值 (万元)

### 复权因子字段 (adj_factor)
- `adj_factor` - 复权因子

### 资金流向字段 (moneyflow)
- `buy/sm/md/lg/elg_vol/amount` - 小/中/大/特大单买卖量/额
- `net_mf_vol`, `net_mf_amount` - 净流入量/额

### 融资融券字段 (margin_detail)
- `rzye`, `rqye` - 融资余额、融券余额
- `rzmre`, `rzche` - 融资买入额、融资偿还额
- `rqyl`, `rqchl`, `rqmcl` - 融券余量、偿还量、卖出量
- `rzrqye` - 融资融券余额

> **注意**: 字段名已修正为 Tushare 官方标准，如 `volume_ratio` (非 `vol_ratio`)。

## 🔗 相关文档

- [主 README](../README.md)
- [Agent System](./agent_system.md)
- [Screening Engine](./screening_engine.md)
- [Backtest Engine](./backtest_engine.md)

## 📝 更新日志

- **2024-01**: 初始版本，实现核心的 Repository Pattern
- **2024-02**: 添加 Parquet 缓存支持
- **2024-03**: 完善领域实体模型
- **2024-04**: 优化数据加载器接口
