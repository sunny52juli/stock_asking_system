#!/usr/bin/env python3
"""
筛选逻辑脚本: 均线多头排列
(由 core.agent 生成, 仅依赖 core)

原始查询: 找出均线多头排列的股票：
1. 5日>10日>20日均线
2. 股价站上所有均线


筛选说明:
    无说明

工具步骤:
    1. ma5: 通过工具 'rolling_mean' 计算，参数={'column': 'close', 'window': 5}
    2. ma10: 通过工具 'rolling_mean' 计算，参数={'column': 'close', 'window': 10}
    3. ma20: 通过工具 'rolling_mean' 计算，参数={'column': 'close', 'window': 20}

筛选表达式: (ma5 > ma10) & (ma10 > ma20) & (close > ma5) & (close > ma10) & (close > ma20)
置信度公式: rank_normalize((ma5 - ma20) / ma20)

生成时间: 2026-04-14 23:27:43
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根加入路径 (脚本可能在 output/ 下)
script_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(script_dir)  # app/
project_root = os.path.dirname(app_dir)  # 项目根目录
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# ==================== 筛选逻辑定义 ====================
SCREENING_LOGIC = {
    "name": "均线多头排列",
    "tools": [
        {
            "tool": "rolling_mean",
            "params": {
                "column": "close",
                "window": 5
            },
            "var": "ma5"
        },
        {
            "tool": "rolling_mean",
            "params": {
                "column": "close",
                "window": 10
            },
            "var": "ma10"
        },
        {
            "tool": "rolling_mean",
            "params": {
                "column": "close",
                "window": 20
            },
            "var": "ma20"
        }
    ],
    "expression": "(ma5 > ma10) & (ma10 > ma20) & (close > ma5) & (close > ma10) & (close > ma20)",
    "confidence_formula": "rank_normalize((ma5 - ma20) / ma20)"
}
# ==================== 筛选逻辑定义结束 ====================

ORIGINAL_QUERY = """找出均线多头排列的股票：
1. 5日>10日>20日均线
2. 股价站上所有均线
"""


def get_screening_logic() -> dict:
    """获取筛选逻辑定义（供加载器使用）"""
    return SCREENING_LOGIC


def screen_with_data(data: pd.DataFrame, top_n: int = 20, screening_date: str = None) -> List[Dict[str, Any]]:
    """
    使用提供的数据执行筛选（仅依赖 core.stock_screener）
    """
    from utils.screening.stock_screener import StockScreener

    screener = StockScreener(data, screening_date=screening_date)
    return screener.execute_screening(
        screening_logic=SCREENING_LOGIC,
        top_n=top_n,
        query=ORIGINAL_QUERY
    )


def main():
    """主函数 - 独立运行时使用 (数据来自 core.data_loading)"""
    import argparse
    import os

    logic_name = SCREENING_LOGIC.get("name", "未命名筛选")
    
    parser = argparse.ArgumentParser(description=f'均线多头排列 - 筛选脚本')
    parser.add_argument('--top_n', type=int, default=20, help='返回股票数量（默认 20）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（可选）')
    args = parser.parse_args()

    # 检查 Tushare token 配置
    if not os.getenv('TUSHARE_TOKEN'):
        print("⚠️ 警告: 未检测到 TUSHARE_TOKEN 环境变量")
        print("   请在 .env 文件中设置 TUSHARE_TOKEN=your_token")
        print("   或者设置环境变量: export TUSHARE_TOKEN=your_token")
        print("\n💡 提示: 如果已有缓存数据，脚本仍可能正常运行")
        print("-" * 60)
    
    from datahub.loaders import StockDataLoader

    print("📊 加载市场数据...")
    try:
        # 独立运行时使用最新交易日期，不依赖 backtest_config
        from infrastructure.config.settings import get_settings
        settings = get_settings()
        loader = StockDataLoader()
        data = loader.load_market_data(observation_days=settings.observation_days)
        print(f"✅ 数据加载完成：{len(data)} 条记录")
    except ValueError as e:
        if "Tushare token" in str(e):
            print(f"❌ 数据加载失败: {e}")
            print("\n解决方法:")
            print("1. 在项目根目录创建 .env 文件")
            print("2. 添加以下内容: TUSHARE_TOKEN=your_token_here")
            print("3. 重新运行脚本")
            sys.exit(1)
        else:
            raise

    print("\n🔍 执行筛选: " + logic_name)
    results = screen_with_data(data, top_n=args.top_n)

    print("\n✅ 找到 " + str(len(results)) + " 只符合条件的股票")
    print("{:<6}{:<12}{:<20}{:<10}{}".format('排名', '股票代码', '股票名称', '置信度', '筛选理由'))
    print("-" * 100)
    for i, stock in enumerate(results, 1):
        print("{:<6}{:<12}{:<20}{:.2%}    {}".format(i, stock['ts_code'], stock['name'], stock['confidence'], stock['reason']))

    if args.output and results:
        result_df = pd.DataFrame(results)
        result_df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print("\n💾 结果已保存: " + str(args.output))


if __name__ == "__main__":
    main()
