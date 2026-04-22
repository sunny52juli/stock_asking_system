# ============================================================================
# DEPRECATED - 此文件已被弃用
# ============================================================================
# 弃用原因: 此文件未被项目中任何其他模块引用或使用
# 替代方案: 请使用 src/backtest/ 模块中的回测功能
# 弃用日期: 2026-04-19
# ============================================================================

"""回测应用入口 - 执行策略回测并生成报告."""

import sys
from pathlib import Path
from dotenv import load_dotenv
import polars as pl
# 加载环境变量（必须在其他导入之前）
load_dotenv()

# 获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.agent.services.stock_pool_service import StockPoolService
import argparse
import traceback

from src.backtest.engine import BacktestEngine
from src.backtest.report import print_backtest_report
from infrastructure.config.settings import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def main(
    scripts_dir: str | None = None,
    screening_date: str | None = None,
    holding_periods: list[int] | None = None,
    observation_days: int | None = None,
):
    """主函数 - 执行回测.
    
    Args:
        scripts_dir: 回测脚本目录
        screening_date: 筛选日期（YYYYMMDD 格式）
        holding_periods: 持有期列表（天）
        observation_days: 观察期长度（交易日）
    """
    print("=" * 60)
    print("开始执行回测")
    print("-" * 60)
    
    try:
        # 回测需要加载所有配置文件
        settings = get_settings(reload=True, config_files=["backtest.yaml", "stock_pool.yaml"])
        
        # 使用传入的参数或配置的默认值
        actual_scripts_dir = scripts_dir or "screening_scripts"
        actual_screening_date = screening_date or settings.backtest.screening_date
        actual_holding_periods = holding_periods or settings.backtest.holding_periods
        actual_observation_days = observation_days or settings.observation_days
        
        logger.info(f"回测目录：{actual_scripts_dir}")
        logger.info(f"筛选日期：{actual_screening_date}")
        logger.info(f"持有期：{actual_holding_periods}")
        logger.info(f"观察期：{actual_observation_days} 个交易日")
        
        # 创建回测引擎（不传入 settings）
        engine = BacktestEngine(
            screening_date=actual_screening_date,
            holding_periods=actual_holding_periods,
            observation_days=actual_observation_days,
        )
        
        # 加载原始数据（不过滤）
        if not engine.load_raw_data():
            logger.error("❌ 数据加载失败")
            return
        
        # 执行股票池过滤（独立服务模块，与 screener 一致）
        logger.info("\n" + "=" * 60)
        logger.info("执行股票池过滤")
        logger.info("=" * 60)
        stock_pool_service = StockPoolService(settings)
        
        # 应用股票池过滤（注意：apply_filter 返回三个值，包括指数数据）
        filtered_data, filtered_codes, index_data = stock_pool_service.apply_filter(
            engine.data
        )
        logger.info(f"✅ 股票池过滤完成：{len(filtered_codes)} 只股票")
        
        # 检查并记录指数数据
        if index_data is not None and not index_data.is_empty():
            logger.info(f"✅ 从 StockPoolService 获取指数数据: {len(index_data)} 条记录")
            logger.debug(f"   指数数据列: {list(index_data.columns)}")
        else:
            logger.warning("⚠️ StockPoolService 未返回有效的指数数据")
            index_data = None
        
        # 更新引擎的过滤后数据和指数数据
        engine.data = filtered_data
        engine.index_data = index_data
        
        if index_data is not None:
            logger.info(f"✅ engine.index_data 已设置: {len(index_data)} 条记录, 列: {list(index_data.columns)}")
        else:
            logger.warning("⚠️ engine.index_data 为 None")
        
        # 执行策略
        results = engine.run_directory(actual_scripts_dir)
        
        if not results:
            logger.error("❌ 没有成功的筛选结果")
            return
        
        # 计算收益
        results_with_returns = engine.calculate_returns(results)
        
        # 生成报告
        report = engine.generate_report(results_with_returns)
        
        # 打印报告
        print_backtest_report(report)
        
        logger.info("\n✅ 回测完成！")
        
    except Exception as e:
        logger.exception(f"❌ 回测失败：{e}")
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("回测结束")
    print("=" * 60)


def cli():
    """命令行入口"""
    
    parser = argparse.ArgumentParser(description='执行策略回测')
    parser.add_argument('--dir', type=str, default=None, 
                       help='策略脚本目录（默认：配置中的第一个策略）')
    parser.add_argument('--date', type=str, default=None,
                       help='筛选日期 YYYYMMDD（默认：配置中的日期）')
    parser.add_argument('--periods', type=str, default=None,
                       help='持有期列表，逗号分隔（默认：4,10,20）')
    parser.add_argument('--observation', type=int, default=None,
                       help='观察期长度（默认：配置的 observation_days）')
    
    args = parser.parse_args()
    
    # 解析持有期
    holding_periods = None
    if args.periods:
        holding_periods = [int(p.strip()) for p in args.periods.split(',')]
    
    try:
        main(
            scripts_dir=args.dir,
            screening_date=args.date,
            holding_periods=holding_periods,
            observation_days=args.observation,
        )
    except KeyboardInterrupt:
        logger.info("\n用户中断程序")
        sys.exit(0)
    except Exception as e:
        logger.exception("程序异常：%s", e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
