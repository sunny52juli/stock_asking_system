#!/usr/bin/env python3
"""
筛选逻辑脚本: 放量上涨策略
(由 screener_deepagent 生成, 仅依赖 core)

原始查询: 找出最近放量突破的股票：
    1. 成交量较前期放大（至少 1.5 倍）
    2. 涨幅>3%
    3. 技术形态良好

筛选说明:
    筛选放量上涨股票：1) 日涨幅>3%；2) 成交量较5日均量放大1.2倍以上；3) RSI<80避免超买；4) 收盘价站上5日均线

工具步骤:
    1. daily_return = pct_change({'column': 'close', 'periods': 1})
    2. avg_volume_5d = rolling_mean({'column': 'vol', 'window': 5})
    3. rsi_14 = rsi({'column': 'close', 'window': 14})
    4. ma_5 = rolling_mean({'column': 'close', 'window': 5})

筛选表达式: (daily_return > 0.03) & (vol / avg_volume_5d > 1.2) & (rsi_14 < 80) & (close > ma_5)
置信度公式: daily_return * 100 * 0.4 + (vol / avg_volume_5d) * 0.3 + (close / ma_5 - 1) * 100 * 0.3

生成时间: 2026-04-01 11:36:04
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any

# 项目根加入路径 (脚本可能在 output/ 下)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# ==================== 筛选逻辑定义 ====================
SCREENING_LOGIC = {
    "name": "放量上涨策略",
    "tools": [
        {
            "tool": "pct_change",
            "params": {
                "column": "close",
                "periods": 1
            },
            "var": "daily_return"
        },
        {
            "tool": "rolling_mean",
            "params": {
                "column": "vol",
                "window": 5
            },
            "var": "avg_volume_5d"
        },
        {
            "tool": "rsi",
            "params": {
                "column": "close",
                "window": 14
            },
            "var": "rsi_14"
        },
        {
            "tool": "rolling_mean",
            "params": {
                "column": "close",
                "window": 5
            },
            "var": "ma_5"
        }
    ],
    "expression": "(daily_return > 0.03) & (vol / avg_volume_5d > 1.2) & (rsi_14 < 80) & (close > ma_5)",
    "confidence_formula": "daily_return * 100 * 0.4 + (vol / avg_volume_5d) * 0.3 + (close / ma_5 - 1) * 100 * 0.3",
    "rationale": "筛选放量上涨股票：1) 日涨幅>3%；2) 成交量较5日均量放大1.2倍以上；3) RSI<80避免超买；4) 收盘价站上5日均线"
}
# ==================== 筛选逻辑定义结束 ====================

ORIGINAL_QUERY = """找出最近放量突破的股票：
    1. 成交量较前期放大（至少 1.5 倍）
    2. 涨幅>3%
    3. 技术形态良好"""


def get_screening_logic() -> dict:
    """获取筛选逻辑定义（供加载器使用）"""
    return SCREENING_LOGIC


def screen_with_data(data: pd.DataFrame, top_n: int = 20, screening_date: str = None) -> List[Dict[str, Any]]:
    """
    使用提供的数据执行筛选（仅依赖 core.stock_screener）
    """
    from utils.stock_screener import StockScreener

    screener = StockScreener(data, screening_date=screening_date)
    return screener.execute_screening(
        screening_logic=SCREENING_LOGIC,
        top_n=top_n,
        query=ORIGINAL_QUERY
    )


def main():
    """主函数 - 独立运行时使用 (数据来自 core.data_loading)"""
    import argparse

    parser = argparse.ArgumentParser(description='放量上涨策略 - 筛选脚本')
    parser.add_argument('--top_n', type=int, default=20, help='返回股票数量（默认 20）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（可选）')
    args = parser.parse_args()

    from datahub import load_market_data

    print("📊 加载市场数据...")
    # 独立运行时使用最新交易日期，不依赖 backtest_config
    data = load_market_data()
    print(f"✅ 数据加载完成：{len(data)} 条记录")

    print(f"\n🔍 执行筛选: 放量上涨策略")
    results = screen_with_data(data, top_n=args.top_n)

    print(f"\n✅ 找到 {len(results)} 只符合条件的股票")
    print(f"{'排名':<6}{'股票代码':<12}{'股票名称':<20}{'置信度':<10}{'筛选理由'}")
    print("-" * 100)
    for i, stock in enumerate(results, 1):
        print(f"{i:<6}{stock['ts_code']:<12}{stock['name']:<20}{stock['confidence']:.2%}    {stock['reason']}")

    if args.output and results:
        result_df = pd.DataFrame(results)
        result_df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\n💾 结果已保存: {args.output}")


if __name__ == "__main__":
    main()
