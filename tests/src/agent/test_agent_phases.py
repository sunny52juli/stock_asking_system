"""Agent模块测试 - agent_phases.py"""

import pytest
from unittest.mock import MagicMock, patch

from src.agent.execution.agent_phases import execute_query_with_reflection, _build_retry_query


class TestBuildRetryQuery:
    """重试查询构建测试."""

    def test_no_suggestions(self):
        """测试没有建议时返回原始查询."""
        original_query = "测试查询"
        quality_report = {'suggestions': []}
        
        result = _build_retry_query(original_query, quality_report)
        
        assert result == original_query

    def test_with_suggestions(self):
        """测试有建议时添加建议到查询."""
        original_query = "测试查询"
        quality_report = {
            'suggestions': [
                '建议1：增加筛选条件',
                '建议2：优化参数',
            ]
        }
        
        result = _build_retry_query(original_query, quality_report)
        
        assert original_query in result
        assert '建议1：增加筛选条件' in result
        assert '建议2：优化参数' in result
        assert '请根据以下建议优化筛选条件' in result

    def test_single_suggestion(self):
        """测试单个建议."""
        original_query = "测试查询"
        quality_report = {
            'suggestions': ['唯一建议']
        }
        
        result = _build_retry_query(original_query, quality_report)
        
        assert '1. 唯一建议' in result

    def test_multiple_suggestions_numbering(self):
        """测试多个建议的编号."""
        original_query = "测试查询"
        quality_report = {
            'suggestions': ['建议A', '建议B', '建议C']
        }
        
        result = _build_retry_query(original_query, quality_report)
        
        assert '1. 建议A' in result
        assert '2. 建议B' in result
        assert '3. 建议C' in result


