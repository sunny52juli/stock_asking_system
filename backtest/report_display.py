#!/usr/bin/env python3
"""
回测报告展示模块

提供回测结果的表格化展示功能
"""


def print_backtest_report(report: dict):
    """
    打印回测报告（增强版）
    
    Args:
        report: 回测报告字典，包含 results 和 summary
    """
    # 从配置中动态获取持有期
    from config.backtest_config import StockConfig
    holding_periods = StockConfig.BACKTEST_LOOKBACK_DAYS
    
    # 1. 回测报告详情表 - 第一行展示具体股票信息
    results = report.get('results', [])
    if results:
        print("\n" + "="*160)
        print("📄 回测报告详情 - 持仓股票及收益")
        print("="*160)
        
        for result in results:
            script_name = result.get('script_name', '未知')
            status = result.get('status', '未知')
            
            if status != '成功':
                continue
            
            print(f"\n【{script_name}】")
            print("-" * 160)
            
            # 获取持仓股票数据
            holding_stocks = result.get('holding_stocks', [])
            if not holding_stocks or not isinstance(holding_stocks, list):
                print("暂无持仓股票数据")
                continue
            
            # 第一行：输出前 20 个股票的名称、行业和收益率
            print("\n前 20 大持仓股票：")
            
            # 动态构建表头
            header = f"{'股票名称':<12} {'行业':<15}"
            for period in holding_periods:
                header += f" {period}日收益率     "
            print(header)
            print("-" * (27 + len(holding_periods) * 13))
            
            for i, stock in enumerate(holding_stocks[:20]):
                stock_name = stock.get('stock_name', 'N/A')
                industry = stock.get('industry', 'N/A')
                
                row = f"{stock_name:<12} {industry:<15}"
                for period in holding_periods:
                    ret_key = f'return_{period}d'
                    ret = stock.get(ret_key, 0)
                    ret_str = f"{ret:.2f}%" if ret is not None else 'N/A'
                    row += f" {ret_str:>10}"
                print(row)
            
            # 第二行：统计信息（表格形式）
            print("\n持仓统计：")
            stats = result.get('portfolio_stats', {})
            
            if stats:
                # 构建表格数据
                table_data = []
                for period in holding_periods:
                    period_key = f'day_{period}'
                    period_stats = stats.get(period_key, {})
                    
                    if period_stats:
                        avg_return = period_stats.get('avg_return', 0)
                        max_return = period_stats.get('max_return', 0)
                        min_return = period_stats.get('min_return', 0)
                        win_rate = period_stats.get('win_rate', 0)
                        count = period_stats.get('count', 0)
                        
                        table_data.append({
                            '持有期': f'{period}日',
                            '有效样本': f'{count}只',
                            '平均收益': f'{avg_return:>8.2f}%',
                            '最大收益': f'{max_return:>8.2f}%',
                            '最大亏损': f'{min_return:>8.2f}%',
                            '胜率': f'{win_rate:>6.1f}%',
                        })
                
                # 打印统计表
                if table_data:
                    _print_table(table_data)
            
            print("\n" + "="*160)
        
        print("="*160)
    
    # 2. 汇总统计表
    summary = report.get('summary', {})
    if summary and isinstance(summary, list) and len(summary) > 0:
        print("\n" + "="*140)
        print("📊 回测汇总统计")
        print("="*140)
        
        # 收集汇总数据
        summary_table = []
        for item in summary:
            if isinstance(item, dict):
                script_name = item.get('script', '未知')
                status = item.get('status', '未知')
                
                if status == '成功':
                    row = {
                        '策略文件': script_name[:30] + '...' if len(script_name) > 30 else script_name,
                        '状态': '✅',
                    }
                    
                    # 添加每个持有期的汇总指标
                    performance = item.get('performance', {})
                    if performance and isinstance(performance, dict):
                        for period_key, stats in performance.items():
                            if isinstance(stats, dict):
                                period_name = f"持仓{period_key.replace('日', '')}日"
                                row[f'{period_name}\n年化'] = f"{stats.get('年化收益率', 'N/A')}"
                                row[f'{period_name}\n胜率'] = f"{stats.get('胜率', 'N/A')}"
                                row[f'{period_name}\n有效数'] = stats.get('有效股票数', 'N/A')
                    else:
                        candidates_count = item.get('candidates', 0)
                        row['备注'] = f'候选{candidates_count}只'
                    
                    summary_table.append(row)
                else:
                    summary_table.append({
                        '策略文件': script_name[:30] + '...' if len(script_name) > 30 else script_name,
                        '状态': '❌',
                        '备注': '执行失败'
                    })
        
        # 打印汇总表
        if summary_table:
            _print_table(summary_table)
        
        print("="*140)


def _print_table(table_data: list[dict]):
    """
    打印表格（辅助函数）
    
    Args:
        table_data: 表格数据列表，每个元素是一个字典
    """
    if not table_data:
        return
    
    # 计算每列的最大宽度
    all_headers = list(table_data[0].keys())
    col_widths = {}
    for header in all_headers:
        max_width = len(header)
        for row in table_data:
            cell_value = str(row.get(header, ''))
            max_width = max(max_width, len(cell_value))
        col_widths[header] = min(max_width + 2, 20)  # 限制最大宽度
    
    # 打印表头
    header_line = "|"
    separator = "|"
    for header in all_headers:
        width = col_widths[header]
        header_line += f" {header.center(width-1)} |"
        separator += "-" * width + "|"
    
    print(header_line)
    print(separator)
    
    # 打印数据行
    for row in table_data:
        data_line = "|"
        for header in all_headers:
            width = col_widths[header]
            cell_value = str(row.get(header, ''))
            # 截断过长的内容
            if len(cell_value) > width - 2:
                cell_value = cell_value[:width-3] + "..."
            data_line += f" {cell_value.center(width-1)} |"
        print(data_line)
    
    print(separator)
