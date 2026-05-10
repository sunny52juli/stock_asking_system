#!/usr/bin/env python3
"""股票筛选执行引擎 (Utils).

委托给 src.screening.executor.ScreeningExecutor 执行实际筛选逻辑。
"""

from typing import Any, Optional
import polars as pl

from infrastructure.logging.logger import get_logger
from src.screening.executor import ScreeningExecutor

logger = get_logger(__name__)

# ✅ 全局变量：存储最后一次质量评估的建议（用于迭代时输出）
_last_quality_suggestions: list[str] = []


def set_last_quality_suggestions(suggestions: list[str]):
    """设置最后一次质量评估的建议（供 Harness 框架调用）.
    
    Args:
        suggestions: 质量评估器返回的建议列表
    """
    global _last_quality_suggestions
    _last_quality_suggestions = suggestions


def get_last_quality_suggestions() -> str:
    """获取最后一次质量评估的建议（用于迭代时输出）.
    
    Returns:
        格式化的建议字符串
    """
    if not _last_quality_suggestions:
        return ""
    
    # 将建议列表合并为单个字符串
    return "\n   ".join(_last_quality_suggestions)


class StockScreener:
    """股票筛选器.
    
    委托给 src.screening.executor.ScreeningExecutor 执行实际筛选。
    """

    def __init__(
        self,
        data: pl.DataFrame,
        screening_date: Optional[str] = None,
        stock_codes: Optional[list[str]] = None,
        index_data: Optional[pl.DataFrame] = None,
    ):
        """初始化股票筛选器（兼容旧接口）.
        
        Args:
            data: 市场数据 DataFrame (MultiIndex: trade_date, ts_code)
            screening_date: 筛选日期（YYYYMMDD 格式），默认使用最新交易日
            stock_codes: 预筛选后的股票代码列表（可选，将被忽略）
            index_data: 指数数据 DataFrame (columns: trade_date, index_close)，可选
        """
        
        self.data = data
        self.index_data = index_data
        
        # 如果已提供有效的指数数据，直接使用
        if index_data is not None:
            if not index_data.is_empty():
                logger.info(f"✅ StockScreener 使用传入的指数数据: {len(index_data)} 条记录")
                logger.debug(f"   指数数据列: {list(index_data.columns)}")
            else:
                logger.warning("⚠️ 传入的指数数据为空")
                index_data = None
        else:
            # 仅在未提供指数数据时尝试自动加载
            logger.info("📊 未提供指数数据，尝试自动加载...")
            try:
                # 延迟导入以避免循环依赖
                from src.agent.services.index_loader import IndexDataLoader
                loader = IndexDataLoader()
                
                # 需要加载独立的指数数据，而不是合并后的数据
                # 使用内部方法直接加载指数数据
                if stock_codes:
                    codes_to_process = stock_codes
                else:
                    codes_to_process = data.select(pl.col('ts_code').unique()).to_series().to_list()
                
                # 确定指数代码列表
                unique_indices = set()
                for code in codes_to_process[:100]:  # 限制数量以提高性能
                    from datahub.domain.index_selector import get_index_code
                    idx_code = get_index_code(code)
                    unique_indices.add(idx_code)
                
                if unique_indices:
                    # 提取日期范围
                    dates = data.select(pl.col('trade_date').unique()).to_series()
                    if len(dates) > 0:
                        min_date = dates.min()
                        max_date = dates.max()
                        if hasattr(min_date, 'strftime'):
                            start_date = min_date.strftime('%Y%m%d')
                            end_date = max_date.strftime('%Y%m%d')
                        else:
                            start_date = str(min_date).replace('-', '')[:8]
                            end_date = str(max_date).replace('-', '')[:8]
                        
                        # 加载所有指数数据
                        all_index_data = []
                        missing_indices = []
                        for idx_code in unique_indices:
                            index_data = loader._load_index_data(idx_code, start_date, end_date)
                            if not index_data.is_empty():
                                all_index_data.append(index_data)
                            else:
                                missing_indices.append(idx_code)
                        
                        # 如果有缺失的指数数据，尝试同步
                        if missing_indices:
                            logger.warning(f"⚠️ 发现 {len(missing_indices)} 个指数的缓存数据缺失: {missing_indices}")
                            logger.info("🔄 尝试同步缺失的指数数据...")
                            try:
                                self._sync_missing_indices(missing_indices)
                                
                                # 重新加载
                                for idx_code in missing_indices:
                                    index_data = loader._load_index_data(idx_code, start_date, end_date)
                                    if not index_data.is_empty():
                                        all_index_data.append(index_data)
                                        logger.info(f"✅ 成功同步并加载指数 {idx_code}")
                                    else:
                                        logger.warning(f"⚠️ 同步后仍无法加载指数 {idx_code}")
                            except Exception as sync_error:
                                logger.error(f"❌ 同步指数数据失败: {sync_error}")
                        
                        if all_index_data:
                            # 合并所有指数数据
                            self.index_data = pl.concat(all_index_data).sort('trade_date')
                            logger.info(f"✅ 成功加载指数数据: {len(self.index_data)} 条记录")
                        else:
                            logger.warning("⚠️ 无法加载任何指数数据")
                    else:
                        logger.warning("⚠️ 无法提取日期范围")
                else:
                    logger.warning("⚠️ 无法确定指数代码")
            except Exception as e:
                logger.warning(f"⚠️ 自动加载指数数据失败: {e}")
        
        # 创建实际的筛选执行器，传递独立的指数数据
        
        # 验证数据格式（Polars DataFrame）
        required_cols = ['ts_code', 'trade_date']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            raise ValueError(f"Polars DataFrame 缺少必需列: {missing_cols}")
        
        self._executor = ScreeningExecutor(
            data=self.data,
            screening_date=screening_date,
            index_data=self.index_data
        )
        
        # 保存参数用于日志
        self.screening_date_str = screening_date or self._executor.screening_date_str
        self.latest_date = self._executor.latest_date

    def execute_screening(
        self, screening_logic: dict, top_n: int = 10, query: str = "", iteration: int = 1, retry_reason: str = ""
    ) -> list[dict[str, Any]]:
        """执行股票筛选（兼容旧接口）.
        
        Args:
            screening_logic: 筛选逻辑配置
            top_n: 返回前 N 只股票
            query: 原始查询文本
            iteration: 重试次数（仅用于日志，不影响实际逻辑）
            retry_reason: 重试原因（来自质量评估器的 suggestions）
            
        Returns:
            候选股票列表
        """
        if iteration > 1:
            logger.info(f"🔄 第 {iteration} 次筛选迭代...")
            
            # ✅ 从全局变量获取质量评估建议
            retry_reason = retry_reason or get_last_quality_suggestions()
            if retry_reason:
                logger.info(f"   📝 迭代原因: {retry_reason}")
                # 提取本次更新内容（从 screening_logic 中）
                expression = screening_logic.get("expression", "")
                tools = screening_logic.get("tools", [])
                if expression:
                    logger.info(f"   🔧 本次更新: 表达式 = {expression}")
                if tools:
                    tool_names = [t.get('var', t.get('tool', '')) for t in tools]
                    logger.info(f"   🔧 本次更新: 工具 = {', '.join(tool_names)}")
        
        # 委托给实际的执行器
        return self._executor.run_screening(
            screening_logic=screening_logic,
            top_n=top_n,
            query=query,
        )
    
    def _sync_missing_indices(self, missing_indices: list[str]):
        """同步缺失的指数数据。
        
        Args:
            missing_indices: 缺失的指数代码列表
        """
        if not missing_indices:
            return
        
        import sys
        import subprocess
        
        try:
            codes_str = ','.join(missing_indices)
            # 正确的命令格式：datahub index sync --codes ...
            sync_cmd = [
                sys.executable, '-m', 'datahub', 'index', 'sync',
                '--codes', codes_str
            ]
            
            logger.info(f"   执行命令: {' '.join(sync_cmd)}")
            result = subprocess.run(
                sync_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info("✅ 指数数据同步成功")
            else:
                logger.error(f"❌ 指数数据同步失败: {result.stderr}")
                raise RuntimeError(f"同步失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("❌ 指数数据同步超时")
            raise
        except Exception as e:
            logger.error(f"❌ 指数数据同步异常: {e}")
            raise


def create_stock_screener(
    data: pl.DataFrame,
    screening_date: Optional[str] = None,
    stock_codes: Optional[list[str]] = None,
    index_data: Optional[pl.DataFrame] = None,
) -> StockScreener:
    """创建 StockScreener 实例的便捷函数（兼容旧接口）。"""
    return StockScreener(
        data=data,
        screening_date=screening_date,
        stock_codes=stock_codes,
        index_data=index_data,
    )
