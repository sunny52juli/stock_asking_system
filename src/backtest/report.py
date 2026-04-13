"""回测报告生成器 - 格式化并展示回测结果.

本模块从 backtest/report_display.py 重构而来，
提供更清晰的报告展示功能。
"""

from __future__ import annotations

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def print_backtest_report(report: dict):
    """打印回测报告.
    
    Args:
        report: 回测报告字典
    """
    print("\n回测报告详情 - 持仓股票及收益")
    print("=" * 100)
    
    # 各策略详情
    results = report.get("results", [])
    if not results:
        print("\n⚠️  没有回测结果")
        return
    
    for i, result in enumerate(results, 1):
        print(f"\n【{result.get('script_name', 'N/A')}】")
        
        status = result.get("status", "unknown")
        if status == "failed":
            print(f"   ❌ 执行失败：{result.get('error', '未知错误')}")
            continue
        
        candidates_count = len(result.get("candidates", []))
        print(f"\n前 {candidates_count} 大持仓股票：")
        
        # 持仓股票详情
        holding_stocks = result.get("holding_stocks", [])
        if holding_stocks:
            _print_stock_table_detailed(holding_stocks)
        
        # 持仓统计
        portfolio_stats = result.get("portfolio_stats", {})
        if portfolio_stats:
            print(f"\n持仓统计：")
            _print_portfolio_stats_table(portfolio_stats)
    
    print("\n" + "=" * 100)


def _print_stock_table_detailed(stocks: list[dict]):
    """打印详细股票表格（所有持仓）.
    
    Args:
        stocks: 股票列表
    """
    if not stocks:
        return
    
    # 表头
    headers = ["股票名称", "行业"]
    
    # 动态添加收益率列
    first_stock = stocks[0]
    ret_columns = sorted([k for k in first_stock.keys() if k.startswith("return_")])
    for col in ret_columns:
        period = col.replace("return_", "").replace("d", "")
        headers.append(f"{period}日收益率")
    
    # 计算列宽
    col_widths = []
    for i, header in enumerate(headers):
        max_width = len(header)
        for stock in stocks:
            if i == 0:  # 股票名称
                value = str(stock.get("stock_name", ""))
            elif i == 1:  # 行业
                value = str(stock.get("industry", ""))
            else:  # 收益率
                ret_key = ret_columns[i - 2]
                ret_value = stock.get(ret_key)
                value = f"{ret_value:.2f}%" if ret_value is not None else "N/A"
            max_width = max(max_width, len(value))
        col_widths.append(max_width + 2)  # 留2个空格
    
    # 打印表头
    header_str = "".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    print(header_str)
    print("-" * sum(col_widths))
    
    # 打印数据行
    for stock in stocks:
        row_data = [
            str(stock.get("stock_name", "")),
            str(stock.get("industry", "")),
        ]
        
        # 添加收益率
        for col in ret_columns:
            ret_value = stock.get(col)
            if ret_value is not None:
                row_data.append(f"{ret_value:>8.2f}%")
            else:
                row_data.append(f"{'N/A':>8}")
        
        row_str = "".join(f"{str(d):<{w}}" for d, w in zip(row_data, col_widths))
        print(row_str)


def _print_portfolio_stats_table(portfolio_stats: dict):
    """打印持仓统计表.
    
    Args:
        portfolio_stats: 持仓统计字典
    """
    if not portfolio_stats:
        return
    
    # 表头和列宽
    headers = ["持有期", "有效样本", "平均收益", "最大收益", "最大亏损", "胜率"]
    col_widths = [6, 8, 10, 10, 10, 8]
    
    # 计算总宽度
    total_width = sum(col_widths) + len(headers) + 1
    separator = "+" + "+".join("-" * w for w in col_widths) + "+"
    
    # 打印表头
    print(separator)
    header_str = "|" + "|".join(f"{h:^{w}}" for h, w in zip(headers, col_widths)) + "|"
    print(header_str)
    print(separator)
    
    # 打印数据行（按持有期排序）
    sorted_periods = sorted(portfolio_stats.keys(), key=lambda x: int(x.replace("day_", "")))
    for period_key in sorted_periods:
        stats = portfolio_stats[period_key]
        period = period_key.replace("day_", "") + "日"
        count = f"{stats.get('count', 0)}只"
        avg_ret = f"{stats.get('avg_return', 0):+.2f}%"
        max_ret = f"{stats.get('max_return', 0):+.2f}%"
        min_ret = f"{stats.get('min_return', 0):+.2f}%"
        win_rate = f"{stats.get('win_rate', 0):.1f}%"
        
        row_str = "|" + "|".join([
            f"{period:^{col_widths[0]}}",
            f"{count:^{col_widths[1]}}",
            f"{avg_ret:^{col_widths[2]}}",
            f"{max_ret:^{col_widths[3]}}",
            f"{min_ret:^{col_widths[4]}}",
            f"{win_rate:^{col_widths[5]}}",
        ]) + "|"
        print(row_str)
    
    print(separator)


def format_backtest_summary(report: dict) -> str:
    """格式化回测摘要（用于日志或API返回）.
    
    Args:
        report: 回测报告
        
    Returns:
        格式化的摘要字符串
    """
    lines = [
        f"回测完成",
        f"筛选日期：{report.get('config', {}).get('screening_date', 'N/A')}",
        f"策略总数：{report.get('total_scripts', 0)}",
        f"成功：{report.get('successful', 0)}",
        f"失败：{report.get('failed', 0)}",
    ]
    
    return "\n".join(lines)
