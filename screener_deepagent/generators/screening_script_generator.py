"""

"""

from __future__ import annotations

import json
import os
from datetime import datetime


def _sanitize_filename(name: str) -> str:
    illegal = ["/", "\\", ":", "*", "?", '"', "<", ">", "|", " ", "（", "）", "(", ")", "，", "。", "！", "？"]
    for c in illegal:
        name = name.replace(c, "_")
    while "__" in name:
        name = name.replace("__", "_")
    return name.strip("_")


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
        os.makedirs(self.output_dir, exist_ok=True)

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
        logic_name_safe = _sanitize_filename(logic_name)
        
        # 创建策略专属文件夹
        strategy_dir = os.path.join(self.output_dir, logic_name_safe)
        os.makedirs(strategy_dir, exist_ok=True)
        
        saved_files = []
        
        # 生成指定数量的策略版本，每个版本间隔 1 秒确保时间戳不同
        for i in range(strategy_num):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 文件名：策略名_时间戳.py（直接用时间戳区分版本）
            filename = f"{logic_name_safe}_{timestamp}.py"
            filepath = os.path.join(strategy_dir, filename)
            
            content = self._generate_script_content(screening_logic, query)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            print(f"      💾 策略脚本已保存：{filepath}")
            saved_files.append(filepath)
            
            # 如果还有下一个版本，等待 1 秒确保时间戳不同
            if i < strategy_num - 1:
                import time
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
            tools_desc += f"    {i}. {var_name} = {tool_name}({params})\n"

        # 脚本内仅引用 core, 不引用 stock_asking_system / factor_backtest_system
        script = f'''#!/usr/bin/env python3
"""
筛选逻辑脚本: {logic_name}
(由 screener_deepagent 生成, 仅依赖 core)

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

# 项目根加入路径 (脚本可能在 output/ 下)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

    parser = argparse.ArgumentParser(description='{logic_name} - 筛选脚本')
    parser.add_argument('--top_n', type=int, default=20, help='返回股票数量（默认 20）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（可选）')
    args = parser.parse_args()

    from datahub import load_market_data

    print("📊 加载市场数据...")
    # 独立运行时使用最新交易日期，不依赖 backtest_config
    data = load_market_data()
    print(f"✅ 数据加载完成：{{len(data)}} 条记录")

    print(f"\\n🔍 执行筛选: {logic_name}")
    results = screen_with_data(data, top_n=args.top_n)

    print(f"\\n✅ 找到 {{len(results)}} 只符合条件的股票")
    print(f"{{\'排名\':<6}}{{\'股票代码\':<12}}{{\'股票名称\':<20}}{{\'置信度\':<10}}{{\'筛选理由\'}}")
    print("-" * 100)
    for i, stock in enumerate(results, 1):
        print(f"{{i:<6}}{{stock[\'ts_code\']:<12}}{{stock[\'name\']:<20}}{{stock[\'confidence\']:.2%}}    {{stock[\'reason\']}}")

    if args.output and results:
        result_df = pd.DataFrame(results)
        result_df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\\n💾 结果已保存: {{args.output}}")


if __name__ == "__main__":
    main()
'''
        return script
