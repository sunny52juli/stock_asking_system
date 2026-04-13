"""Agent模块测试 - config.py"""

import pytest
from pydantic import ValidationError

from src.agent.config import (
    AgentConfig,
    HookConfig,
    HookMatcherConfig,
    HooksConfig,
    AgentConfigModel,
)


class TestAgentConfig:
    """Agent配置测试."""

    def test_default_values(self):
        """测试默认值."""
        config = AgentConfig()
        
        assert config.mode == "single"
        assert config.enable_subagents is False

    def test_custom_values(self):
        """测试自定义值."""
        config = AgentConfig(mode="deep_thinking", enable_subagents=True)
        
        assert config.mode == "deep_thinking"
        assert config.enable_subagents is True

    def test_invalid_mode(self):
        """测试无效模式（pydantic不会阻止，但应该接受任何字符串）."""
        config = AgentConfig(mode="invalid_mode")
        assert config.mode == "invalid_mode"


class TestHookConfig:
    """Hook配置测试."""

    def test_required_fields(self):
        """测试必需字段."""
        hook = HookConfig(command="echo test")
        
        assert hook.type == "command"
        assert hook.command == "echo test"

    def test_custom_type(self):
        """测试自定义类型."""
        hook = HookConfig(type="script", command="python script.py")
        
        assert hook.type == "script"
        assert hook.command == "python script.py"

    def test_missing_command(self):
        """测试缺少command字段."""
        with pytest.raises(ValidationError):
            HookConfig()


class TestHookMatcherConfig:
    """Hook匹配器配置测试."""

    def test_default_values(self):
        """测试默认值."""
        matcher = HookMatcherConfig()
        
        assert matcher.matcher is None
        assert matcher.hooks == []

    def test_with_matcher(self):
        """测试带匹配器的配置."""
        hooks = [HookConfig(command="echo test")]
        matcher = HookMatcherConfig(matcher="test_tool", hooks=hooks)
        
        assert matcher.matcher == "test_tool"
        assert len(matcher.hooks) == 1

    def test_empty_hooks(self):
        """测试空hooks列表."""
        matcher = HookMatcherConfig(matcher="test_tool")
        assert matcher.hooks == []


class TestHooksConfig:
    """Hooks完整配置测试."""

    def test_default_values(self):
        """测试默认值."""
        hooks = HooksConfig()
        
        assert hooks.PreToolUse == []
        assert hooks.PostToolUse == []
        assert hooks.Stop == []

    def test_with_hooks(self):
        """测试带hooks的配置."""
        pre_hooks = [
            HookMatcherConfig(
                matcher="test_tool",
                hooks=[HookConfig(command="echo pre")]
            )
        ]
        
        hooks = HooksConfig(PreToolUse=pre_hooks)
        
        assert len(hooks.PreToolUse) == 1
        assert hooks.PostToolUse == []
        assert hooks.Stop == []


class TestAgentConfigModel:
    """Agent完整配置模型测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = AgentConfigModel()
        
        assert isinstance(config.agent, AgentConfig)
        assert config.agent.mode == "single"
        assert config.agent.enable_subagents is False

    def test_custom_agent_config(self):
        """测试自定义Agent配置."""
        config = AgentConfigModel(
            agent=AgentConfig(mode="deep_thinking", enable_subagents=True)
        )
        
        assert config.agent.mode == "deep_thinking"
        assert config.agent.enable_subagents is True

    def test_all_sections_present(self):
        """测试所有配置部分都存在."""
        config = AgentConfigModel()
        
        # 验证所有主要配置部分都存在
        assert hasattr(config, 'agent')
        assert hasattr(config, 'llm')
        assert hasattr(config, 'harness')
        assert hasattr(config, 'permissions')
        assert hasattr(config, 'hooks')
        assert hasattr(config, 'backtest')
        assert hasattr(config, 'reflection')
        assert hasattr(config, 'data')
        assert hasattr(config, 'output')
        assert hasattr(config, 'logging')
        assert hasattr(config, 'telemetry')

    def test_nested_config_modification(self):
        """测试嵌套配置修改."""
        config = AgentConfigModel()
        
        # 修改agent配置
        config.agent.mode = "deep_thinking"
        config.agent.enable_subagents = True
        
        assert config.agent.mode == "deep_thinking"
        assert config.agent.enable_subagents is True
        
        # 其他配置保持不变
        assert config.agent.mode != "single"

    def test_hooks_configuration(self):
        """测试hooks配置."""
        hooks_config = HooksConfig(
            PreToolUse=[
                HookMatcherConfig(
                    matcher="read_file",
                    hooks=[HookConfig(command="validate_file")]
                )
            ]
        )
        
        config = AgentConfigModel(hooks=hooks_config)
        
        assert len(config.hooks.PreToolUse) == 1
        assert config.hooks.PreToolUse[0].matcher == "read_file"
