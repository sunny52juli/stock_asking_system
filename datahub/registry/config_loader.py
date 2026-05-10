"""数据集配置加载器 - 从YAML文件加载数据集注册配置."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from datahub.core.dataset import Dataset, DatasetMeta, DatasetRegistry, FetchStep

logger = logging.getLogger(__name__)


class DatasetConfigLoader:
    """数据集配置加载器 - 从YAML加载并注册数据集."""
    
    @staticmethod
    def load_from_yaml(yaml_path: str | Path):
        """从YAML文件加载并注册所有数据集.
        
        Args:
            yaml_path: YAML配置文件路径
        """
        yaml_path = Path(yaml_path)
        
        if not yaml_path.exists():
            logger.error(f"[ERROR] 配置文件不存在: {yaml_path}")
            return
        
        logger.info(f"📖 加载数据集配置: {yaml_path}")
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            datasets = config.get('datasets', {})
            
            for dataset_name, dataset_config in datasets.items():
                DatasetConfigLoader._register_dataset(dataset_name, dataset_config)
            
            logger.info(f"[OK] 成功注册 {len(datasets)} 个数据集")
            
        except Exception as e:
            logger.error(f"[ERROR] 加载配置文件失败: {e}", exc_info=True)
            raise
    
    @staticmethod
    def _register_dataset(dataset_name: str, config: dict[str, Any]):
        """注册单个数据集.
        
        Args:
            dataset_name: 数据集名称
            config: 数据集配置
        """
        # 解析元信息
        meta_config = config['meta']
        meta = DatasetMeta(
            dataset=Dataset[dataset_name],
            domain=meta_config['domain'],
            partition_by=meta_config['partition_by'],
            key_columns=meta_config['key_columns'],
            storage_path=meta_config['storage_path'],
            date_column=meta_config['date_column'],
            code_column=meta_config['code_column'],
            partition_key_template=meta_config['partition_key_template'],
            description=meta_config.get('description', ''),
        )
        
        # 解析管道步骤
        pipeline = [
            DatasetConfigLoader._parse_fetch_step(step_config)
            for step_config in config.get('pipeline', [])
        ]
        
        # 注册数据集
        DatasetRegistry.register(meta, pipeline=pipeline)
        logger.debug(f"  [OK] 注册数据集: {dataset_name} ({len(pipeline)}步管道)")
    
    @staticmethod
    def _parse_fetch_step(config: dict[str, Any]) -> FetchStep:
        """解析FetchStep配置.
        
        Args:
            config: FetchStep配置字典
            
        Returns:
            FetchStep实例
        """
        return FetchStep(
            api_name=config['api_name'],
            param_mapping=config.get('param_mapping', {}),
            fixed_params=config.get('fixed_params', {}),
            fields=config.get('fields'),
            merge_on=config.get('merge_on', []),
            optional=config.get('optional', False),
        )
