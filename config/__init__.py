"""
配置模块 - 统一配置管理

按功能拆分：
- api_config: API 相关配置
- data_config: 数据源、路径、质量配置
- stock_config: 股票池和回测配置
- screener_deepagent_config: DeepAgent 专属配置
"""

from typing import Any

from config.api_config import APIConfig
from config.data_config import DataConfig
from config.screener_deepagent_config import ScreenerDeepAgentConfig, data_accessor
from config.backtest_config import StockConfig


# 统一配置类（向后兼容）
class Config:
    """统一配置类 - 整合所有配置模块（向后兼容）"""
    
    # API 配置
    DEFAULT_API_URL = APIConfig.DEFAULT_API_URL
    DEFAULT_API_KEY = APIConfig.DEFAULT_API_KEY
    DEFAULT_MODEL = APIConfig.DEFAULT_MODEL
    MAX_ITERATIONS = APIConfig.MAX_ITERATIONS
    MAX_TOKENS = APIConfig.MAX_TOKENS
    TEMPERATURE = APIConfig.TEMPERATURE
    
    # 数据配置
    DATA_SOURCE_TOKEN = DataConfig.DATA_SOURCE_TOKEN
    DATA_CACHE_ROOT = DataConfig.DATA_CACHE_ROOT
    DAILY_DATA_DIR = DataConfig.DAILY_DATA_DIR
    INDICES_DATA_DIR = DataConfig.INDICES_DATA_DIR
    BY_DATE_DATA_DIR = DataConfig.BY_DATE_DATA_DIR
    FACTOR_DATA_DIR = DataConfig.FACTOR_DATA_DIR
    BACKTEST_DATA_DIR = DataConfig.BACKTEST_DATA_DIR
    MIN_DATA_COMPLETENESS_RATIO = DataConfig.MIN_DATA_COMPLETENESS_RATIO
    MAX_MISSING_DAYS = DataConfig.MAX_MISSING_DAYS
    MIN_PRICE = DataConfig.MIN_PRICE
    MAX_PRICE = DataConfig.MAX_PRICE
    MIN_VOL = DataConfig.MIN_VOL
    
    # 股票配置
    STOCK_POOL_MIN_LIST_DAYS = StockConfig.STOCK_POOL_MIN_LIST_DAYS
    STOCK_POOL_EXCLUDE_ST = StockConfig.STOCK_POOL_EXCLUDE_ST
    EXCLUDE_SUSPENDED_STOCKS = StockConfig.EXCLUDE_SUSPENDED_STOCKS
    BACKTEST_DEFAULT_INDEX_CODE = StockConfig.BACKTEST_DEFAULT_INDEX_CODE
    BACKTEST_LOOKBACK_DAYS = StockConfig.BACKTEST_LOOKBACK_DAYS
    
    # 便捷方法
    @classmethod
    def get_api_config(cls) -> dict[str, Any]:
        return APIConfig.get_api_config()
    
    @classmethod
    def get_data_config(cls) -> dict[str, Any]:
        return DataConfig.get_data_config()
    
    @classmethod
    def get_stock_pool_rules(cls) -> dict[str, Any]:
        return StockConfig.get_stock_pool_rules()


# 向后兼容别名
BacktestConfig = StockConfig  # type: ignore
FactorBacktestConfig = StockConfig  # type: ignore
StockPoolConfig = StockConfig  # type: ignore

__all__ = [
    # 核心配置类
    "APIConfig",
    "DataConfig",
    "StockConfig",
    # 统一配置（向后兼容）
    "Config",
    # 公共配置别名（向后兼容）
    "BacktestConfig",
    "FactorBacktestConfig",
    "StockPoolConfig",
    # 系统专属配置
    "ScreenerDeepAgentConfig",
    "data_accessor",
]
