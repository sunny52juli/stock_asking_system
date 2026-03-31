#!/usr/bin/env python3
"""
回测功能测试脚本

测试 backtest 模块是否能正确：
1. 加载 screening_scripts 下的策略文件
2. 使用 datahub 加载市场数据
3. 执行筛选并计算收益率
4. 生成回测报告

使用方法:
    python backtest_runner.py
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
if project_root not in sys.path:
    sys.path.insert(0, str(project_root))


def strategy_backtest(
    scripts_dir: str = "screening_scripts/放量突破策略",
    screening_date: str | None = None,
    holding_periods: list[int] | None = None,
    observation_days: int | None = None,
):
    """测试回测功能 - 使用新的两阶段架构
    
    Args:
        scripts_dir: 回测脚本目录
        screening_date: 筛选日期（YYYYMMDD 格式）
        holding_periods: 持有期列表（天）
        observation_days: 观察期长度（交易日）
    """
    print("="*60)
    print("开始测试回测功能")
    print("-"*60)
    
    try:
        from backtest.backtest import DataProvider, ScreeningExecutor, ReturnCalculator
        from backtest.report_display import print_backtest_report
        from config.backtest_config import StockConfig
        
        print(f"回测目录：{scripts_dir}")
        
        # 使用传入的参数或配置的默认值
        actual_screening_date = screening_date or StockConfig.BACKTEST_SCREENING_DATE
        actual_holding_periods = holding_periods or StockConfig.BACKTEST_LOOKBACK_DAYS
        actual_observation_days = observation_days or StockConfig.OBSERVATION_PERIOD_DAYS
        
        if screening_date:
            print(f"筛选日期：{screening_date}")
        else:
            print(f"筛选日期：{actual_screening_date} (配置默认值)")
        
        # 阶段 1: 数据加载 + 筛选
        data_provider = DataProvider(
            screening_date=actual_screening_date,
            holding_periods=actual_holding_periods,
            observation_days=actual_observation_days
        )
        
        if not data_provider.load_data():
            print("\n❌ 数据加载失败")
            return
        
        # 扫描并执行脚本
        from pathlib import Path
        scripts_dir_path = Path(scripts_dir)
        if not scripts_dir_path.exists():
            print(f"\n❌ 脚本目录不存在：{scripts_dir}")
            return
        
        scripts = [s for s in scripts_dir_path.glob("*.py") if not s.name.startswith("_")]
        print(f"\n🔍 找到 {len(scripts)} 个脚本")
        
        screening_results = []
        for script_path in scripts:
            print(f"\n   📝 执行：{script_path.name}")
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("screening_script", str(script_path))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "screen_with_data"):
                        candidates = module.screen_with_data(
                            data_provider.data,
                            top_n=20,
                            screening_date=data_provider.screening_date.strftime("%Y%m%d") if data_provider.screening_date else None
                        )
                        
                        screening_results.append({
                            "script_name": script_path.stem,
                            "candidates": candidates,
                            "screening_date": data_provider.screening_date.strftime("%Y%m%d") if data_provider.screening_date else "",
                        })
                        print(f"      ✅ 筛选出 {len(candidates)} 只股票")
            except Exception as e:
                print(f"      ❌ 执行失败：{e}")
        
        if not screening_results:
            print("\n❌ 没有成功的筛选结果")
            return
        
        # 阶段 2: 收益计算
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
                    for period in data_provider.holding_periods:
                        ret_key = f"ret_{period}d"
                        ret_value = stock_data.get(ret_key)
                        
                        if ret_value is not None:
                            stock_entry[f"return_{period}d"] = ret_value * 100  # 转为百分比
                        else:
                            stock_entry[f"return_{period}d"] = None
                    
                    holding_stocks.append(stock_entry)
            
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
                "query": result["script_name"],
                "screening_date": result["screening_date"],
                "status": "成功",
                "candidates_count": len(result["candidates"]),
                "holding_period_results": holding_period_results,
                "holding_stocks": holding_stocks,  # 新增：持仓股票列表
                "portfolio_stats": portfolio_stats,  # 新增：持仓统计
            })
        
        # 生成报告
        report = {
            "status": "completed",
            "total_scripts": len(screening_results),
            "successful": len([r for r in backtest_results if r["status"] == "成功"]),
            "failed": len([r for r in backtest_results if r["status"] == "失败"]),
            "results": backtest_results,
            "timestamp": datetime.now().isoformat(),
        }
        
        print("\n✅ 回测完成！")
        print(f"总脚本数：{report.get('total_scripts', 0)}")
        print(f"成功：{report.get('successful', 0)}")
        print(f"失败：{report.get('failed', 0)}")
        
        # 展示详细的回测报告
        print_backtest_report(report)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    strategy_backtest()
