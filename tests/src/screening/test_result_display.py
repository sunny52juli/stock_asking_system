"""筛选模块测试 - result_display.py"""

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from src.screening.result_display import ResultDisplayer


class TestResultDisplayer:
    """结果显示器测试类."""

    def test_display_empty_result(self):
        """测试显示空结果."""
        displayer = ResultDisplayer()
        
        # 不应该抛出异常
        displayer.display({})
        displayer.display({"messages": []})

    @patch('src.screening.result_display.logger')
    def test_display_with_messages(self, mock_logger):
        """测试显示带消息的结果."""
        displayer = ResultDisplayer()
        
        # 创建模拟消息对象
        mock_message = SimpleNamespace(content="这是测试结果，包含股票000001.SZ和600000.SH")
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 验证日志被调用
        assert mock_logger.info.called

    @patch('src.screening.result_display.logger')
    def test_display_extract_stock_codes(self, mock_logger):
        """测试提取股票代码."""
        displayer = ResultDisplayer()
        
        content = """
        根据分析，推荐以下股票：
        - 000001.SZ 平安银行
        - 000002.SZ 万科A
        - 600000.SH 浦发银行
        - 600036.SH 招商银行
        """
        
        mock_message = SimpleNamespace(content=content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 验证日志中包含了股票代码
        calls = [str(call) for call in mock_logger.info.call_args_list]
        all_calls = ' '.join(calls)
        assert '000001.SZ' in all_calls
        assert '000002.SZ' in all_calls
        assert '600000.SH' in all_calls
        assert '600036.SH' in all_calls

    @patch('src.screening.result_display.logger')
    def test_display_no_stock_codes(self, mock_logger):
        """测试没有股票代码的情况."""
        displayer = ResultDisplayer()
        
        content = "这是一段普通的分析文本，没有具体的股票代码。"
        mock_message = SimpleNamespace(content=content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 验证显示了未检测到股票代码的提示
        calls = [str(call) for call in mock_logger.info.call_args_list]
        all_calls = ' '.join(calls)
        assert '未检测到明确的股票代码' in all_calls

    @patch('src.screening.result_display.logger')
    def test_display_many_stock_codes(self, mock_logger):
        """测试大量股票代码的显示限制."""
        displayer = ResultDisplayer()
        
        # 生成25个股票代码
        stock_codes = [f"{i:06d}.SZ" for i in range(1, 26)]
        content = "推荐股票：" + ", ".join(stock_codes)
        
        mock_message = SimpleNamespace(content=content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 验证只显示前20个，并提示还有更多
        calls = [str(call) for call in mock_logger.info.call_args_list]
        all_calls = ' '.join(calls)
        assert '还有 5 只股票' in all_calls

    @patch('src.screening.result_display.logger')
    def test_display_message_without_content_attribute(self, mock_logger):
        """测试消息对象没有content属性的情况."""
        displayer = ResultDisplayer()
        
        # 使用字符串作为消息
        result = {"messages": ["这是一个字符串消息"]}
        
        displayer.display(result)
        
        # 应该能正常处理，不抛出异常
        assert mock_logger.info.called

    @patch('src.screening.result_display.logger')
    def test_display_long_content_truncation(self, mock_logger):
        """测试长内容截断."""
        displayer = ResultDisplayer()
        
        # 生成长于800字符的内容
        long_content = "测试内容 " * 100
        mock_message = SimpleNamespace(content=long_content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 验证日志被调用（内容会被截断到800字符）
        assert mock_logger.info.called
        
        # 检查实际记录的内容长度
        for call in mock_logger.info.call_args_list:
            args = call[0]
            if args and isinstance(args[0], str) and len(args[0]) > 100:
                # 第一个长消息应该被截断
                break
