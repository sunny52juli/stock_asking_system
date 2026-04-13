"""收益计算器 - 计算持有期收益率和统计指标.

本模块从 backtest/returns.py 重构而来，
提供更清晰的收益计算API。
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ReturnsCalculator:
    """收益计算器 - 负责计算持有期收益率.
    
    核心功能:
    1. 计算单只股票的持有期收益
    2. 计算投资组合的平均收益、胜率等统计指标
    3. 生成详细的收益报告
    """
    
    def __init__(self, data: pd.DataFrame, holding_periods: list[int]):
        """初始化收益计算器.
        
        Args:
            data: 市场数据 DataFrame（MultiIndex: trade_date, ts_code）
            holding_periods: 持有期列表（天）
        """
        self.data = data
        self.holding_periods = holding_periods
    
    def calculate_returns(
        self,
        candidates: list[dict[str, Any]],
        screening_date: str,
    ) -> dict[str, Any]:
        """计算候选股票的持有期收益.
        
        Args:
            candidates: 候选股票列表
            screening_date: 筛选日期（YYYYMMDD格式）
            
        Returns:
            包含每只股票收益和投资组合统计的结果
        """
        if not candidates:
            return {"per_stock": [], "summary": {}}
        
        # 转换筛选日期
        screen_date = pd.to_datetime(screening_date, format="%Y%m%d")
        
        # 获取所有候选股票代码
        stock_codes = [c["ts_code"] for c in candidates]
        
        # 计算每只股票的收益
        per_stock_results = []
        for ts_code in stock_codes:
            stock_returns = self._calculate_single_stock_returns(ts_code, screen_date)
            
            if stock_returns:
                # 找到对应的候选信息
                candidate_info = next(
                    (c for c in candidates if c["ts_code"] == ts_code),
                    {}
                )
                
                result = {
                    "ts_code": ts_code,
                    "name": candidate_info.get("name", ts_code),
                    **stock_returns,
                }
                per_stock_results.append(result)
        
        # 计算投资组合统计
        summary = self._calculate_portfolio_stats(per_stock_results)
        
        return {
            "per_stock": per_stock_results,
            "summary": summary,
        }
    
    def _calculate_single_stock_returns(
        self,
        ts_code: str,
        screen_date: pd.Timestamp,
    ) -> dict[str, float] | None:
        """计算单只股票的持有期收益.
        
        Args:
            ts_code: 股票代码
            screen_date: 筛选日期
            
        Returns:
            各持有期的收益率字典，如果数据不足则返回 None
        """
        try:
            # 提取该股票的数据
            if isinstance(self.data.index, pd.MultiIndex):
                stock_data = self.data.xs(ts_code, level="ts_code")
            else:
                stock_data = self.data[self.data["ts_code"] == ts_code]
            
            if stock_data.empty:
                return None
            
            # 确保日期列存在
            if "trade_date" not in stock_data.columns:
                stock_data = stock_data.reset_index()
            
            # 转换为 datetime
            if not pd.api.types.is_datetime64_any_dtype(stock_data["trade_date"]):
                stock_data["trade_date"] = pd.to_datetime(stock_data["trade_date"])
            
            # 排序
            stock_data = stock_data.sort_values("trade_date")
            
            # 找到筛选日期及之后的数据
            future_data = stock_data[stock_data["trade_date"] > screen_date]
            
            if len(future_data) == 0:
                logger.debug(f"股票 {ts_code} 在 {screen_date.date()} 后无交易数据")
                return None
            
            # 获取买入价格（筛选日期的收盘价）
            buy_data = stock_data[stock_data["trade_date"] <= screen_date]
            if buy_data.empty:
                logger.debug(f"股票 {ts_code} 在 {screen_date.date()} 前无交易数据")
                return None
            
            buy_price = buy_data.iloc[-1]["close"]
            
            if pd.isna(buy_price) or buy_price <= 0:
                return None
            
            # 计算各持有期的收益
            returns = {}
            for period in self.holding_periods:
                if len(future_data) < period:
                    logger.debug(f"股票 {ts_code} 未来数据不足 {period} 天（实际 {len(future_data)} 天，范围：{future_data['trade_date'].min().date()} 至 {future_data['trade_date'].max().date()}）")
                    returns[f"ret_{period}d"] = None
                    continue
                
                # 获取卖出价格（第 period 个交易日）
                sell_row = future_data.iloc[period - 1]
                sell_price = sell_row["close"]
                sell_date = sell_row["trade_date"]
                
                if pd.isna(sell_price) or sell_price <= 0:
                    returns[f"ret_{period}d"] = None
                    continue
                
                # 计算收益率
                ret = (sell_price - buy_price) / buy_price
                returns[f"ret_{period}d"] = ret
            
            return returns
            
        except Exception as e:
            logger.debug(f"计算股票 {ts_code} 收益失败：{e}")
            return None
    
    def _calculate_portfolio_stats(
        self,
        per_stock_results: list[dict[str, Any]],
    ) -> dict[int, dict[str, float]]:
        """计算投资组合统计指标.
        
        Args:
            per_stock_results: 每只股票的收益结果
            
        Returns:
            各持有期的统计指标
        """
        summary = {}
        
        for period in self.holding_periods:
            ret_key = f"ret_{period}d"
            
            # 收集有效收益
            valid_returns = [
                r[ret_key]
                for r in per_stock_results
                if r.get(ret_key) is not None
            ]
            
            if not valid_returns:
                summary[period] = {
                    "mean": 0.0,
                    "std": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "win_rate": 0.0,
                    "valid_stocks": 0,
                    "total_stocks": len(per_stock_results),
                }
                continue
            
            # 计算统计指标
            returns_array = np.array(valid_returns)
            
            mean_ret = np.mean(returns_array)
            std_ret = np.std(returns_array) if len(returns_array) > 1 else 0.0
            win_rate = np.sum(returns_array > 0) / len(returns_array)
            
            summary[period] = {
                "mean": float(mean_ret),
                "std": float(std_ret),
                "min": float(np.min(returns_array)),
                "max": float(np.max(returns_array)),
                "win_rate": float(win_rate),
                "valid_stocks": len(valid_returns),
                "total_stocks": len(per_stock_results),
            }
        
        return summary
    
    def get_stock_info(self, ts_code: str) -> dict[str, str]:
        """获取股票基本信息.
        
        Args:
            ts_code: 股票代码
            
        Returns:
            股票信息字典
        """
        try:
            if isinstance(self.data.index, pd.MultiIndex):
                # 从 MultiIndex 中提取
                first_date = self.data.index.get_level_values("trade_date")[0]
                stock_row = self.data.loc[(first_date, ts_code)]
            else:
                stock_row = self.data[self.data["ts_code"] == ts_code].iloc[0]
            
            return {
                "ts_code": ts_code,
                "name": stock_row.get("name", ts_code),
                "industry": stock_row.get("industry", "N/A"),
            }
            
        except Exception:
            return {
                "ts_code": ts_code,
                "name": ts_code,
                "industry": "N/A",
            }
