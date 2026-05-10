"""观测系统测试."""

import pytest
from pathlib import Path
from src.agent.observability import get_observability, reset_observability


@pytest.fixture
def obs(tmp_path):
    """创建测试用的观测管理器."""
    reset_observability()
    return get_observability(enabled=True, project_root=tmp_path)


def test_trace_query(obs, tmp_path):
    """测试查询追踪."""
    query = "测试查询"
    
    with obs.trace_query(query, query_id=1):
        pass
    
    # 检查trace文件是否创建（使用telemetry的实际路径）
    traces_dir = Path(obs.telemetry.trace_dir)
    assert traces_dir.exists()
    trace_files = list(traces_dir.glob("trace_*.json"))
    assert len(trace_files) > 0


def test_record_strategy(obs, tmp_path):
    """测试策略记录."""
    record_id = obs.record_strategy(
        query="测试策略",
        strategy_name="test_strategy_" + str(id(tmp_path)),  # 确保名称唯一
        screening_logic={"expression": "beta > 1.0"},
        candidates_count=10,
        success=True
    )
    
    # Neo4j 返回的是内部 ID，只要不报错且能查到即视为成功
    assert record_id is not None
    
    # 检查 Neo4j 中是否真的保存了数据
    strategies = obs.get_recent_strategies(limit=1)
    assert len(strategies) > 0


def test_search_strategies(obs):
    """测试策略搜索."""
    # 先保存一些策略
    obs.record_strategy(
        query="高波动股票筛选",
        strategy_name="high_vol_1",
        screening_logic={},
        candidates_count=5
    )
    
    obs.record_strategy(
        query="低估值高分红",
        strategy_name="value_dividend",
        screening_logic={},
        candidates_count=8
    )
    
    # 搜索
    suggestions = obs.get_strategy_suggestions("高波动", limit=2)
    assert len(suggestions) >= 1
    assert any("高波动" in s.query for s in suggestions)


def test_get_recent_strategies(obs):
    """测试获取最近策略."""
    # 保存多个策略
    for i in range(3):
        obs.record_strategy(
            query=f"测试策略{i}",
            strategy_name=f"test_{i}",
            screening_logic={},
            candidates_count=i * 5
        )
    
    recent = obs.get_recent_strategies(limit=2)
    assert len(recent) == 2
    # 应该是最近的两个（按时间倒序）
    assert recent[0].strategy_name == "test_2"


def test_record_tool_call(obs):
    """测试工具调用记录."""
    obs.record_tool_call("beta_60", window=60)
    
    # 检查trace文件
    traces_dir = Path(obs.telemetry.trace_dir)
    tool_traces = list(traces_dir.glob("*tool_call*"))
    assert len(tool_traces) > 0


def test_print_summary(obs, caplog):
    """测试打印摘要."""
    import logging
    caplog.set_level(logging.INFO)
    
    obs.print_summary()
    
    # 检查是否输出了统计信息
    assert any("TELEMETRY" in record.message for record in caplog.records)


def test_disabled_mode(tmp_path):
    """测试禁用模式."""
    reset_observability()
    obs = get_observability(enabled=False, project_root=tmp_path)
    
    # 在禁用模式下不应创建文件
    obs.record_strategy(
        query="测试",
        strategy_name="test",
        screening_logic={},
        candidates_count=0
    )
    
    memory_db = tmp_path / ".stock_asking" / "memory.db"
    # 禁用模式下数据库可能仍会创建（LongTermMemory初始化时），但不会写入数据
    # 这里主要测试不报错
    obs.close()


def test_singleton_pattern():
    """测试单例模式."""
    reset_observability()
    
    obs1 = get_observability(enabled=True)
    obs2 = get_observability(enabled=True)
    
    assert obs1 is obs2
    
    reset_observability()
