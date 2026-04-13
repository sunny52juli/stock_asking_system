#!/usr/bin/env python3
"""
筛选逻辑脚本: 放量突破策略
(由 core.agent 生成, 仅依赖 core)

原始查询: 找出最近放量突破的股票：
1. 成交量较前期放大（至少 1.5 倍）
2. 涨幅>3%
3. 技术形态良好


筛选说明:
    无说明

工具步骤:
    1. vol_ma20: 通过工具 'rolling_mean' 计算，参数={'column': 'vol', 'window': 20}
    2. vol_ma5: 通过工具 'rolling_mean' 计算，参数={'column': 'vol', 'window': 5}
    3. pct_1d: 通过工具 'pct_change' 计算，参数={'column': 'close', 'periods': 1}
    4. ma5: 通过工具 'rolling_mean' 计算，参数={'column': 'close', 'window': 5}
    5. ma10: 通过工具 'rolling_mean' 计算，参数={'column': 'close', 'window': 10}
    6. ma20: 通过工具 'rolling_mean' 计算，参数={'column': 'close', 'window': 20}
    7. high_20: 通过工具 'rolling_max' 计算，参数={'column': 'high', 'window': 20}
    8. low_20: 通过工具 'rolling_min' 计算，参数={'column': 'low', 'window': 20}

筛选表达式: (vol > vol_ma20 * 1.5) & (pct_1d > 0.03) & (close > ma5) & (close > ma10) & (close > ma20) & (close >= high_20 * 0.95)
置信度公式: rank_normalize(vol / vol_ma20) * 0.4 + rank_normalize(pct_1d) * 0.3 + rank_normalize((close - ma20) / ma20) * 0.3

生成时间: 2026-04-14 00:26:58
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
    "name": "放量突破策略",
    "description": "筛选成交量明显放大、涨幅超过3%且技术形态良好的股票",
    "tools": [
        {
            "tool": "rolling_mean",
            "params": {
                "column": "vol",
                "window": 20
            },
            "var": "vol_ma20"
        },
        {
            "tool": "rolling_mean",
            "params": {
                "column": "vol",
                "window": 5
            },
            "var": "vol_ma5"
        },
        {
            "tool": "pct_change",
            "params": {
                "column": "close",
                "periods": 1
            },
            "var": "pct_1d"
        },
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
        },
        {
            "tool": "rolling_max",
            "params": {
                "column": "high",
                "window": 20
            },
            "var": "high_20"
        },
        {
            "tool": "rolling_min",
            "params": {
                "column": "low",
                "window": 20
            },
            "var": "low_20"
        }
    ],
    "expression": "(vol > vol_ma20 * 1.5) & (pct_1d > 0.03) & (close > ma5) & (close > ma10) & (close > ma20) & (close >= high_20 * 0.95)",
    "confidence_formula": "rank_normalize(vol / vol_ma20) * 0.4 + rank_normalize(pct_1d) * 0.3 + rank_normalize((close - ma20) / ma20) * 0.3",
    "explanation": "1. 成交量较20日均量放大1.5倍以上\n2. 当日涨幅超过3%\n3. 收盘价站上5日、10日、20日均线\n4. 收盘价接近20日最高价（达到95%以上），显示强势突破形态"
}
# ==================== 筛选逻辑定义结束 ====================

ORIGINAL_QUERY = """找出最近放量突破的股票：
1. 成交量较前期放大（至少 1.5 倍）
2. 涨幅>3%
3. 技术形态良好
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
    
    parser = argparse.ArgumentParser(description=f'放量突破策略 - 筛选脚本')
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
