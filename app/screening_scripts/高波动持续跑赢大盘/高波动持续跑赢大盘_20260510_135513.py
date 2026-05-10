#!/usr/bin/env python3
"""
筛选逻辑脚本: 高波动持续跑赢大盘
(由 core.agent 生成, 仅依赖 core)

原始查询: 找出高波动且持续跑赢大盘的股票

筛选说明:
    筛选高波动(ATR排名前50%)且持续跑赢大盘(Alpha>0, 跑赢天数>50%, Beta>0.8)的强势股

工具步骤:
    1. atr14: 通过工具 'atr' 计算，参数={'high': 'high', 'low': 'low', 'close': 'close', 'window': 14}
    2. alpha_60d: 通过工具 'alpha' 计算，参数={'stock_col': 'close', 'index_col': 'index_close', 'window': 60}
    3. outperform_rate_60d: 通过工具 'outperform_rate' 计算，参数={'stock_col': 'close', 'index_col': 'index_close', 'window': 60}
    4. beta_60d: 通过工具 'beta' 计算，参数={'stock_col': 'close', 'index_col': 'index_close', 'window': 60}
    5. atr_rank: 通过工具 'rank_normalize' 计算，参数={'values': 'atr14'}
    6. alpha_rank: 通过工具 'rank_normalize' 计算，参数={'values': 'alpha_60d'}

筛选表达式: (alpha_60d > 0) & (outperform_rate_60d > 0.5) & (atr_rank > 0.5) & (beta_60d > 0.8)
置信度公式: atr_rank * 0.4 + alpha_rank * 0.4 + outperform_rate_60d * 0.2

生成时间: 2026-05-10 13:55:13
"""

import sys
import os
import json
import argparse
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

# 导入 StockScreener
from utils.screening.stock_screener import StockScreener
from infrastructure.config.settings import get_settings
from src.agent.services.stock_pool_service import StockPoolService


# ==================== 筛选逻辑定义 ====================
SCREENING_LOGIC = {
    "name": "高波动持续跑赢大盘",
    "tools": [
        {
            "tool": "atr",
            "params": {
                "high": "high",
                "low": "low",
                "close": "close",
                "window": 14
            },
            "var": "atr14"
        },
        {
            "tool": "alpha",
            "params": {
                "stock_col": "close",
                "index_col": "index_close",
                "window": 60
            },
            "var": "alpha_60d"
        },
        {
            "tool": "outperform_rate",
            "params": {
                "stock_col": "close",
                "index_col": "index_close",
                "window": 60
            },
            "var": "outperform_rate_60d"
        },
        {
            "tool": "beta",
            "params": {
                "stock_col": "close",
                "index_col": "index_close",
                "window": 60
            },
            "var": "beta_60d"
        },
        {
            "tool": "rank_normalize",
            "params": {
                "values": "atr14"
            },
            "var": "atr_rank"
        },
        {
            "tool": "rank_normalize",
            "params": {
                "values": "alpha_60d"
            },
            "var": "alpha_rank"
        }
    ],
    "expression": "(alpha_60d > 0) & (outperform_rate_60d > 0.5) & (atr_rank > 0.5) & (beta_60d > 0.8)",
    "confidence_formula": "atr_rank * 0.4 + alpha_rank * 0.4 + outperform_rate_60d * 0.2",
    "rationale": "筛选高波动(ATR排名前50%)且持续跑赢大盘(Alpha>0, 跑赢天数>50%, Beta>0.8)的强势股"
}
# ==================== 筛选逻辑定义结束 ====================

ORIGINAL_QUERY = """找出高波动且持续跑赢大盘的股票"""


def get_screening_logic() -> dict:
    """获取筛选逻辑定义（供加载器使用）"""
    return SCREENING_LOGIC


def screen_with_data(data: pd.DataFrame, top_n: int = 10, screening_date: str = None) -> List[Dict[str, Any]]:
    """
    使用提供的数据执行筛选（仅依赖 core.stock_screener）
    """
    # 使用全局变量中的指数数据和股票代码
    index_data = globals().get('INDEX_DATA', None)
    stock_codes = globals().get('STOCK_CODES', None)
    
    screener = StockScreener(data, screening_date=screening_date, stock_codes=stock_codes, index_data=index_data)
    return screener.execute_screening(
        screening_logic=SCREENING_LOGIC,
        top_n=top_n,
        query=ORIGINAL_QUERY
    )


def main():
    """主函数 - 独立运行时使用 (数据来自 core.data_loading)"""

    logic_name = SCREENING_LOGIC.get("name", "未命名筛选")
    
    parser = argparse.ArgumentParser(description=f'高波动持续跑赢大盘 - 筛选脚本')
    parser.add_argument('--top_n', type=int, default=10, help='返回股票数量（默认 10）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（可选）')
    args = parser.parse_args()

    # 检查 Tushare token 配置
    if not os.getenv('TUSHARE_TOKEN'):
        print("[WARN] 警告: 未检测到 TUSHARE_TOKEN 环境变量")
        print("   请在 .env 文件中设置 TUSHARE_TOKEN=your_token")
        print("   或者设置环境变量: export TUSHARE_TOKEN=your_token")
        print("\n💡 提示: 如果已有缓存数据，脚本仍可能正常运行")
        print("-" * 60)
    

    print("[DATA] 加载市场数据...")
    try:
        # 使用与 screener.py 相同的数据加载方式
        # 关键：必须传入 project_root，确保从项目根目录加载配置文件
        settings = get_settings(project_root=project_root)
        stock_pool_service = StockPoolService(settings)
        data, stock_codes, index_data = stock_pool_service.apply_filter()
        print(f"[OK] 数据加载完成：{len(data)} 条记录，{len(stock_codes)} 只股票")
        
        # 将指数数据传递给全局变量，供 screen_with_data 使用
        globals()['INDEX_DATA'] = index_data
        globals()['STOCK_CODES'] = stock_codes
    except ValueError as e:
        if "Tushare token" in str(e):
            print(f"[ERROR] 数据加载失败: {e}")
            print("\n解决方法:")
            print("1. 在项目根目录创建 .env 文件")
            print("2. 添加以下内容: TUSHARE_TOKEN=your_token_here")
            print("3. 重新运行脚本")
            sys.exit(1)
        else:
            raise

    print("\n[SEARCH] 执行筛选: " + logic_name)
    results = screen_with_data(data, top_n=args.top_n)

    print("\n[OK] 找到 " + str(len(results)) + " 只符合条件的股票")
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
