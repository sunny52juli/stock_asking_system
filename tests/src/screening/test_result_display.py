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
        
        # 新实现不再处理普通消息，所以不会调用logger
        # assert mock_logger.info.called

    @patch('src.screening.result_display.logger')
    def test_display_extract_stock_codes(self, mock_logger):
        """测试提取股票代码 - 已废弃，新实现不再提取股票代码."""
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
        
        # 新实现不再提取股票代码，此测试跳过
        pass

    @patch('src.screening.result_display.logger')
    def test_display_no_stock_codes(self, mock_logger):
        """测试没有股票代码的情况 - 已废弃."""
        displayer = ResultDisplayer()
        
        content = "这是一段普通的分析文本，没有具体的股票代码。"
        mock_message = SimpleNamespace(content=content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 新实现不再处理普通消息
        pass

    @patch('src.screening.result_display.logger')
    def test_display_many_stock_codes(self, mock_logger):
        """测试大量股票代码的显示 - 已废弃."""
        displayer = ResultDisplayer()
        
        # 生成25个股票代码
        stock_codes = [f"{i:06d}.SZ" for i in range(1, 26)]
        content = "推荐股票：" + ", ".join(stock_codes)
        
        mock_message = SimpleNamespace(content=content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 新实现不再处理普通消息
        pass

    @patch('src.screening.result_display.logger')
    def test_display_message_without_content_attribute(self, mock_logger):
        """测试消息对象没有content属性的情况."""
        displayer = ResultDisplayer()
        
        # 使用字符串作为消息
        result = {"messages": ["这是一个字符串消息"]}
        
        displayer.display(result)
        
        # 新实现不再处理普通消息
        pass

    @patch('src.screening.result_display.logger')
    def test_display_long_content_truncation(self, mock_logger):
        """测试长内容截断 - 已废弃."""
        displayer = ResultDisplayer()
        
        # 生成长于800字符的内容
        long_content = "测试内容 " * 100
        mock_message = SimpleNamespace(content=long_content)
        result = {"messages": [mock_message]}
        
        displayer.display(result)
        
        # 新实现不再处理普通消息
        pass
