"""Utils 模块 - 统一导出接口."""

# File system utilities
from utils.fs import ensure_dir, sanitize_filename

# Datetime utilities
from utils.datetime_utils import format_date, parse_date

# Polars tools (performance optimization)
try:
    from utils.polars_tools import (
        pivot_wide,
        rolling_mean,
        rolling_std,
        pct_change,
        ts_rank,
        decay_linear,
    )
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

# Logging
from infrastructure.logging.logger import get_logger

# Errors  
from infrastructure.errors.exceptions import ScreeningError, DataLoadError, ConfigError

# Paths
from infrastructure.paths.path_manager import PathManager, ensure_project_path, get_path_manager, get_project_root

# Config
from infrastructure.config.settings import get_settings, Settings

# Data
from datahub.data_fields import DataFields

# Note: Agent imports removed to avoid circular dependency with datahub
# If you need PermissionChecker, import directly: from utils.agent.permissions import PermissionChecker

__all__ = [
    # File system
    "sanitize_filename",
    "ensure_dir",
    # Datetime
    "format_date",
    "parse_date",
    # Polars tools
    "pivot_wide",
    "rolling_mean",
    "rolling_std",
    "pct_change",
    "ts_rank",
    "decay_linear",
    "POLARS_AVAILABLE",
    # Infrastructure
    "get_logger", "ScreeningError", "DataLoadError", "ConfigError",
    "PathManager", "ensure_project_path", "get_path_manager", "get_project_root",
    "get_settings", "Settings", "DataFields",
]
