"""
数据配置模块 - 管理所有数据源相关的配置
包含数据缓存路径、数据质量配置等
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录下的数据缓存目录
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_CACHE_ROOT = _PROJECT_ROOT / "data_cache"


class DataConfig:
    """数据配置类 - 包含所有数据源相关的配置"""

    # ==================== 数据源配置 ====================
    DATA_SOURCE_TOKEN = os.getenv("DATA_SOURCE_TOKEN")

    # ==================== 数据缓存路径配置 ====================
    DATA_CACHE_ROOT = str(_DEFAULT_CACHE_ROOT)
    Path(DATA_CACHE_ROOT).mkdir(parents=True, exist_ok=True)

    # 子目录配置
    DAILY_DATA_DIR = Path(DATA_CACHE_ROOT) / "daily"  # 日线数据目录
    INDICES_DATA_DIR = Path(DATA_CACHE_ROOT) / "indices"  # 指数数据目录
    BY_DATE_DATA_DIR = Path(DATA_CACHE_ROOT) / "by_date"  # 按日期分类数据目录
    FACTOR_DATA_DIR = Path(DATA_CACHE_ROOT) / "factors"  # 因子数据目录
    BACKTEST_DATA_DIR = Path(DATA_CACHE_ROOT) / "backtest"  # 回测数据目录
    TRADE_CALENDAR_DIR = Path(DATA_CACHE_ROOT) / "stock" / "trade_calendar"  # 交易日历数据目录

    # ==================== 数据质量配置 ====================
    # 数据完整性检查
    MIN_DATA_COMPLETENESS_RATIO = 0.8  # 最小数据完整率
    MAX_MISSING_DAYS = 5  # 最大连续缺失天数

    # 数据有效性检查
    MIN_PRICE = 0.01  # 最小有效价格
    MAX_PRICE = 10000  # 最大有效价格
    MIN_VOL = 1000  # 最小有效成交量

    @classmethod
    def get_data_config(cls) -> dict[str, Any]:
        """
        获取数据配置字典

        Returns:
            dict: 包含所有数据配置的字典
        """
        return {
            # 数据源配置
            "token": cls.DATA_SOURCE_TOKEN,
            # 缓存路径配置
            "data_cache_root": cls.DATA_CACHE_ROOT,
            "daily_data_dir": str(cls.DAILY_DATA_DIR),
            "indices_data_dir": str(cls.INDICES_DATA_DIR),
            "by_date_data_dir": str(cls.BY_DATE_DATA_DIR),
            "factor_data_dir": str(cls.FACTOR_DATA_DIR),
            "backtest_data_dir": str(cls.BACKTEST_DATA_DIR),
            "trade_calendar_dir": str(cls.TRADE_CALENDAR_DIR),
            # 数据质量配置
            "min_data_completeness_ratio": cls.MIN_DATA_COMPLETENESS_RATIO,
            "max_missing_days": cls.MAX_MISSING_DAYS,
            "min_price": cls.MIN_PRICE,
            "max_price": cls.MAX_PRICE,
            "min_vol": cls.MIN_VOL,
        }

    @classmethod
    def get_cache_paths(cls) -> dict[str, str]:
        """
        获取缓存路径配置

        Returns:
            dict: 缓存路径字典
        """
        return {
            "root": cls.DATA_CACHE_ROOT,
            "daily": str(cls.DAILY_DATA_DIR),
            "indices": str(cls.INDICES_DATA_DIR),
            "by_date": str(cls.BY_DATE_DATA_DIR),
            "factors": str(cls.FACTOR_DATA_DIR),
            "backtest": str(cls.BACKTEST_DATA_DIR),
            "trade_calendar": str(cls.TRADE_CALENDAR_DIR),
        }
