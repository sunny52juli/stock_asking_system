"""Utils 模块 - 统一导出接口."""

# Date utilities
from utils.date import (
    ensure_dir,
    sanitize_filename,
    format_date,
    parse_date,
    get_today_str,
    DATE_FMT_YMD,
    DATE_FMT_ISO,
    DATE_FMT_FULL,
    DATE_FMT_TIMESTAMP,
    # Trade calendar
    count_trade_days,
    calculate_date_offset,
    get_data_start_date,
    DateAdjuster,
)

# Data processing utilities
try:
    from utils.data import (
        pivot_wide,
        rolling_mean,
        rolling_std,
        pct_change,
        ts_rank,
        decay_linear,
        prepare_index_returns,
        merge_stock_with_index_returns,
    )
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

# Cache utilities
from utils.cache import LRUCache, DiskCache, MultiLevelCache

# Logging helpers
from utils.logging import (
    log_success,
    log_warning,
    log_error,
    log_info,
    log_debug,
    log_section,
    log_step,
    LOG_PREFIX_SUCCESS,
    LOG_PREFIX_WARNING,
    LOG_PREFIX_ERROR,
    LOG_PREFIX_INFO,
    LOG_PREFIX_DEBUG,
)

# Error formatter
from utils.errors import (
    format_error_message,
    format_validation_error,
    format_tool_error,
)

__all__ = [
    # Date
    "ensure_dir",
    "sanitize_filename",
    "format_date",
    "parse_date",
    "get_today_str",
    "DATE_FMT_YMD",
    "DATE_FMT_ISO",
    "DATE_FMT_FULL",
    "DATE_FMT_TIMESTAMP",
    # Trade calendar
    "count_trade_days",
    "calculate_date_offset",
    "get_data_start_date",
    "DateAdjuster",
    # Data processing
    "pivot_wide",
    "rolling_mean",
    "rolling_std",
    "pct_change",
    "ts_rank",
    "decay_linear",
    "prepare_index_returns",
    "merge_stock_with_index_returns",
    "POLARS_AVAILABLE",
    # Cache
    "LRUCache",
    "DiskCache",
    "MultiLevelCache",
    # Logging
    "log_success",
    "log_warning",
    "log_error",
    "log_info",
    "log_debug",
    "log_section",
    "log_step",
    "LOG_PREFIX_SUCCESS",
    "LOG_PREFIX_WARNING",
    "LOG_PREFIX_ERROR",
    "LOG_PREFIX_INFO",
    "LOG_PREFIX_DEBUG",
    # Errors
    "format_error_message",
    "format_validation_error",
    "format_tool_error",
]
