"""统一配置管理 - 多层配置架构.

配置加载顺序（后者覆盖前者）:
1. setting/screening.yaml - 策略配置和高级配置
2. setting/stock_pool.yaml - 股票池配置
3. setting/backtest.yaml - 回测配置
4. 环境变量 ${VAR:-default} (.env 文件)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class LLMConfig(BaseModel):
    """LLM配置."""
    model: str = Field(default=os.getenv("DEFAULT_MODEL", "deepseek-chat"))
    api_key: str = Field(default=os.getenv("DEFAULT_API_KEY", ""))
    api_url: str = Field(default=os.getenv("DEFAULT_API_URL", "https://api.deepseek.com/v1"))
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.api_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


class DataConfig(BaseModel):
    """数据配置."""
    cache_root: Path = Field(
        default=Path(os.getenv("DATA_CACHE_ROOT", "./data_cache"))
    )
    source_token: str = Field(default=os.getenv("DATA_SOURCE_TOKEN", ""))


class BacktestConfig(BaseModel):
    """回测配置."""
    holding_periods: list[int] = Field(default=[4, 10, 20])
    screening_date: str = Field(default="20260201")
    index_code: str | None = Field(default=None)
    # observation_days 已移除，统一使用全局 observation_period_days


class StockPoolConfig(BaseModel):
    """股票池筛选配置."""
    min_list_days: int = Field(default=180, gt=0)
    exclude_st: bool = Field(default=True)
    exclude_suspended: bool = Field(default=True)
    industry: list[str] | None = Field(default=None)  # 行业过滤列表（支持模糊匹配），None表示全市场
    
    # 数据质量参数
    min_completeness_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    max_missing_days: int = Field(default=5, gt=0)
    min_price: float = Field(default=0.0, ge=0.0)  # 0表示不过滤
    max_price: float = Field(default=999999, gt=0)  # 极大值表示不过滤
    min_vol: float = Field(default=0.0, ge=0.0)  # 0表示不过滤
    min_amount: float = Field(default=0.0, ge=0.0)  # 最小成交金额，0表示不过滤
    min_turnover: float = Field(default=0.0, ge=0.0)  # 最小换手率，0表示不过滤
    min_total_mv: float = Field(default=0.0, ge=0.0)  # 最小总市值（万元），0表示不过滤
    max_total_mv: float = Field(default=999999999, gt=0)  # 最大总市值（万元），极大值表示不过滤


class OutputConfig(BaseModel):
    """输出配置."""
    strategies_dir: Path = Field(
        default=Path(os.getenv("SCREENER_SCRIPTS_DIR", "./screening_scripts"))
    )
    auto_save_script: bool = Field(default=False)  # 是否自动保存脚本，不询问用户


class HarnessConfig(BaseModel):
    """约束框架配置."""
    max_iterations: int = Field(default=25, gt=0)
    max_consecutive_errors: int = Field(default=3, gt=0)
    max_execution_time: int = Field(default=300, gt=0)
    deep_thinking: bool = Field(default=False)  # 是否启用深度思考模式
    hooks: dict[str, Any] = Field(default_factory=lambda: {
        "PreToolUse": [
            {
                "matcher": "run_screening",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python hooks/validate-strategy.py"
                    }
                ]
            }
        ],
        "PostToolUse": [],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python hooks/quality-gate.py"
                    }
                ]
            }
        ]
    })


class PermissionsConfig(BaseModel):
    """权限配置."""
    allow: list[str] = Field(default=["*"])
    deny: list[str] = Field(default=[])


class MCPConfig(BaseModel):
    """MCP 服务配置."""
    pass


class StrategyConfig(BaseModel):
    """策略生成配置."""
    screening_date: str = Field(default="20260320")
    # observation_days已移除，统一使用 backtest.observation_days


class StrategyTemplateConfig(BaseModel):
    """单个策略模板配置."""
    query: str = Field(default="")
    strategy_num: int = Field(default=1, gt=0)
    # observation_days已移除，统一使用 backtest.observation_days


class StrategiesConfig(BaseModel):
    """策略模板集合配置."""
    # 动态字段，允许任意策略名称
    model_config = ConfigDict(extra="allow")


class Settings(BaseModel):
    """全局设置."""
    model_config = ConfigDict(frozen=False)
    
    llm: LLMConfig = Field(default_factory=LLMConfig)
    strategies: dict[str, StrategyTemplateConfig] = Field(default_factory=dict)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    stock_pool: StockPoolConfig = Field(default_factory=StockPoolConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    
    # 全局观察期配置（统一使用此配置）
    observation_days: int = Field(default=80, gt=0, description="全局观察期长度（交易日），用于所有策略生成、回测和指标计算")


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """加载YAML文件."""
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}")
        return {}


def _expand_env_vars(obj: Any) -> Any:
    """递归展开环境变量."""
    if isinstance(obj, str):
        import re
        # 支持 ${VAR} 和 ${VAR:-default} 两种格式
        pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ''
            return os.getenv(var_name, default_value)
        return re.sub(pattern, replacer, obj)
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


def load_settings(project_root: Path | None = None, config_files: list[str] | None = None) -> Settings:
    """加载配置（多层合并）.
    
    加载顺序:
    1. setting/screening.yaml - 策略配置和高级配置
    2. setting/stock_pool.yaml - 股票池配置
    3. setting/backtest.yaml - 回测配置
    4. 环境变量 ${VAR:-default} (.env 文件)
    
    Args:
        project_root: 项目根目录
        config_files: 指定要加载的配置文件列表（相对于 setting/ 目录），
                     为 None 时加载所有配置文件
        
    Returns:
        Settings实例
    """
    if project_root is None:
        project_root = Path.cwd()
    
    # 默认加载所有配置文件
    if config_files is None:
        config_files = [
            "screening.yaml",
            "stock_pool.yaml",
            "backtest.yaml",
        ]
    
    # 构建完整路径
    config_paths = [project_root / "setting" / f for f in config_files]
    
    # 按顺序加载并合并
    config_dict = {}
    for config_path in config_paths:
        loaded = _load_yaml_file(config_path)
        if loaded:
            # 深度合并（注意：需要接收返回值）
            config_dict = _deep_merge(config_dict, loaded)
    
    # 展开环境变量
    config_dict = _expand_env_vars(config_dict)
    
    # 转换为Settings对象
    return Settings(**config_dict)


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# 单例缓存
_settings_cache: Settings | None = None


def get_settings(reload: bool = False, config_files: list[str] | None = None) -> Settings:
    """获取全局设置（单例模式）.
    
    Args:
        reload: 是否重新加载配置
        config_files: 指定要加载的配置文件列表，为 None 时加载所有
        
    Returns:
        Settings实例
    """
    global _settings_cache
    if _settings_cache is None or reload:
        _settings_cache = load_settings(config_files=config_files)
    return _settings_cache