class TestExecuteQueryWithReflection:
    """执行带反思的查询测试."""

    @pytest.fixture
    def mock_agent(self):
        """创建模拟Agent."""
        agent = MagicMock()
        agent.invoke.return_value = {
            'messages': [{'role': 'assistant', 'content': '测试结果'}]
        }
        return agent

    @pytest.fixture
    def mock_quality_evaluator(self):
        """创建模拟质量评估器."""
        evaluator = MagicMock()
        evaluator.evaluate.return_value = {
            'should_retry': False,
            'suggestions': [],
            'reflection_rules': []
        }
        return evaluator

    @pytest.fixture
    def mock_settings(self):
        """创建模拟设置."""
        settings = MagicMock()
        settings.harness.max_iterations = 3
        return settings

    def test_successful_first_iteration(
        self, mock_agent, mock_quality_evaluator, mock_settings
    ):
        """测试第一次迭代就成功."""
        initial_files = {}
        thread_id = "test_thread"
        query = "测试查询"
        
        result = execute_query_with_reflection(
            mock_agent,
            query,
            initial_files,
            mock_quality_evaluator,
            mock_settings,
            thread_id
        )
        
        # 应该只调用一次invoke
        assert mock_agent.invoke.call_count == 1
        
        # 应该调用一次质量评估
        assert mock_quality_evaluator.evaluate.call_count == 1
        
        # 返回结果
        assert 'messages' in result

    def test_retry_then_success(
        self, mock_agent, mock_quality_evaluator, mock_settings
    ):
        """测试重试后成功."""
        # 第一次需要重试，第二次成功
        mock_quality_evaluator.evaluate.side_effect = [
            {
                'should_retry': True,
                'suggestions': ['改进建议'],
                'reflection_rules': []
            },
            {
                'should_retry': False,
                'suggestions': [],
                'reflection_rules': []
            }
        ]
        
        initial_files = {}
        thread_id = "test_thread"
        query = "测试查询"
        
        result = execute_query_with_reflection(
            mock_agent,
            query,
            initial_files,
            mock_quality_evaluator,
            mock_settings,
            thread_id
        )
        
        # 应该调用两次invoke
        assert mock_agent.invoke.call_count == 2
        
        # 应该调用两次质量评估
        assert mock_quality_evaluator.evaluate.call_count == 2

    def test_max_iterations_reached(
        self, mock_agent, mock_quality_evaluator, mock_settings
    ):
        """测试达到最大迭代次数."""
        # 一直需要重试
        mock_quality_evaluator.evaluate.return_value = {
            'should_retry': True,
            'suggestions': ['改进建议'],
            'reflection_rules': []
        }
        
        initial_files = {}
        thread_id = "test_thread"
        query = "测试查询"
        
        result = execute_query_with_reflection(
            mock_agent,
            query,
            initial_files,
            mock_quality_evaluator,
            mock_settings,
            thread_id
        )
        
        # 应该调用max_iterations次invoke
        assert mock_agent.invoke.call_count == mock_settings.harness.max_iterations

    def test_execution_error(self, mock_agent, mock_quality_evaluator, mock_settings):
        """测试执行错误."""
        mock_agent.invoke.side_effect = Exception("执行错误")
        
        initial_files = {}
        thread_id = "test_thread"
        query = "测试查询"
        
        result = execute_query_with_reflection(
            mock_agent,
            query,
            initial_files,
            mock_quality_evaluator,
            mock_settings,
            thread_id
        )
        
        # 应该返回错误信息
        assert 'error' in result
        assert result['status'] == 'failed'
        assert '执行错误' in result['error']
        assert result['iteration'] == 1

    def test_reflection_rules_loaded(
        self, mock_agent, mock_quality_evaluator, mock_settings
    ):
        """测试reflection规则加载."""
        mock_quality_evaluator.evaluate.return_value = {
            'should_retry': False,
            'suggestions': [],
            'reflection_rules': ['rule1', 'rule2']
        }
        
        initial_files = {}
        thread_id = "test_thread"
        query = "测试查询"
        
        with patch('src.agent.execution.agent_phases.logger') as mock_logger:
            result = execute_query_with_reflection(
                mock_agent,
                query,
                initial_files,
                mock_quality_evaluator,
                mock_settings,
                thread_id
            )
            
            # 验证执行了质量评估
            assert mock_quality_evaluator.evaluate.called
            # 验证返回了结果
            assert result is not None

    def test_suggestions_logged(
        self, mock_agent, mock_quality_evaluator, mock_settings
    ):
        """测试建议被记录到日志."""
        mock_quality_evaluator.evaluate.return_value = {
            'should_retry': False,
            'suggestions': ['建议1', '建议2'],
            'reflection_rules': []
        }
        
        initial_files = {}
        thread_id = "test_thread"
        query = "测试查询"
        
        with patch('src.agent.execution.agent_phases.logger') as mock_logger:
            result = execute_query_with_reflection(
                mock_agent,
                query,
                initial_files,
                mock_quality_evaluator,
                mock_settings,
                thread_id
            )
            
            # 验证Suggestions被记录
            assert any('Suggestions' in str(call) for call in mock_logger.info.call_args_list)

    def test_correct_invoke_parameters(
        self, mock_agent, mock_quality_evaluator, mock_settings
    ):
        """测试invoke调用参数正确."""
        initial_files = {'file1.txt': 'content'}
        thread_id = "test_thread"
        query = "测试查询"
        
        execute_query_with_reflection(
            mock_agent,
            query,
            initial_files,
            mock_quality_evaluator,
            mock_settings,
            thread_id
        )
        
        # 验证invoke调用参数
        call_args = mock_agent.invoke.call_args
        assert call_args is not None
        
        # 检查位置参数
        invoke_input = call_args[0][0]
        assert 'messages' in invoke_input
        assert 'files' in invoke_input
        assert invoke_input['files'] == initial_files
        
        # 检查config参数
        assert 'config' in call_args[1]
        assert call_args[1]['config']['configurable']['thread_id'] == thread_id
