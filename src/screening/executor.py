"""筛选执行器 - 负责高效执行股票筛选逻辑.

本模块从 utils/screening/stock_screener.py 重构而来，
职责更加清晰，命名更加语义化。

已拆分为：
- prefilter.py: 预筛选逻辑
- batch_calculator.py: 批量计算引擎
"""
from typing import Any, Optional
import polars as pl
from datetime import datetime

from datahub import Calendar
from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import get_logger
from src.screening.batch_calculator import BatchCalculator

logger = get_logger(__name__)


class ScreeningExecutor:
    """股票筛选执行器 - 组合预筛选和批量计算."""

    def __init__(self, data: pl.DataFrame, screening_date: Optional[str] = None, index_data: Optional[pl.DataFrame] = None):
        """初始化股票筛选器.
        
        Args:
            data: 市场数据 DataFrame (columns: ts_code, trade_date, ...)
            screening_date: 筛选日期（YYYYMMDD 格式），默认使用最新交易日
            index_data: 指数数据 DataFrame (columns: trade_date, index_close)，可选
        """
        
        self.data = data
        self.index_data = index_data
        
        # 使用传入的日期或自动获取最新交易日
        if screening_date is None:
            calendar = Calendar()
            today = datetime.now().strftime("%Y%m%d")
            screening_date = calendar.get_latest_trade_date(today)
            if not screening_date:
                screening_date = today
        
        self.screening_date_str = screening_date
        self.latest_date = datetime.strptime(self.screening_date_str, "%Y%m%d")
        
        # 获取所有交易日期
        all_dates_pl = data.select(pl.col("trade_date").unique()).to_series().sort().to_list()
        all_dates = [datetime.strptime(str(d), "%Y%m%d") if isinstance(d, (int, str)) else d for d in all_dates_pl]
        
        if len(all_dates) == 0:
            raise ValueError("数据中不包含任何交易日")
        
        if self.latest_date not in all_dates:
            available_dates = [d for d in all_dates if d <= self.latest_date]
            if available_dates:
                self.latest_date = available_dates[-1]
                logger.warning(
                    f"数据中不存在配置的筛选日期 {self.screening_date_str}，"
                    f"使用最近的交易日：{self.latest_date.strftime('%Y-%m-%d')}"
                )
            else:
                raise ValueError(f"数据中没有筛选日期 {self.screening_date_str} 及之前的数据")
        
        # 获取所有股票代码
        self.all_stock_codes = data.select(pl.col("ts_code").unique()).to_series().to_list()
        
        # 初始化子模块
        self.batch_calculator = BatchCalculator(
            data=data,
            latest_date=self.latest_date,
            index_data=index_data
        )

    def run_screening(
        self, screening_logic: dict, top_n: int = 10, query: str = ""
    ) -> list[dict[str, Any]]:
        """执行股票筛选.
        
        Args:
            screening_logic: 筛选逻辑配置
            top_n: 返回Top N只股票
            query: 原始查询文本（用于智能检测预筛选条件）
            
        Returns:
            筛选结果列表
        """
        # 步骤 1: 批量计算（预筛选已在 stock_pool_filter 中完成）
        filtered_stock_codes = self.all_stock_codes
        
        if not filtered_stock_codes:
            logger.warning("⚠️ 无可用股票")
            return []
        
        # 步骤 2: 批量计算
        candidates = self.batch_calculator.batch_screen(
            stock_codes=filtered_stock_codes,
            screening_logic=screening_logic
        )
        
        # ✅ 核心改进：使用 confidence_weights 字典进行截面归一化打分
        # expression 仅用于过滤，不参与打分
        confidence_weights = screening_logic.get("confidence_weights", {})
        
        if candidates and confidence_weights:
            try:
                import re
                
                # ✅ 直接使用权重字典
                scoring_vars = set(confidence_weights.keys())
                var_weights = {k: float(v) for k, v in confidence_weights.items()}
                logger.info(f"📊 综合评分指标: {', '.join(sorted(scoring_vars))}")
                
                # 2. 收集所有候选股票中各指标的原始值
                metrics_data = {var: [] for var in scoring_vars}
                for c in candidates:
                    for var in scoring_vars:
                        # 如果指标不存在于 metrics 中，使用默认值 0
                        metrics_data[var].append(c["metrics"].get(var, 0))
                
                # 3. ✅ 对每个指标进行 Min-Max 截面归一化 (0-1)
                normalized_data = {}
                for var, values in metrics_data.items():
                    min_val = min(values)
                    max_val = max(values)
                    range_val = max_val - min_val if max_val != min_val else 1.0
                    normalized_data[var] = [(v - min_val) / range_val for v in values]
                
                # 4. ✅ 验证并归一化权重
                defined_vars = set(var_weights.keys())
                undefined_vars = scoring_vars - defined_vars
                
                if undefined_vars:
                    # 部分变量缺少权重定义 → 视为设计失败，回退等权
                    logger.warning(f"⚠️ 权重定义不完整")
                    logger.warning(f"   已定义: {', '.join(sorted(defined_vars))}")
                    logger.warning(f"   缺失: {', '.join(sorted(undefined_vars))}")
                    logger.warning(f"   → 回退到等权分配")
                    var_weights = {}
                else:
                    # 所有变量都有权重 → 归一化并使用
                    total_weight = sum(var_weights.values())
                    if total_weight > 0:
                        var_weights = {k: v / total_weight for k, v in var_weights.items()}
                        logger.info(f"✅ 使用自定义权重（已归一化）: {', '.join([f'{k}={v:.2f}' for k, v in sorted(var_weights.items())])}")
                    else:
                        logger.warning("⚠️ 权重总和为0，回退到等权")
                        var_weights = {}
                
                # 5. ✅ 计算加权综合得分（先归一化，再按权重求和）
                n = len(candidates)
                scores = [0.0] * n
                
                if var_weights:
                    # 使用自定义权重（每个指标已经过 Min-Max 归一化）
                    for var, weight in var_weights.items():
                        for i in range(n):
                            scores[i] += normalized_data[var][i] * weight
                else:
                    # 等权分配
                    weight = 1.0 / len(scoring_vars)
                    for var in scoring_vars:
                        for i in range(n):
                            scores[i] += normalized_data[var][i] * weight
                    logger.info(f"📐 使用等权分配: 每个指标权重={weight:.2f}")
                
                # ✅ 将综合得分保存到每个候选股票的 confidence 字段
                for i, candidate in enumerate(candidates):
                    candidate["confidence"] = scores[i]
                
                # 6. 按得分降序排列
                paired = list(zip(scores, candidates))
                paired.sort(key=lambda x: x[0], reverse=True)
                candidates = [c for _, c in paired]
                
                logger.info(f"✅ 综合评分计算完成，Top 1 得分: {max(scores):.4f}")

            except Exception as e:
                # ✅ 即使解析失败，也使用等权分配，不回退到按第一个指标排序
                logger.error(f"❌ 得分公式解析异常: {e}，强制使用等权分配")
                
                # 重新执行等权分配逻辑
                n = len(candidates)
                scores = [0.0] * n
                weight = 1.0 / len(scoring_vars)
                for var in scoring_vars:
                    for i in range(n):
                        scores[i] += normalized_data[var][i] * weight
                
                # 保存得分并排序
                for i, candidate in enumerate(candidates):
                    candidate["confidence"] = scores[i]
                
                candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)
                logger.info(f"⚠️ 已使用等权分配: 每个指标权重={weight:.2f}")
        
        # 记录物理匹配总数，方便日志输出
        total_matched = len(candidates)
        
        # 仅返回 Top N 用于展示（但保留完整列表在内存中供后续分析）
        results = candidates[:top_n]
        
        if total_matched > top_n:
            logger.info(f"[DATA] 物理匹配 {total_matched} 只股票，已按得分截取 Top {top_n} 只")
        else:
            logger.info(f"[DATA] 物理匹配 {total_matched} 只股票")
            
        return results


def create_screening_executor(
    data: pl.DataFrame,
    screening_date: Optional[str] = None,
    index_data: pl.DataFrame | None = None,
) -> ScreeningExecutor:
    """创建筛选执行器实例的便捷函数.
    
    Args:
        data: 股票数据 DataFrame
        screening_date: 筛选日期
        index_data: 指数数据 DataFrame（用于 Beta、Alpha 等指标）
    """
    return ScreeningExecutor(data, screening_date=screening_date, index_data=index_data)
