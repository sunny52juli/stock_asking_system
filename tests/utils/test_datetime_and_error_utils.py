"""测试日期工具和错误格式化工具."""

import pytest
from datetime import datetime
from utils.date import get_today_str, format_date, parse_date
from utils.errors import format_error_message, format_validation_error, format_tool_error


class TestDateTimeUtils:
    """测试日期工具函数."""
    
    def test_get_today_str_default_format(self):
        """测试默认格式获取今天日期."""
        today = get_today_str()
        assert len(today) == 8
        assert today.isdigit()
        # 验证格式为 YYYYMMDD
        datetime.strptime(today, "%Y%m%d")
    
    def test_get_today_str_custom_format(self):
        """测试自定义格式获取今天日期."""
        today_iso = get_today_str(fmt="%Y-%m-%d")
        assert len(today_iso) == 10
        datetime.strptime(today_iso, "%Y-%m-%d")
    
    def test_format_date_with_datetime(self):
        """测试格式化指定的datetime对象."""
        dt = datetime(2026, 5, 12)
        result = format_date(dt)
        assert result == "20260512"
    
    def test_format_date_with_custom_fmt(self):
        """测试自定义格式."""
        dt = datetime(2026, 5, 12, 14, 30, 0)
        result = format_date(dt, fmt="%Y-%m-%d %H:%M:%S")
        assert result == "2026-05-12 14:30:00"
    
    def test_format_date_default_now(self):
        """测试不传参数时使用当前时间."""
        result = format_date()
        # 应该是今天的日期
        expected = datetime.now().strftime("%Y%m%d")
        assert result == expected
    
    def test_parse_date_default_format(self):
        """测试解析默认格式的日期字符串."""
        dt = parse_date("20260512")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 12
    
    def test_parse_date_custom_format(self):
        """测试解析自定义格式的日期字符串."""
        dt = parse_date("2026-05-12", fmt="%Y-%m-%d")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 12


class TestErrorFormatter:
    """测试错误消息格式化工具."""
    
    def test_format_error_message_basic(self):
        """测试基本错误消息格式化."""
        result = format_error_message("测试错误")
        assert "❌ 错误：测试错误" in result
    
    def test_format_error_message_with_suggestions(self):
        """测试带建议的错误消息."""
        result = format_error_message(
            error="参数错误",
            suggestions=["建议1", "建议2"]
        )
        assert "❌ 错误：参数错误" in result
        assert "💡 建议：" in result
        assert "• 建议1" in result
        assert "• 建议2" in result
    
    def test_format_error_message_with_tips(self):
        """测试带提示的错误消息."""
        result = format_error_message(
            error="执行失败",
            tips=["提示1", "提示2"]
        )
        assert "🔧 提示：" in result
        assert "• 提示1" in result
        assert "• 提示2" in result
    
    def test_format_error_message_complete(self):
        """测试完整的错误消息（包含建议和提示）."""
        result = format_error_message(
            error="完整错误",
            suggestions=["建议A"],
            tips=["提示B"]
        )
        assert "❌ 错误：完整错误" in result
        assert "💡 建议：" in result
        assert "🔧 提示：" in result
    
    def test_format_validation_error(self):
        """测试验证错误格式化."""
        result = format_validation_error(
            field="expression",
            issue="变量未定义",
            fix_suggestion="在tools中添加变量定义"
        )
        assert "expression 验证失败" in result
        assert "变量未定义" in result
        assert "在tools中添加变量定义" in result
    
    def test_format_tool_error_with_correction(self):
        """测试工具错误格式化（带正确工具名）."""
        result = format_tool_error(
            tool_name="sma",
            error_msg="工具不存在",
            correct_tool="rolling_mean"
        )
        assert "工具 'sma' 不存在" in result
        assert "正确工具：'rolling_mean'" in result
    
    def test_format_tool_error_without_correction(self):
        """测试工具错误格式化（不带正确工具名）."""
        result = format_tool_error(
            tool_name="custom_tool",
            error_msg="执行超时"
        )
        assert "工具 'custom_tool' 执行失败" in result
        assert "执行超时" in result
    
    def test_format_error_message_empty_lists(self):
        """测试空列表参数."""
        result = format_error_message(
            error="测试",
            suggestions=[],
            tips=[]
        )
        assert "❌ 错误：测试" in result
        assert "💡 建议：" not in result
        assert "🔧 提示：" not in result
