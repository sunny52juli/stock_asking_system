"""配置键名常量 - 统一管理所有配置项的键名.

避免魔法字符串，提供IDE自动补全和类型检查。
"""

from __future__ import annotations


# ==================== LLM 配置键名 ====================

LLM_MODEL = "model"
LLM_API_KEY = "api_key"
LLM_API_URL = "api_url"
LLM_BASE_URL = "base_url"  # API转换后的键名
LLM_TEMPERATURE = "temperature"
LLM_MAX_TOKENS = "max_tokens"


# ==================== 数据配置键名 ====================

DATA_CACHE_ROOT = "cache_root"
DATA_SOURCE_TOKEN = "source_token"


# ==================== 回测配置键名 ====================

BACKTEST_HOLDING_PERIODS = "holding_periods"
BACKTEST_SCREENING_DATE = "screening_date"


# ==================== 股票池配置键名 ====================

STOCK_POOL_MIN_LIST_DAYS = "min_list_days"
STOCK_POOL_EXCLUDE_ST = "exclude_st"
STOCK_POOL_EXCLUDE_SUSPENDED = "exclude_suspended"
STOCK_POOL_INDUSTRY = "industry"

# 数据质量参数
STOCK_POOL_MIN_COMPLETENESS_RATIO = "min_completeness_ratio"
STOCK_POOL_MAX_MISSING_DAYS = "max_missing_days"
STOCK_POOL_MIN_PRICE = "min_price"
STOCK_POOL_MAX_PRICE = "max_price"
STOCK_POOL_MIN_VOL = "min_vol"
STOCK_POOL_MIN_AMOUNT = "min_amount"
STOCK_POOL_MIN_TURNOVER = "min_turnover"
STOCK_POOL_MIN_TOTAL_MV = "min_total_mv"
STOCK_POOL_MAX_TOTAL_MV = "max_total_mv"


# ==================== 输出配置键名 ====================

OUTPUT_STRATEGIES_DIR = "strategies_dir"


# ==================== Harness 配置键名 ====================

HARNESS_MAX_ITERATIONS = "max_iterations"
HARNESS_MAX_CONSECUTIVE_ERRORS = "max_consecutive_errors"
HARNESS_MAX_EXECUTION_TIME = "max_execution_time"
HARNESS_HOOKS = "hooks"

# Hook 类型
HOOK_PRE_TOOL_USE = "PreToolUse"
HOOK_POST_TOOL_USE = "PostToolUse"
HOOK_STOP = "Stop"

# Hook 匹配器
MATCHER_RUN_SCREENING = "run_screening"
MATCHER_ALL = ".*"

# Hook 命令
HOOK_VALIDATE_STRATEGY = "python hooks/validate-strategy.py"
HOOK_VALIDATE_TOOL_CALL = "python hooks/validate-tool-call.py"
HOOK_QUALITY_GATE = "python hooks/quality-gate.py"


# ==================== 权限配置键名 ====================

PERMISSIONS_ALLOW = "allow"
PERMISSIONS_DENY = "deny"


# ==================== 策略配置键名 ====================

STRATEGY_SCREENING_DATE = "screening_date"
STRATEGY_QUERY = "query"
STRATEGY_NUM = "strategy_num"


# ==================== 全局配置键名 ====================

OBSERVATION_DAYS = "observation_days"


# ==================== 环境变量键名 ====================

ENV_DEFAULT_MODEL = "DEFAULT_MODEL"
ENV_DEFAULT_API_KEY = "DEFAULT_API_KEY"
ENV_DEFAULT_API_URL = "DEFAULT_API_URL"
ENV_DATA_CACHE_ROOT = "DATA_CACHE_ROOT"
ENV_DATA_SOURCE_TOKEN = "DATA_SOURCE_TOKEN"
ENV_SCREENER_SCRIPTS_DIR = "SCREENER_SCRIPTS_DIR"


# ==================== 默认值常量 ====================

# LLM 默认值
DEFAULT_LLM_MODEL = "deepseek-chat"
DEFAULT_LLM_API_URL = "https://api.deepseek.com/v1"
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_LLM_MAX_TOKENS = 4096

# 数据默认值
DEFAULT_DATA_CACHE_ROOT = "./data_cache"
DEFAULT_SCREENER_SCRIPTS_DIR = "./app/screening_scripts"

# 回测默认值
DEFAULT_HOLDING_PERIODS = [4, 10, 20]
DEFAULT_SCREENING_DATE = "20260201"

# 股票池默认值
DEFAULT_MIN_LIST_DAYS = 180
DEFAULT_EXCLUDE_ST = True
DEFAULT_EXCLUDE_SUSPENDED = True
DEFAULT_MIN_COMPLETENESS_RATIO = 0.8
DEFAULT_MAX_MISSING_DAYS = 5
DEFAULT_MIN_PRICE = 0.0
DEFAULT_MAX_PRICE = 999999
DEFAULT_MIN_VOL = 0.0
DEFAULT_MIN_AMOUNT = 0.0
DEFAULT_MIN_TURNOVER = 0.0
DEFAULT_MIN_TOTAL_MV = 0.0
DEFAULT_MAX_TOTAL_MV = 999999999

# Harness 默认值
DEFAULT_MAX_ITERATIONS = 3
DEFAULT_MAX_CONSECUTIVE_ERRORS = 3
DEFAULT_MAX_EXECUTION_TIME = 300

# 观察期默认值
DEFAULT_OBSERVATION_DAYS = 80


# ==================== 错误码常量 ====================

# 数据相关 (1xxx)
ERR_DATA_NOT_FOUND = 1001
ERR_DATA_FORMAT_ERROR = 1002
ERR_DATA_LOADING_FAILED = 1003
ERR_INDEX_DATA_MISSING = 1004

# 工具执行 (2xxx)
ERR_TOOL_NOT_FOUND = 2001
ERR_TOOL_PARAM_ERROR = 2002
ERR_TOOL_EXECUTION_FAILED = 2003

# 筛选引擎 (3xxx)
ERR_SCREENING_FAILED = 3001
ERR_EXPRESSION_EVAL_ERROR = 3002
ERR_NO_VALID_STOCKS = 3003

# Agent 相关 (4xxx)
ERR_AGENT_TIMEOUT = 4001
ERR_AGENT_MAX_RETRIES = 4002
ERR_AGENT_INVALID_RESPONSE = 4003

# 配置错误 (5xxx)
ERR_CONFIG_MISSING = 5001
ERR_CONFIG_INVALID = 5002


# ==================== HTTP 状态码常量 ====================

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500


# ==================== 日期格式常量（引用）====================
# 从 utils.datetime_utils 导入，避免重复定义
# from utils.date import DATE_FMT_YMD, DATE_FMT_ISO, DATE_FMT_FULL, DATE_FMT_TIMESTAMP
