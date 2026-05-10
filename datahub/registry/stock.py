"""股票数据集注册 - 从YAML配置加载."""

from pathlib import Path

from datahub.registry.config_loader import DatasetConfigLoader

# 加载YAML配置
_config_path = Path(__file__).parent / "stock_datasets.yaml"
DatasetConfigLoader.load_from_yaml(_config_path)
