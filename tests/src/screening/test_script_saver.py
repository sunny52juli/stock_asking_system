"""筛选模块测试 - script_saver.py"""

import pytest
import json
from unittest.mock import MagicMock, patch

from src.screening.script_saver import ScriptSaver


class TestScriptSaver:
    """脚本保存器测试类."""

    @pytest.fixture
    def mock_bridge_tools(self):
        """创建模拟的bridge tools."""
        return {
            "save_screening_script": MagicMock(return_value=json.dumps({
                "status": "success",
                "filename": "test_strategy.py"
            }))
        }

    @pytest.fixture
    def saver(self, mock_bridge_tools):
        """创建脚本保存器实例."""
        return ScriptSaver(mock_bridge_tools, auto_save=True)

    def test_init_default_auto_save(self, mock_bridge_tools):
        """测试默认auto_save为False."""
        saver = ScriptSaver(mock_bridge_tools)
        assert saver.auto_save is False

    def test_init_custom_auto_save(self, mock_bridge_tools):
        """测试自定义auto_save."""
        saver = ScriptSaver(mock_bridge_tools, auto_save=True)
        assert saver.auto_save is True

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    def test_handle_save_no_logic(self, mock_extract, mock_bridge_tools):
        """测试没有筛选逻辑时不保存."""
        mock_extract.return_value = None
        saver = ScriptSaver(mock_bridge_tools, auto_save=True)
        
        # 不应该抛出异常
        saver.handle_save({}, "测试查询")
        
        # 不应该调用保存工具
        mock_bridge_tools["save_screening_script"].assert_not_called()

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    def test_handle_save_auto_save_enabled(self, mock_extract, mock_bridge_tools):
        """测试自动保存启用时的行为."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        saver = ScriptSaver(mock_bridge_tools, auto_save=True)
        
        saver.handle_save({}, "测试查询")
        
        # 应该直接调用保存工具，不询问用户
        mock_bridge_tools["save_screening_script"].assert_called_once()

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    @patch('builtins.input', return_value='y')
    def test_handle_save_user_confirms(self, mock_input, mock_extract, mock_bridge_tools):
        """测试用户确认保存."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        saver = ScriptSaver(mock_bridge_tools, auto_save=False)
        
        saver.handle_save({}, "测试查询")
        
        # 应该询问用户并调用保存
        mock_input.assert_called_once()
        mock_bridge_tools["save_screening_script"].assert_called_once()

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    @patch('builtins.input', return_value='n')
    def test_handle_save_user_declines(self, mock_input, mock_extract, mock_bridge_tools):
        """测试用户拒绝保存."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        saver = ScriptSaver(mock_bridge_tools, auto_save=False)
        
        saver.handle_save({}, "测试查询")
        
        # 应该询问用户但不调用保存
        mock_input.assert_called_once()
        mock_bridge_tools["save_screening_script"].assert_not_called()

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    @patch('builtins.input', return_value='invalid')
    def test_handle_save_invalid_input(self, mock_input, mock_extract, mock_bridge_tools):
        """测试用户输入无效值."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        saver = ScriptSaver(mock_bridge_tools, auto_save=False)
        
        saver.handle_save({}, "测试查询")
        
        # 应该询问用户但不调用保存
        mock_input.assert_called_once()
        mock_bridge_tools["save_screening_script"].assert_not_called()

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_handle_save_keyboard_interrupt(self, mock_input, mock_extract, mock_bridge_tools):
        """测试用户中断保存操作."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        saver = ScriptSaver(mock_bridge_tools, auto_save=False)
        
        # 不应该抛出异常
        saver.handle_save({}, "测试查询")
        
        mock_bridge_tools["save_screening_script"].assert_not_called()

    def test_save_script_success(self, mock_bridge_tools):
        """测试脚本保存成功."""
        saver = ScriptSaver(mock_bridge_tools, auto_save=True)
        
        with patch('src.screening.script_saver.logger') as mock_logger:
            saver._save_script(json.dumps({"condition": "test"}), "测试查询")
            
            # 验证调用了保存工具
            mock_bridge_tools["save_screening_script"].assert_called_once()
            
            # 验证记录了成功日志
            assert any('已保存' in str(call) for call in mock_logger.info.call_args_list)

    def test_save_script_failure(self, mock_bridge_tools):
        """测试脚本保存失败."""
        # 修改mock返回失败
        mock_bridge_tools["save_screening_script"].return_value = json.dumps({
            "status": "failed",
            "error": "保存错误"
        })
        
        saver = ScriptSaver(mock_bridge_tools, auto_save=True)
        
        with patch('src.screening.script_saver.logger') as mock_logger:
            saver._save_script(json.dumps({"condition": "test"}), "测试查询")
            
            # 验证记录了警告日志
            assert any('保存失败' in str(call) for call in mock_logger.warning.call_args_list)

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    def test_handle_save_various_yes_inputs(self, mock_extract, mock_bridge_tools):
        """测试各种肯定输入."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        
        for yes_input in ['y', 'Y', 'yes', 'YES', '是']:
            mock_bridge_tools["save_screening_script"].reset_mock()
            
            with patch('builtins.input', return_value=yes_input):
                saver = ScriptSaver(mock_bridge_tools, auto_save=False)
                saver.handle_save({}, "测试查询")
                
                mock_bridge_tools["save_screening_script"].assert_called_once()

    @patch('utils.agent.result_checker._extract_screening_logic_from_result')
    def test_handle_save_various_no_inputs(self, mock_extract, mock_bridge_tools):
        """测试各种否定输入."""
        mock_extract.return_value = json.dumps({"condition": "test"})
        
        for no_input in ['n', 'N', 'no', 'NO', '否']:
            mock_bridge_tools["save_screening_script"].reset_mock()
            
            with patch('builtins.input', return_value=no_input):
                saver = ScriptSaver(mock_bridge_tools, auto_save=False)
                saver.handle_save({}, "测试查询")
                
                mock_bridge_tools["save_screening_script"].assert_not_called()
