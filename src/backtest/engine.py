"""回测引擎 - 整合数据加载、筛选执行和收益计算.

本模块从 backtest/backtest.py 重构而来，
提供更清晰的回测流程和API。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import pandas as pd

from datahub.loaders import load_raw_market_data
from src.screening.executor import ScreeningExecutor
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class BacktestEngine:
    """回测引擎 - 负责执行策略回测.
    
    核心功能:
    1. 加载历史数据
    2. 执行策略脚本
    3. 计算持有期收益
    4. 生成回测报告
    """
    
    def __init__(
        self,
        screening_date: str,
        holding_periods: list[int] | None = None,
        observation_days: int = 80,
    ):
        """初始化回测引擎.
        
        Args:
            screening_date: 筛选日期（YYYYMMDD格式）
            holding_periods: 持有期列表（天），默认 [4, 10, 20]
            observation_days: 观察期长度（交易日）
        """
        self.screening_date = screening_date
        self.holding_periods = holding_periods or [4, 10, 20]
        self.observation_days = observation_days
        
        self.data: Optional[pd.DataFrame] = None
        self.results: list[dict[str, Any]] = []
    
    def load_raw_data(self) -> bool:
        """加载回测所需的原始市场数据（不过滤）.
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"📊 加载回测原始数据（筛选日期：{self.screening_date}）")
            
            # 计算日期范围（需要包含持有期未来数据）
            from datetime import datetime, timedelta
            end_dt = datetime.strptime(self.screening_date, "%Y%m%d")
            # 结束日期 = 筛选日期 + 最大持有期 * 2（考虑非交易日，确保足够交易日）
            max_holding = max(self.holding_periods) if self.holding_periods else 20
            future_end = end_dt + timedelta(days=max_holding * 2)
            start_dt = end_dt - timedelta(days=self.observation_days + 60)
            
            start_date = start_dt.strftime("%Y%m%d")
            end_date = future_end.strftime("%Y%m%d")
            
            # 使用 datahub 的统一函数加载原始数据
            self.data = load_raw_market_data(
                start_date=start_date,
                end_date=end_date,
                exclude_st=False,
                min_list_days=0,
            )
            
            # 验证数据实际覆盖的日期范围
            if "trade_date" in self.data.columns:
                actual_start = self.data["trade_date"].min()
                actual_end = self.data["trade_date"].max()
                logger.info(f"   数据实际范围：{actual_start} 至 {actual_end}")
                
                # 检查是否有足够的未来数据
                screen_dt = pd.to_datetime(self.screening_date, format="%Y%m%d")
                max_future_needed = screen_dt + pd.Timedelta(days=max(self.holding_periods) * 2)
                if actual_end < max_future_needed:
                    logger.warning(f"   ⚠️ 数据不足：需要到 {max_future_needed.date()}，实际只到 {actual_end.date()}")
                    logger.warning(f"   建议：使用更早的筛选日期或更新数据")
            
            logger.info(f"✅ 数据加载完成：{len(self.data)} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据加载失败：{e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_script(self, script_path: Path) -> dict[str, Any]:
        """执行单个策略脚本.
        
        Args:
            script_path: 策略脚本路径
            
        Returns:
            筛选结果
        """
        logger.info(f"\n📝 执行策略：{script_path.name}")
        
        try:
            # 动态加载脚本
            spec = importlib.util.spec_from_file_location(
                "strategy_module", str(script_path)
            )
            if not spec or not spec.loader:
                raise ImportError(f"无法加载脚本：{script_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 检查是否有 screen_with_data 函数
            if not hasattr(module, "screen_with_data"):
                raise AttributeError("脚本缺少 screen_with_data 函数")
            
            # 执行筛选
            candidates = module.screen_with_data(
                self.data,
                top_n=20,
                screening_date=self.screening_date
            )
            
            logger.info(f"   ✅ 筛选出 {len(candidates)} 只股票")
            
            return {
                "script_name": script_path.stem,
                "candidates": candidates,
                "screening_date": self.screening_date,
                "status": "success",
            }
            
        except Exception as e:
            logger.error(f"   ❌ 执行失败：{e}")
            import traceback
            traceback.print_exc()
            
            return {
                "script_name": script_path.stem,
                "candidates": [],
                "screening_date": self.screening_date,
                "status": "failed",
                "error": str(e),
            }
    
    def run_directory(self, scripts_dir: str) -> list[dict[str, Any]]:
        """执行目录下所有策略脚本.
        
        Args:
            scripts_dir: 策略脚本目录
            
        Returns:
            所有策略的执行结果
        """
        scripts_dir_path = Path(scripts_dir)
        
        if not scripts_dir_path.exists():
            raise FileNotFoundError(f"脚本目录不存在：{scripts_dir}")
        
        # 扫描所有 .py 文件（包括子目录）
        scripts = [
            s for s in scripts_dir_path.rglob("*.py")
            if not s.name.startswith("_") and "/__" not in str(s)
        ]
        
        if not scripts:
            logger.warning(f"⚠️ 目录 {scripts_dir} 下没有找到策略脚本")
            return []
        
        logger.info(f"🔍 找到 {len(scripts)} 个策略脚本")
        
        # 逐个执行
        results = []
        for script_path in scripts:
            result = self.run_script(script_path)
            results.append(result)
        
        self.results = results
        return results
    
    def calculate_returns(self, results: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """计算持有期收益.
        
        Args:
            results: 筛选结果列表，如果为 None 则使用 self.results
            
        Returns:
            包含收益信息的完整回测结果
        """
        if results is None:
            results = self.results
        
        if not results:
            logger.warning("⚠️ 没有可计算收益的结果")
            return []
        
        from src.backtest.returns import ReturnsCalculator
        
        calculator = ReturnsCalculator(self.data, self.holding_periods)
        
        backtest_results = []
        for result in results:
            if result["status"] != "success" or not result["candidates"]:
                backtest_results.append(result)
                continue
            
            # 计算收益
            returns_result = calculator.calculate_returns(
                result["candidates"],
                result["screening_date"]
            )
            
            # 格式化收益结果
            holding_period_results = {}
            if "summary" in returns_result:
                for period, stats in returns_result["summary"].items():
                    if isinstance(period, int):
                        key = f"{period}日"
                        holding_period_results[key] = {
                            "年化收益率": f"{stats.get('mean', 0) * 252:.2%}" if stats.get('mean') else "N/A",
                            "胜率": f"{stats.get('win_rate', 0):.2%}" if stats.get('win_rate') is not None else "N/A",
                            "有效股票数": f"{stats.get('valid_stocks', 0)}/{stats.get('total_stocks', 0)}",
                        }
            
            # 构建持仓股票列表
            holding_stocks = self._build_holding_stocks(
                returns_result, result["candidates"]
            )
            
            # 构建持仓统计
            portfolio_stats = self._build_portfolio_stats(returns_result)
            
            # 合并结果
            enriched_result = {
                **result,
                "holding_period_results": holding_period_results,
                "holding_stocks": holding_stocks,
                "portfolio_stats": portfolio_stats,
            }
            
            backtest_results.append(enriched_result)
        
        return backtest_results
    
    def generate_report(self, results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """生成回测报告.
        
        Args:
            results: 回测结果列表
            
        Returns:
            完整的回测报告
        """
        if results is None:
            results = self.results
        
        total_scripts = len(results)
        successful = sum(1 for r in results if r.get("status") == "success")
        failed = total_scripts - successful
        
        report = {
            "status": "completed",
            "total_scripts": total_scripts,
            "successful": successful,
            "failed": failed,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "screening_date": self.screening_date,
                "holding_periods": self.holding_periods,
                "observation_days": self.observation_days,
            }
        }
        
        return report
    
    def _build_holding_stocks(
        self,
        returns_result: dict,
        candidates: list[dict],
    ) -> list[dict]:
        """构建持仓股票列表."""
        holding_stocks = []
        
        if "per_stock" not in returns_result:
            return holding_stocks
        
        for stock_data in returns_result["per_stock"]:
            ts_code = stock_data.get("ts_code", "")
            if not ts_code:
                continue
            
            stock_name = stock_data.get("name", ts_code)
            
            # 从 candidates 中获取行业信息
            industry = "N/A"
            for candidate in candidates:
                if candidate.get("ts_code") == ts_code:
                    industry = candidate.get("industry", "N/A")
                    break
            
            # 构建持仓条目
            stock_entry = {
                "ts_code": ts_code,
                "stock_name": stock_name,
                "industry": industry,
            }
            
            # 添加各持有期的收益率
            for period in self.holding_periods:
                ret_key = f"ret_{period}d"
                ret_value = stock_data.get(ret_key)
                
                if ret_value is not None:
                    stock_entry[f"return_{period}d"] = ret_value * 100  # 转为百分比
                else:
                    stock_entry[f"return_{period}d"] = None
            
            holding_stocks.append(stock_entry)
        
        return holding_stocks
    
    def _build_portfolio_stats(self, returns_result: dict) -> dict:
        """构建投资组合统计."""
        portfolio_stats = {}
        
        if "summary" not in returns_result:
            return portfolio_stats
        
        for period, stats in returns_result["summary"].items():
            if isinstance(period, int):
                period_key = f"day_{period}"
                portfolio_stats[period_key] = {
                    "avg_return": float(stats.get("mean", 0) * 100) if stats.get("mean") else 0.0,
                    "max_return": float(stats.get("max", 0) * 100) if stats.get("max") is not None else 0.0,
                    "min_return": float(stats.get("min", 0) * 100) if stats.get("min") is not None else 0.0,
                    "win_rate": float(stats.get("win_rate", 0) * 100) if stats.get("win_rate") is not None else 0.0,
                    "count": stats.get("valid_stocks", 0),
                }
        
        return portfolio_stats


def run_backtest(
    scripts_dir: str,
    screening_date: str,
    holding_periods: list[int] | None = None,
    observation_days: int = 80,
) -> dict[str, Any]:
    """便捷函数：执行完整的回测流程.
    
    Args:
        scripts_dir: 策略脚本目录
        screening_date: 筛选日期
        holding_periods: 持有期列表
        observation_days: 观察期长度
        
    Returns:
        完整的回测报告
    """
    # 创建回测引擎
    engine = BacktestEngine(
        screening_date=screening_date,
        holding_periods=holding_periods,
        observation_days=observation_days,
    )
    
    # 加载原始数据
    if not engine.load_raw_data():
        raise RuntimeError("数据加载失败")
    
    # 执行策略
    results = engine.run_directory(scripts_dir)
    
    # 计算收益
    results_with_returns = engine.calculate_returns(results)
    
    # 生成报告
    report = engine.generate_report(results_with_returns)
    
    return report
