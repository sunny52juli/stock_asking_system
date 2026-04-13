"""筛选脚本生成器."""

from __future__ import annotations

import json
import time
from datetime import datetime

from utils.datetime_utils import format_date
from utils.fs import ensure_dir, sanitize_filename


class ScreeningScriptGenerator:
    """
    筛选脚本生成器
    
    功能：
    1. 根据筛选逻辑生成可执行的 Python 脚本
    2. 支持一次生成多个版本（strategy_num）
    3. 自动保存到策略专属文件夹
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        ensure_dir(output_dir)

    def generate_script(self, screening_logic: dict, query: str = "", strategy_num: int = 1, strategy_name: str = None) -> list[str]:
        """生成筛选脚本并保存到策略专属文件夹
        
        Args:
            screening_logic: 筛选逻辑字典
            query: 原始查询字符串
            strategy_num: 生成的策略版本数量（默认 1）
            strategy_name: 策略名称（如果提供，将覆盖 screening_logic 中的 name，确保与配置一致）
            
        Returns:
            保存的文件路径列表
        """
        # 优先使用传入的策略名称，确保与配置文件一致
        logic_name = strategy_name if strategy_name else screening_logic.get("name", "未命名筛选")
        logic_name_safe = sanitize_filename(logic_name)
        
        # 创建策略专属文件夹
        strategy_dir = ensure_dir(f"{self.output_dir}/{logic_name_safe}")
        
        saved_files = []
        
        # 生成指定数量的策略版本，每个版本间隔 1 秒确保时间戳不同
        for i in range(strategy_num):
            timestamp = format_date(fmt="%Y%m%d_%H%M%S")
            
            # 文件名：策略名_时间戳.py（直接用时间戳区分版本）
            filename = f"{logic_name_safe}_{timestamp}.py"
            filepath = f"{strategy_dir}/{filename}"
            
            content = self._generate_script_content(screening_logic, query)
            with open(filepath, "w", encoding="utf-8-sig") as f:
                f.write(content)
            
            print(f"      💾 策略脚本已保存：{filepath}")
            saved_files.append(filepath)
            
            # 如果还有下一个版本，等待 1 秒确保时间戳不同
            if i < strategy_num - 1:
                time.sleep(1)
        
        return saved_files

    def _generate_script_content(self, screening_logic: dict, query: str) -> str:
        logic_name = screening_logic.get("name", "未命名筛选")
        rationale = screening_logic.get("rationale", "无说明")
        tools = screening_logic.get("tools", [])
        expression = screening_logic.get("expression", "")
        confidence_formula = screening_logic.get("confidence_formula", "1.0")
        
        logic_json = json.dumps(screening_logic, ensure_ascii=False, indent=4)
        tools_desc = ""
        for i, tool in enumerate(tools, 1):
            tool_name = tool.get("tool", "unknown")
            params = tool.get("params", {})
            var_name = tool.get("var", f"temp_{i}")
            # 使用清晰的描述格式，避免 Agent 误认为是可执行代码
            tools_desc += f"    {i}. {var_name}: 通过工具 '{tool_name}' 计算，参数={params}\n"

        # 脚本内仅引用 src, 不引用 stock_asking_system / factor_backtest_system
        script = f'''#!/usr/bin/env python3
"""
筛选逻辑脚本: {logic_name}
(由 core.agent 生成, 仅依赖 core)

原始查询: {query if query else "N/A"}

筛选说明:
    {rationale}

工具步骤:
{tools_desc if tools_desc else "    无工具调用"}
筛选表达式: {expression}
置信度公式: {confidence_formula}

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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
SCREENING_LOGIC = {logic_json}
# ==================== 筛选逻辑定义结束 ====================

ORIGINAL_QUERY = """{query}"""


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
    
    parser = argparse.ArgumentParser(description=f'{logic_name} - 筛选脚本')
    parser.add_argument('--top_n', type=int, default=20, help='返回股票数量（默认 20）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（可选）')
    args = parser.parse_args()

    # 检查 Tushare token 配置
    if not os.getenv('TUSHARE_TOKEN'):
        print("⚠️ 警告: 未检测到 TUSHARE_TOKEN 环境变量")
        print("   请在 .env 文件中设置 TUSHARE_TOKEN=your_token")
        print("   或者设置环境变量: export TUSHARE_TOKEN=your_token")
        print("\\n💡 提示: 如果已有缓存数据，脚本仍可能正常运行")
        print("-" * 60)
    
    from datahub.loaders import StockDataLoader

    print("📊 加载市场数据...")
    try:
        # 独立运行时使用最新交易日期，不依赖 backtest_config
        from infrastructure.config.settings import get_settings
        settings = get_settings()
        loader = StockDataLoader()
        data = loader.load_market_data(observation_days=settings.observation_days)
        print(f"✅ 数据加载完成：{{len(data)}} 条记录")
    except ValueError as e:
        if "Tushare token" in str(e):
            print(f"❌ 数据加载失败: {{e}}")
            print("\\n解决方法:")
            print("1. 在项目根目录创建 .env 文件")
            print("2. 添加以下内容: TUSHARE_TOKEN=your_token_here")
            print("3. 重新运行脚本")
            sys.exit(1)
        else:
            raise

    print("\\n🔍 执行筛选: " + logic_name)
    results = screen_with_data(data, top_n=args.top_n)

    print("\\n✅ 找到 " + str(len(results)) + " 只符合条件的股票")
    print("{{:<6}}{{:<12}}{{:<20}}{{:<10}}{{}}".format('排名', '股票代码', '股票名称', '置信度', '筛选理由'))
    print("-" * 100)
    for i, stock in enumerate(results, 1):
        print("{{:<6}}{{:<12}}{{:<20}}{{:.2%}}    {{}}".format(i, stock['ts_code'], stock['name'], stock['confidence'], stock['reason']))

    if args.output and results:
        result_df = pd.DataFrame(results)
        result_df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print("\\n💾 结果已保存: " + str(args.output))


if __name__ == "__main__":
    main()
'''
        return script
