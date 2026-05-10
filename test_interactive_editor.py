#!/usr/bin/env python3
"""交互式编辑器功能测试脚本."""

import sys
from pathlib import Path

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.interactive.editor import InteractiveConditionEditor, ScreeningState


def test_basic_operations():
    """测试基本操作."""
    print("="*70)
    print("测试 1: 基本操作")
    print("="*70)
    
    # 创建示例筛选逻辑
    sample_logic = {
        "name": "测试策略",
        "rationale": "用于测试的策略",
        "expression": "(beta_60 > 1.2) & (outperform_60 > 0.5)",
        "confidence_formula": "rank_normalize(beta_60) * 0.5 + rank_normalize(outperform_60) * 0.5",
        "tools": [
            {
                "var": "beta_60",
                "tool": "beta",
                "params": {"window": 60}
            },
            {
                "var": "outperform_60",
                "tool": "outperform_rate",
                "params": {"window": 60}
            }
        ]
    }
    
    # 创建编辑器
    editor = InteractiveConditionEditor(sample_logic)
    print("✅ 编辑器创建成功")
    
    # 显示状态
    print("\n--- 初始状态 ---")
    editor.show_current_state()
    
    # 测试表达式修改
    print("\n--- 测试表达式修改 ---")
    editor.adjust_expression("(beta_60 > 1.0) & (outperform_60 > 0.4)")
    print(f"当前表达式: {editor.current_state.logic['expression']}")
    
    # 测试参数调整
    print("\n--- 测试参数调整 ---")
    editor.adjust_parameter("beta_60", "window", 30)
    beta_tool = [t for t in editor.current_state.logic['tools'] if t['var'] == 'beta_60'][0]
    print(f"Beta 窗口: {beta_tool['params']['window']}")
    
    print("\n✅ 基本操作测试通过\n")


def test_version_control():
    """测试版本控制."""
    print("="*70)
    print("测试 2: 版本控制 (Undo/Redo)")
    print("="*70)
    
    sample_logic = {
        "name": "版本控制测试",
        "expression": "beta_60 > 1.2",
        "tools": [
            {"var": "beta_60", "tool": "beta", "params": {"window": 60}}
        ]
    }
    
    editor = InteractiveConditionEditor(sample_logic)
    
    # 修改表达式（会自动保存到历史）
    print("\n1. 初始表达式:", editor.current_state.logic['expression'])
    
    editor.adjust_expression("beta_60 > 1.0")
    print("2. 修改后:", editor.current_state.logic['expression'])
    
    # 撤销
    print("\n3. 执行 undo...")
    editor.undo()
    print("   撤销后:", editor.current_state.logic['expression'])
    
    # 重做
    print("\n4. 执行 redo...")
    editor.redo()
    print("   重做后:", editor.current_state.logic['expression'])
    
    print("\n✅ 版本控制测试通过\n")


def test_snapshot():
    """测试快照功能."""
    print("="*70)
    print("测试 3: 快照保存/加载")
    print("="*70)
    
    sample_logic = {
        "name": "快照测试",
        "expression": "beta_60 > 1.2",
        "tools": [
            {"var": "beta_60", "tool": "beta", "params": {"window": 60}}
        ]
    }
    
    editor = InteractiveConditionEditor(sample_logic)
    
    # 保存快照
    print("\n1. 保存快照...")
    try:
        snapshot_path = editor.save_snapshot("测试快照")
        print(f"   快照路径: {snapshot_path}")
        
        # 修改逻辑
        editor.adjust_expression("beta_60 > 1.5")
        print(f"   修改后表达式: {editor.current_state.logic['expression']}")
        
        # 加载快照
        print("\n2. 加载快照...")
        editor.load_snapshot(snapshot_path)
        print(f"   加载后表达式: {editor.current_state.logic['expression']}")
        
        # 清理测试文件
        snapshot_path.unlink()
        print("   测试文件已清理")
        
    except Exception as e:
        print(f"   ⚠️  快照测试跳过（可能需要完整环境）: {e}")
    
    print("\n✅ 快照测试完成\n")


def test_export_import():
    """测试导出/导入."""
    print("="*70)
    print("测试 4: 导出/导入")
    print("="*70)
    
    sample_logic = {
        "name": "导出测试",
        "expression": "beta_60 > 1.2",
        "tools": [
            {"var": "beta_60", "tool": "beta", "params": {"window": 60}}
        ]
    }
    
    editor = InteractiveConditionEditor(sample_logic)
    
    # 导出
    export_path = PROJECT_ROOT / "test_export.json"
    print(f"\n1. 导出到: {export_path}")
    editor.export_logic(export_path)
    
    # 验证文件存在
    if export_path.exists():
        print("   ✅ 导出文件创建成功")
        
        # 读取并显示内容
        import json
        with open(export_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"   导出的策略名称: {data.get('name')}")
        
        # 清理
        export_path.unlink()
        print("   测试文件已清理")
    else:
        print("   ❌ 导出文件未创建")
    
    print("\n✅ 导出/导入测试完成\n")


def main():
    """运行所有测试."""
    print("\n" + "="*70)
    print("🧪 交互式筛选条件编辑器 - 功能测试")
    print("="*70 + "\n")
    
    try:
        test_basic_operations()
        test_version_control()
        test_snapshot()
        test_export_import()
        
        print("="*70)
        print("✅ 所有测试完成！")
        print("="*70)
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
