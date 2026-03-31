"""
回测执行器 - 加载并回测筛选脚本

功能:
1. 扫描 screening_scripts 目录中的所有 Python 脚本
2. 动态加载脚本并执行筛选
3. 计算不同持有期的收益率
4. 生成回测报告

与 stock_asking_system 的回测逻辑同源，但仅依赖 core 模块
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from datahub import load_market_data_for_backtest
from backtest.returns import calculate_holding_returns
from utils.logger import get_logger
from config.backtest_config import StockConfig
from config.data_config import DataConfig

logger = get_logger(__name__)


@dataclass
class ScreeningResult:
    """筛选结果数据类"""
    
    script_name: str
    script_path: str
    query: str
    screening_date: str
    status: str = "成功"  # 成功/失败
    candidates: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None
    execution_time: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "script_name": self.script_name,
            "script_path": self.script_path,
            "query": self.query,
            "screening_date": self.screening_date,
            "status": self.status,
            "candidates": self.candidates,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
        }


@dataclass
class BacktestResult:
    """回测结果数据类"""
    
    script_name: str
    script_path: str
    query: str
    screening_date: str
    status: str = "成功"  # 成功/失败
    candidates_count: int = 0
    holding_period_results: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    execution_time: float = 0.0
    holding_stocks: list[dict[str, Any]] = field(default_factory=list)  # 持仓股票详细信息
    portfolio_stats: dict[str, Any] = field(default_factory=dict)  # 组合统计信息
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "script_name": self.script_name,
            "script_path": self.script_path,
            "query": self.query,
            "screening_date": self.screening_date,
            "status": self.status,
            "candidates_count": self.candidates_count,
            "holding_period_results": self.holding_period_results,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
            "holding_stocks": self.holding_stocks,
            "portfolio_stats": self.portfolio_stats,
        }


class ScriptLoader:
    """筛选脚本加载器"""
    
    @staticmethod
    def load_script_from_path(script_path: str) -> tuple[Any, dict[str, Any]] | None:
        """从文件路径加载脚本
        
        Args:
            script_path: 脚本文件路径
            
        Returns:
            (module, screening_logic) 元组，如果加载失败则返回 None
        """
        try:
            spec = importlib.util.spec_from_file_location(
                "screening_script", 
                script_path
            )
            if spec is None or spec.loader is None:
                logger.error(f"无法加载脚本：{script_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["screening_script"] = module
            spec.loader.exec_module(module)
            
            # 获取筛选逻辑
            if hasattr(module, "get_screening_logic"):
                screening_logic = module.get_screening_logic()
            elif hasattr(module, "SCREENING_LOGIC"):
                screening_logic = module.SCREENING_LOGIC
            else:
                logger.error(f"脚本 {script_path} 缺少筛选逻辑定义")
                return None
            
            return module, screening_logic
            
        except Exception as e:
            logger.error(f"加载脚本 {script_path} 失败：{e}")
            logger.debug(traceback.format_exc())
            return None


class DataProvider:
    """数据提供者 - 负责加载和管理市场数据"""
    
    def __init__(self, screening_date: str, holding_periods: list[int], observation_days: int):
        """初始化数据提供者
        
        Args:
            screening_date: 筛选日期（YYYYMMDD 格式）
            holding_periods: 持有期列表（天）
            observation_days: 观察期长度（交易日）
        """
        self.screening_date_str = screening_date
        self.holding_periods = holding_periods
        self.observation_days = observation_days
        self.data: pd.DataFrame | None = None
        self.screening_date: pd.Timestamp | None = None
    
    def load_data(self) -> bool:
        """加载市场数据
        
        Returns:
            是否加载成功
        """
        try:
            logger.info("="*60)
            logger.info("加载市场数据...")
            logger.info(f"配置的筛选日期：{self.screening_date_str}")
            
            # 计算数据起止日期
            data_start_date = StockConfig.get_data_start_date(
                self.screening_date_str, 
                observation_days=self.observation_days
            )
            data_end_date = StockConfig.get_data_end_date(
                self.screening_date_str, 
                holding_periods=self.holding_periods
            )
            
            logger.info(f"观察期长度：{self.observation_days} 个交易日")
            logger.info(f"持有期：{self.holding_periods} 天")
            logger.info(f"数据起止日期：{data_start_date} ~ {data_end_date}")
            logger.info(f"缓存目录：{DataConfig.DATA_CACHE_ROOT}")
            
            # 使用 datahub 的 backtest 专用加载器
            logger.info("正在检查本地缓存...")
            self.data = load_market_data_for_backtest(force_reload=False)
            
            # 设置筛选日期（字符串转为 Timestamp）
            try:
                self.screening_date = pd.to_datetime(self.screening_date_str, format="%Y%m%d")
                if pd.isna(self.screening_date):
                    logger.error(f"无效的筛选日期格式：{self.screening_date_str}")
                    return False
            except Exception as e:
                logger.error(f"筛选日期转换失败：{e}")
                return False
            
            # 验证数据范围并自动调整非交易日
            all_dates = sorted(self.data.index.get_level_values("trade_date").unique())
            if len(all_dates) == 0:
                logger.error("数据中不包含任何交易日")
                return False
            
            # 检查筛选日期是否在数据范围内，如不在则使用最近的交易日
            try:
                screen_idx = list(all_dates).index(self.screening_date)
            except ValueError:
                # 筛选日期不在数据中，找到最近的交易日
                available_dates = [d for d in all_dates if d <= self.screening_date]
                if available_dates:
                    self.screening_date = available_dates[-1]
                    logger.info(f"配置的筛选日期 {self.screening_date_str} 非交易日，自动切换到最近的交易日：{self.screening_date.strftime('%Y-%m-%d')}")
                    screen_idx = list(all_dates).index(self.screening_date)
                else:
                    logger.error(f"数据中没有筛选日期 {self.screening_date_str} 及之前的数据")
                    return False
            
            # 检查是否有足够的未来数据
            max_holding_period = max(self.holding_periods)
            available_future_days = len(all_dates) - screen_idx - 1
            
            if available_future_days < max_holding_period:
                logger.warning(
                    f"⚠️  警告：数据不足！筛选日期后有 {available_future_days} 天数据，"
                    f"但需要 {max_holding_period} 天来计算收益率"
                )
                logger.warning(f"建议：将筛选日期设置为更早的日期")
            else:
                logger.info(f"✅ 数据充足：筛选日期后有 {available_future_days} 个交易日数据")
            
            logger.info(f"数据加载完成：{len(self.data)} 条记录")
            logger.info("="*60)
            return True
            
        except Exception as e:
            logger.error(f"数据加载失败：{e}")
            logger.error(f"请检查：1) DATA_SOURCE_TOKEN 是否正确配置；2) 网络连接是否正常")
            self.data = None
            self.screening_date = None
            return False
    

class ScreeningExecutor:
    """筛选执行器 - 负责执行策略脚本筛选股票"""
    
    def __init__(self, data: pd.DataFrame, screening_date: pd.Timestamp, holding_periods: list[int]):
        """初始化筛选执行器
        
        Args:
            data: 市场数据 DataFrame
            screening_date: 筛选日期（Timestamp）
            holding_periods: 持有期列表（天）
        """
        self.data = data
        self.screening_date = screening_date
        self.holding_periods = holding_periods
    
    def execute_script(self, module: Any, script_name: str) -> tuple[list[dict[str, Any]], str] | None:
        """执行筛选脚本
        
        Args:
            module: 加载的脚本模块
            script_name: 脚本名称
            
        Returns:
            (candidates, screening_date) 或 None（执行失败）
        """
        try:
            if not hasattr(module, "screen_with_data"):
                logger.error(f"脚本 {script_name} 缺少 screen_with_data 函数")
                return None
            
            if self.data is None:
                logger.error("数据未加载")
                return None
            
            # 执行筛选
            candidates = module.screen_with_data(
                self.data,
                top_n=20,
                holding_periods=self.holding_periods,
                screening_date=self.screening_date.strftime("%Y%m%d") if self.screening_date else None
            )
            
            if not isinstance(candidates, list):
                logger.error(f"screen_with_data 返回值类型错误：{type(candidates)}")
                return None
            
            if self.screening_date is None:
                logger.error("筛选日期未设置")
                return None
            
            return candidates, self.screening_date.strftime("%Y%m%d")
            
        except Exception as e:
            logger.error(f"执行脚本 {script_name} 失败：{e}")
            logger.debug(traceback.format_exc())
            return None


class ReturnCalculator:
    """收益计算器 - 负责计算持仓收益率"""
    
    def __init__(self, data: pd.DataFrame, holding_periods: list[int]):
        """初始化收益计算器
        
        Args:
            data: 市场数据 DataFrame
            holding_periods: 持有期列表（天）
        """
        self.data = data
        self.holding_periods = holding_periods
    
    def calculate_returns(
        self, 
        candidates: list[dict[str, Any]], 
        screening_date: str
    ) -> dict[str, Any]:
        """计算持有期收益率
        
        Args:
            candidates: 候选股票列表
            screening_date: 筛选日期（YYYYMMDD）
            
        Returns:
            收益率计算结果
        """
        if self.data is None:
            logger.error("数据未加载，无法计算收益率")
            return {"error": "数据未加载"}
        
        if not candidates or len(candidates) == 0:
            logger.warning("候选股票为空，无法计算收益率")
            return {"summary": {}}
        
        try:
            # 检查数据中的日期范围
            all_dates = sorted(self.data.index.get_level_values("trade_date").unique())
            screening_date_ts = pd.to_datetime(screening_date, format="%Y%m%d")
            
            try:
                screen_idx = list(all_dates).index(screening_date_ts)
                max_period = max(self.holding_periods)
                required_end_idx = screen_idx + max_period
                
                if required_end_idx >= len(all_dates):
                    available_days = len(all_dates) - screen_idx - 1
                    logger.error(
                        f"数据不足！筛选日期 {screening_date} 后只有 {available_days} 天数据，"
                        f"但需要 {max_period} 天来计算收益率"
                    )
                    logger.error(f"数据范围：{all_dates[0].strftime('%Y%m%d')} ~ {all_dates[-1].strftime('%Y%m%d')}")
                    logger.error(f"需要到：{(screening_date_ts + pd.Timedelta(days=max_period)).strftime('%Y%m%d')}")
                    return {"summary": {}}
            except ValueError:
                logger.error(f"筛选日期 {screening_date} 不在数据日期范围内")
                return {"summary": {}}
            
            result = calculate_holding_returns(
                self.data,
                candidates,
                self.holding_periods,
                screening_date=screening_date_ts
            )
            return result
        except Exception as e:
            logger.error(f"计算收益率失败：{e}")
            logger.debug(traceback.format_exc())
            return {"error": str(e)}
    
    def _get_stock_info(self, ts_code: str) -> dict[str, str]:
        """获取股票基本信息
        
        Args:
            ts_code: 股票代码
            
        Returns:
            包含股票名称和行业的字典
        """
        try:
            # 从已加载的数据中获取股票信息
            if self.data is not None:
                # 尝试从 MultiIndex 中获取
                stock_data = self.data.xs(ts_code, level="ts_code", drop=False)
                if len(stock_data) > 0:
                    # 获取第一行数据
                    first_row = stock_data.iloc[0]
                    return {
                        'name': first_row.get('name', 'N/A'),
                        'industry': first_row.get('industry', 'N/A'),
                    }
        except Exception:
            pass
        
        # 默认返回
        return {'name': 'N/A', 'industry': 'N/A'}


# 向后兼容的便捷函数
def backtest_screening_scripts(
    scripts_dir: str | None = None,
    screening_date: str | None = None,
    holding_periods: list[int] | None = None,
    observation_days: int | None = None,
) -> dict[str, Any]:
    """便捷函数 - 回测筛选脚本（向后兼容）
    
    Args:
        scripts_dir: 脚本目录，默认使用配置中的目录
        screening_date: 筛选日期（YYYYMMDD 格式），默认使用 backtest_config 的配置
        holding_periods: 持有期列表（天），默认使用 backtest_config 的配置
        observation_days: 观察期长度（交易日），默认使用 backtest_config 的配置
        
    Returns:
        回测结果报告
    """
    from config.screener_deepagent_config import ScreenerDeepAgentConfig
    
    if scripts_dir is None:
        scripts_dir = str(ScreenerDeepAgentConfig.get_scripts_dir())
    
    # 使用新的两阶段架构
    try:
        # 阶段 1: 筛选
        data_provider = DataProvider(
            screening_date=screening_date or StockConfig.BACKTEST_SCREENING_DATE,
            holding_periods=holding_periods or StockConfig.BACKTEST_LOOKBACK_DAYS,
            observation_days=observation_days or StockConfig.OBSERVATION_PERIOD_DAYS
        )
        
        if not data_provider.load_data():
            return {
                "status": "failed",
                "error": "数据加载失败",
                "results": [],
            }
        
        # 扫描并执行脚本
        scripts_dir_path = Path(scripts_dir)
        if not scripts_dir_path.exists():
            return {
                "status": "no_scripts",
                "error": f"脚本目录不存在：{scripts_dir}",
                "results": [],
            }
        
        scripts = [s for s in scripts_dir_path.glob("*.py") if not s.name.startswith("_")]
        
        screening_results = []
        for script_path in scripts:
            try:
                loaded = ScriptLoader.load_script_from_path(str(script_path))
                if loaded is None:
                    continue
                
                module, _ = loaded
                if hasattr(module, "screen_with_data"):
                    candidates = module.screen_with_data(
                        data_provider.data,
                        top_n=20,
                        holding_periods=data_provider.holding_periods,
                        screening_date=data_provider.screening_date.strftime("%Y%m%d") if data_provider.screening_date else None
                    )
                    
                    screening_results.append({
                        "script_name": script_path.stem,
                        "candidates": candidates,
                        "screening_date": data_provider.screening_date.strftime("%Y%m%d") if data_provider.screening_date else "",
                    })
            except Exception:
                continue
        
        # 阶段 2: 计算收益
        calculator = ReturnCalculator(data_provider.data, data_provider.holding_periods)
        
        backtest_results = []
        for result in screening_results:
            if len(result["candidates"]) == 0:
                continue
            
            returns_result = calculator.calculate_returns(
                result["candidates"],
                result["screening_date"]
            )
            
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
            
            # 转换 per_stock 数据为 holding_stocks 格式供报表展示
            holding_stocks = []
            if "per_stock" in returns_result and len(returns_result["per_stock"]) > 0:
                for stock_data in returns_result["per_stock"]:
                    ts_code = stock_data.get("ts_code", "")
                    if not ts_code:
                        continue
                    
                    stock_name = stock_data.get("name", ts_code)
                    
                    # 优先从原始 candidates 中获取行业信息
                    industry = "N/A"
                    for candidate in result["candidates"]:
                        if candidate.get("ts_code") == ts_code:
                            industry = candidate.get("industry", "N/A")
                            break
                    
                    # 如果 candidates 中没有，尝试从数据中获取
                    if industry == "N/A":
                        stock_info = calculator._get_stock_info(ts_code)
                        industry = stock_info.get("industry", "N/A")
                    
                    # 构建持仓股票字典
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
            elif "per_stock" in returns_result:
                logger.warning(f"   per_stock 存在但为空列表")
            else:
                logger.warning(f"   returns_result 缺少 per_stock 键，实际 keys: {list(returns_result.keys())}")
            
            # 构建持仓统计信息
            portfolio_stats = {}
            if "summary" in returns_result:
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
            
            backtest_results.append({
                "script_name": result["script_name"],
                "query": result["query"] if "query" in result else result["script_name"],
                "screening_date": result["screening_date"],
                "status": "成功",
                "candidates_count": len(result["candidates"]),
                "holding_period_results": holding_period_results,
                "holding_stocks": holding_stocks,  # 新增：持仓股票列表
                "portfolio_stats": portfolio_stats,  # 新增：持仓统计
            })
        
        return {
            "status": "completed",
            "total_scripts": len(screening_results),
            "successful": len([r for r in backtest_results if r["status"] == "成功"]),
            "failed": len([r for r in backtest_results if r["status"] == "失败"]),
            "results": backtest_results,
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"回测失败：{e}")
        return {
            "status": "failed",
            "error": str(e),
            "results": [],
        }
