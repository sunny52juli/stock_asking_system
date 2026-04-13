"""回测模块测试 - report.py"""

import pytest
from io import StringIO
import sys
from unittest.mock import patch

from src.backtest.report import print_backtest_report, format_backtest_summary


class TestPrintBacktestReport:
    """回测报告打印测试."""

    def test_print_empty_report(self, capsys):
        """测试打印空报告."""
        report = {
            'config': {
                'screening_date': '20240101',
                'holding_periods': [5, 10],
                'observation_days': 20,
            },
            'total_scripts': 0,
            'successful': 0,
            'failed': 0,
            'results': [],
        }
        
        print_backtest_report(report)
        captured = capsys.readouterr()
        
        assert '回测报告' in captured.out
        assert '20240101' in captured.out
        assert '没有回测结果' in captured.out

    def test_print_report_with_failed_script(self, capsys):
        """测试打印包含失败策略的报告."""
        report = {
            'config': {
                'screening_date': '20240101',
                'holding_periods': [5, 10],
                'observation_days': 20,
            },
            'total_scripts': 1,
            'successful': 0,
            'failed': 1,
            'results': [
                {
                    'script_name': 'test_strategy.py',
                    'status': 'failed',
                    'error': '执行错误',
                }
            ],
        }
        
        print_backtest_report(report)
        captured = capsys.readouterr()
        
        assert 'test_strategy.py' in captured.out
        assert '执行失败' in captured.out
        assert '执行错误' in captured.out

    def test_print_report_with_successful_script(self, capsys):
        """测试打印成功策略的报告."""
        report = {
            'config': {
                'screening_date': '20240101',
                'holding_periods': [5, 10],
                'observation_days': 20,
            },
            'total_scripts': 1,
            'successful': 1,
            'failed': 0,
            'results': [
                {
                    'script_name': 'test_strategy.py',
                    'status': 'success',
                    'candidates_count': 5,
                    'holding_period_results': {
                        '5日': {
                            'mean': 0.05,
                            'win_rate': 0.8,
                        }
                    },
                    'holding_stocks': [
                        {
                            'ts_code': '000001.SZ',
                            'stock_name': '平安银行',
                            'industry': '银行业',
                            'return_5d': 5.23,
                        }
                    ],
                }
            ],
        }
        
        print_backtest_report(report)
        captured = capsys.readouterr()
        
        assert 'test_strategy.py' in captured.out
        assert '候选股票数：5' in captured.out
        assert '平安银行' in captured.out
        assert '5.23%' in captured.out

    def test_print_stock_table_empty(self, capsys):
        """测试打印空股票表格."""
        from src.backtest.report import _print_stock_table
        
        _print_stock_table([])
        captured = capsys.readouterr()
        assert captured.out == ''

    def test_print_stock_table_with_data(self, capsys):
        """测试打印股票表格."""
        from src.backtest.report import _print_stock_table
        
        stocks = [
            {
                'ts_code': '000001.SZ',
                'stock_name': '平安银行',
                'industry': '银行业',
                'return_5d': 5.23,
                'return_10d': 8.45,
            },
            {
                'ts_code': '000002.SZ',
                'stock_name': '万科A',
                'industry': '房地产业',
                'return_5d': -2.15,
                'return_10d': None,
            },
        ]
        
        _print_stock_table(stocks)
        captured = capsys.readouterr()
        
        assert '代码' in captured.out
        assert '名称' in captured.out
        assert '行业' in captured.out
        assert '5日收益%' in captured.out
        assert '10日收益%' in captured.out
        assert '平安银行' in captured.out
        assert '5.23%' in captured.out
        assert '-2.15%' in captured.out


class TestFormatBacktestSummary:
    """回测摘要格式化测试."""

    def test_format_summary_basic(self):
        """测试基本摘要格式化."""
        report = {
            'config': {
                'screening_date': '20240101',
            },
            'total_scripts': 10,
            'successful': 8,
            'failed': 2,
        }
        
        summary = format_backtest_summary(report)
        
        assert '回测完成' in summary
        assert '20240101' in summary
        assert '策略总数：10' in summary
        assert '成功：8' in summary
        assert '失败：2' in summary

    def test_format_summary_missing_fields(self):
        """测试缺失字段的摘要格式化."""
        report = {}
        
        summary = format_backtest_summary(report)
        
        assert '回测完成' in summary
        assert 'N/A' in summary
        assert '0' in summary
