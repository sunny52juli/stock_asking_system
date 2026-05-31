"""测试常量提取、日志助手."""

import pytest
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch
from utils.date import (
    DATE_FMT_YMD, DATE_FMT_ISO, DATE_FMT_FULL, DATE_FMT_TIMESTAMP,
    format_date, get_today_str, parse_date
)
from utils.logging import (
    log_success, log_warning, log_error, log_info, log_debug,
    log_section, log_step,
    LOG_PREFIX_SUCCESS, LOG_PREFIX_WARNING, LOG_PREFIX_ERROR,
    LOG_PREFIX_INFO, LOG_PREFIX_DEBUG
)


class TestDateConstants:
    """测试日期格式常量."""
    
    def test_date_fmt_ymd(self):
        """测试 YYYYMMDD 格式常量."""
        assert DATE_FMT_YMD == "%Y%m%d"
        dt = datetime(2026, 5, 12)
        assert dt.strftime(DATE_FMT_YMD) == "20260512"
    
    def test_date_fmt_iso(self):
        """测试 ISO 格式常量."""
        assert DATE_FMT_ISO == "%Y-%m-%d"
        dt = datetime(2026, 5, 12)
        assert dt.strftime(DATE_FMT_ISO) == "2026-05-12"
    
    def test_date_fmt_full(self):
        """测试完整日期时间格式常量."""
        assert DATE_FMT_FULL == "%Y-%m-%d %H:%M:%S"
        dt = datetime(2026, 5, 12, 14, 30, 0)
        assert dt.strftime(DATE_FMT_FULL) == "2026-05-12 14:30:00"
    
    def test_date_fmt_timestamp(self):
        """测试时间戳格式常量."""
        assert DATE_FMT_TIMESTAMP == "%Y%m%d_%H%M%S"
        dt = datetime(2026, 5, 12, 14, 30, 45)
        assert dt.strftime(DATE_FMT_TIMESTAMP) == "20260512_143045"
    
    def test_format_date_uses_constant(self):
        """测试 format_date 使用常量作为默认值."""
        result = format_date(datetime(2026, 5, 12))
        assert result == "20260512"
    
    def test_get_today_str_uses_constant(self):
        """测试 get_today_str 使用常量作为默认值."""
        today = get_today_str()
        expected = datetime.now().strftime(DATE_FMT_YMD)
        assert today == expected
    
    def test_parse_date_uses_constant(self):
        """测试 parse_date 使用常量作为默认值."""
        dt = parse_date("20260512")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 12


class TestLogHelpers:
    """测试日志助手函数."""
    
    @pytest.fixture
    def mock_logger(self):
        """创建模拟 logger."""
        return MagicMock()
    
    def test_log_success(self, mock_logger):
        """测试成功日志."""
        log_success("测试成功", logger_obj=mock_logger)
        mock_logger.info.assert_called_once_with(f"{LOG_PREFIX_SUCCESS} 测试成功")
    
    def test_log_warning(self, mock_logger):
        """测试警告日志."""
        log_warning("测试警告", logger_obj=mock_logger)
        mock_logger.warning.assert_called_once_with(f"{LOG_PREFIX_WARNING} 测试警告")
    
    def test_log_error(self, mock_logger):
        """测试错误日志."""
        log_error("测试错误", logger_obj=mock_logger)
        mock_logger.error.assert_called_once_with(f"{LOG_PREFIX_ERROR} 测试错误", exc_info=False)
    
    def test_log_error_with_exc_info(self, mock_logger):
        """测试带异常信息的错误日志."""
        log_error("测试错误", exc_info=True, logger_obj=mock_logger)
        mock_logger.error.assert_called_once_with(f"{LOG_PREFIX_ERROR} 测试错误", exc_info=True)
    
    def test_log_info(self, mock_logger):
        """测试信息日志."""
        log_info("测试信息", logger_obj=mock_logger)
        mock_logger.info.assert_called_once_with(f"{LOG_PREFIX_INFO} 测试信息")
    
    def test_log_debug(self, mock_logger):
        """测试调试日志."""
        log_debug("测试调试", logger_obj=mock_logger)
        mock_logger.debug.assert_called_once_with(f"{LOG_PREFIX_DEBUG} 测试调试")
    
    def test_log_section(self, mock_logger):
        """测试分段标题."""
        log_section("测试标题", char="=", width=10, logger_obj=mock_logger)
        calls = mock_logger.info.call_args_list
        assert len(calls) == 3
        assert calls[0][0][0] == "=" * 10
        assert calls[1][0][0] == "测试标题"
        assert calls[2][0][0] == "=" * 10
    
    def test_log_step(self, mock_logger):
        """测试步骤进度."""
        log_step(1, 3, "加载数据", logger_obj=mock_logger)
        mock_logger.info.assert_called_once_with("[步骤 1/3] 加载数据")
    
    def test_log_with_format_args(self, mock_logger):
        """测试带格式化参数的日志."""
        log_success("处理了 %d 条记录", 100, logger_obj=mock_logger)
        mock_logger.info.assert_called_once_with(f"{LOG_PREFIX_SUCCESS} 处理了 %d 条记录", 100)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
