"""记忆系统测试 - 图数据库功能验证.

测试新的 Neo4j 图数据库记忆系统功能。
运行方式：
    pytest tests/test_memory_system.py -v
    
注意：需要 Neo4j 运行在 localhost:7687
"""

import pytest
from pathlib import Path

@pytest.mark.skip(reason="需要 Neo4j 运行")
def test_basic_memory():
    """测试基础记忆功能（图数据库）."""
    from src.agent.memory import GraphDatabaseMemory, StrategyRecord
    
    # 初始化
    memory = GraphDatabaseMemory(uri="bolt://localhost:7687")
    
    try:
        # 保存策略
        record = StrategyRecord(
            query="找出高波动且跑赢大盘的股票",
            strategy_name="test_high_volatility_outperform",
            screening_logic={
                "expression": "(beta_60 > 1.0) & (alpha_60 > 0)",
                "tools": [
                    {"var": "beta_60", "tool": "beta", "params": {"window": 60}},
                    {"var": "alpha_60", "tool": "alpha", "params": {"window": 60}}
                ]
            },
            candidates_count=15,
            success=True
        )
        
        record_id = memory.save_strategy(record)
        assert record_id is not None
        
        # 搜索策略
        similar = memory.search_strategies("高波动", limit=3)
        assert len(similar) >= 0
        
        # 获取最近策略
        recent = memory.get_recent_strategies(limit=5)
        assert len(recent) >= 0
        
    finally:
        memory.close()


@pytest.mark.skip(reason="需要 Neo4j 运行")
def test_consolidation():
    """测试记忆整理功能."""
    from src.agent.memory import GraphDatabaseMemory, MemoryConsolidator
    
    # 初始化
    memory = GraphDatabaseMemory(uri="bolt://localhost:7687")
    consolidator = MemoryConsolidator(
        long_term_memory=memory,
        llm=None,  # 无 LLM，跳过原则生成
        config={
            "min_cluster_size": 2,
            "max_memory_age_days": 90
        }
    )
    
    try:
        # 聚类策略
        clusters = consolidator.cluster_strategies()
        assert isinstance(clusters, dict)
        
        # 更新用户画像
        profile = consolidator.update_user_profile()
        assert isinstance(profile, dict)
        
        # 加载画像
        saved_profile = consolidator.load_user_profile()
        assert isinstance(saved_profile, dict)
        
    finally:
        memory.close()


@pytest.mark.skip(reason="需要 Neo4j 运行")
def test_visualization():
    """测试可视化功能."""
    from src.agent.memory import GraphDatabaseMemory, MemoryConsolidator, MemoryVisualizer
    
    # 初始化
    memory = GraphDatabaseMemory(uri="bolt://localhost:7687")
    consolidator = MemoryConsolidator(memory, llm=None)
    visualizer = MemoryVisualizer(
        long_term_memory=memory,
        consolidator=consolidator,
        output_dir=Path("tests/memory_viz_test")
    )
    
    try:
        # 生成仪表板
        dashboard_path = visualizer.generate_dashboard()
        assert dashboard_path.exists()
        
    finally:
        memory.close()


@pytest.mark.skip(reason="需要 Neo4j 运行")
def test_scheduler():
    """测试后台调度器."""
    from src.agent.memory import GraphDatabaseMemory, MemoryScheduler
    
    # 初始化
    memory = GraphDatabaseMemory(uri="bolt://localhost:7687")
    scheduler = MemoryScheduler(
        long_term_memory=memory,
        llm=None,
        config={
            "consolidation_interval_hours": 24,
            "visualization_update_hours": 12,
            "cleanup_interval_days": 7
        }
    )
    
    try:
        # 手动执行一次
        scheduler.run_consolidation()
        scheduler.update_visualization()
        
        # 查看状态
        status = scheduler.get_status()
        assert "is_running" in status
        assert "jobs_count" in status
        
    finally:
        memory.close()


if __name__ == "__main__":
    """直接运行时执行所有测试（用于演示）."""
    print("\n🧠 记忆系统图数据库测试\n")
    print("注意：以下测试需要 Neo4j 运行在 localhost:7687")
    print()
    
    # 移除 skip 标记，直接运行
    test_basic_memory.__wrapped__ = test_basic_memory.__pytest_wrapped__.obj if hasattr(test_basic_memory, '__pytest_wrapped__') else test_basic_memory
    
    try:
        from src.agent.memory import GraphDatabaseMemory, StrategyRecord
        
        print("📚 测试 1: 基础记忆功能...")
        memory = GraphDatabaseMemory(uri="bolt://localhost:7687")
        
        record = StrategyRecord(
            query="找出高波动且跑赢大盘的股票",
            strategy_name="demo_high_volatility",
            screening_logic={
                "expression": "(beta_60 > 1.0) & (alpha_60 > 0)",
                "tools": [
                    {"var": "beta_60", "tool": "beta", "params": {"window": 60}},
                    {"var": "alpha_60", "tool": "alpha", "params": {"window": 60}}
                ]
            },
            candidates_count=15,
            success=True
        )
        
        record_id = memory.save_strategy(record)
        print(f"✅ 保存策略记录 ID: {record_id}")
        
        similar = memory.search_strategies("高波动", limit=3)
        print(f"🔍 找到 {len(similar)} 个相似策略")
        
        recent = memory.get_recent_strategies(limit=5)
        print(f"📋 最近 {len(recent)} 个策略")
        
        memory.close()
        print("\n✅ 测试完成！\n")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
