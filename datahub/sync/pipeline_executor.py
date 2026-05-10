"""管道执行器 - 负责执行数据获取管道."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from datahub.core.dataset import FetchStep
    from datahub.core.query import Query
    from datahub.core.source import DataSource

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """管道执行器 - 执行FetchStep管道."""
    
    def __init__(self, source: DataSource):
        """初始化.
        
        Args:
            source: 数据源
        """
        self.source = source
    
    def execute(self, pipeline: list[FetchStep], query: Query) -> pl.DataFrame | None:
        """执行管道.
        
        Args:
            pipeline: FetchStep列表
            query: 查询对象
            
        Returns:
            合并后的DataFrame或None
        """
        if not pipeline:
            return None
        
        result = None
        
        for i, step in enumerate(pipeline):
            logger.debug(f"执行管道步骤 {i+1}/{len(pipeline)}: {step.api_name}")
            
            try:
                step_data = self._execute_step(step, query)
                
                if step_data is None or step_data.is_empty():
                    if step.optional:
                        logger.debug(f"步骤 {step.api_name} 返回空数据（可选），跳过")
                        continue
                    else:
                        logger.warning(f"步骤 {step.api_name} 返回空数据（必需）")
                        return None
                
                # 合并数据
                if result is None:
                    result = step_data
                else:
                    result = self._merge_data(result, step_data, step.merge_on)
                    
            except Exception as e:
                if step.optional:
                    logger.warning(f"步骤 {step.api_name} 执行失败（可选）: {e}")
                    continue
                else:
                    logger.error(f"步骤 {step.api_name} 执行失败（必需）: {e}")
                    raise
        
        return result
    
    def _execute_step(self, step: FetchStep, query: Query) -> pl.DataFrame | None:
        """执行单个FetchStep.
        
        Args:
            step: FetchStep配置
            query: 查询对象
            
        Returns:
            数据DataFrame或None
        """
        # 构建参数
        params = {}
        
        # 应用参数映射
        for param_name, source_field in step.param_mapping.items():
            if hasattr(query, source_field):
                params[param_name] = getattr(query, source_field)
        
        # 应用固定参数
        if step.fixed_params:
            params.update(step.fixed_params)
        
        # 调用数据源
        try:
            data = self.source.fetch(
                api_name=step.api_name,
                params=params,
                fields=step.fields,
            )
            return data
        except Exception as e:
            logger.error(f"数据源调用失败 {step.api_name}: {e}")
            return None
    
    def _merge_data(
        self,
        base: pl.DataFrame,
        new_data: pl.DataFrame,
        merge_on: list[str]
    ) -> pl.DataFrame:
        """合并两个DataFrame.
        
        Args:
            base: 基础DataFrame
            new_data: 新数据DataFrame
            merge_on: 合并键
            
        Returns:
            合并后的DataFrame
        """
        if not merge_on:
            # 无合并键，直接拼接列
            return pl.concat([base, new_data], how="horizontal")
        
        # 左连接，处理可能的列名冲突
        result = base.join(new_data, on=merge_on, how="left", suffix="_dup")
        
        # 移除带 _dup 后缀的列（保留左侧的原始列）
        dup_cols = [col for col in result.columns if col.endswith("_dup")]
        if dup_cols:
            result = result.drop(dup_cols)
        
        return result
