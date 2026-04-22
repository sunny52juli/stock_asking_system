"""测试 validate-thresholds Hook 的动态解析功能."""

import json
import subprocess
from pathlib import Path


def test_hook_parses_md_dynamically():
    """测试 Hook 能够从 tool-value-ranges.md 动态解析规则."""
    # 准备测试数据
    test_data = {
        "output": json.dumps({
            "expression": "outperform_rate > 0.5",
            "tools": [
                {"var": "outperform_rate", "tool": "outperform_rate"}
            ]
        })
    }
    
    # 执行 Hook（使用项目根目录）
    project_root = Path(__file__).parent.parent.parent.parent.parent
    result = subprocess.run(
        ["python", ".stock_asking/hooks/validate-thresholds.py"],
        input=json.dumps(test_data),
        capture_output=True,
        text=True,
        cwd=project_root
    )
    
    # 验证结果
    assert result.returncode == 0, f"Hook should pass for valid threshold. stderr: {result.stderr}"
    assert "ERRORS" not in result.stdout


def test_hook_detects_invalid_threshold():
    """测试 Hook 能够检测到超出范围的阈值."""
    test_data = {
        "output": json.dumps({
            "expression": "outperform_rate > 1.5",
            "tools": [
                {"var": "outperform_rate", "tool": "outperform_rate"}
            ]
        })
    }
    
    project_root = Path(__file__).parent.parent.parent.parent.parent
    result = subprocess.run(
        ["python", ".stock_asking/hooks/validate-thresholds.py"],
        input=json.dumps(test_data),
        capture_output=True,
        text=True,
        cwd=project_root
    )
    
    # 应该检测到错误
    assert result.returncode == 2, f"Hook should block invalid threshold. stdout: {result.stdout}"
    assert "ERRORS" in result.stdout
    assert "exceeds maximum" in result.stdout


def test_hook_validates_rsi_range():
    """测试 Hook 能够验证 RSI 范围."""
    test_data = {
        "output": json.dumps({
            "expression": "rsi > 150",
            "tools": [
                {"var": "rsi", "tool": "rsi"}
            ]
        })
    }
    
    project_root = Path(__file__).parent.parent.parent.parent.parent
    result = subprocess.run(
        ["python", ".stock_asking/hooks/validate-thresholds.py"],
        input=json.dumps(test_data),
        capture_output=True,
        text=True,
        cwd=project_root
    )
    
    assert result.returncode == 2
    assert "RSI" in result.stdout or "rsi" in result.stdout or "exceeds maximum" in result.stdout


def test_hook_allows_valid_multi_conditions():
    """测试 Hook 允许多个有效条件."""
    test_data = {
        "output": json.dumps({
            "expression": "beta < 1.2 and volatility < 0.3",
            "tools": [
                {"var": "beta", "tool": "beta"},
                {"var": "volatility", "tool": "volatility"}
            ]
        })
    }
    
    project_root = Path(__file__).parent.parent.parent.parent.parent
    result = subprocess.run(
        ["python", ".stock_asking/hooks/validate-thresholds.py"],
        input=json.dumps(test_data),
        capture_output=True,
        text=True,
        cwd=project_root
    )
    
    assert result.returncode == 0


def test_hook_skips_non_json_output():
    """测试 Hook 能够跳过非 JSON 输出."""
    test_data = {
        "output": "This is not JSON"
    }
    
    project_root = Path(__file__).parent.parent.parent.parent.parent
    result = subprocess.run(
        ["python", ".stock_asking/hooks/validate-thresholds.py"],
        input=json.dumps(test_data),
        capture_output=True,
        text=True,
        cwd=project_root
    )
    
    # 应该跳过验证，返回 0
    assert result.returncode == 0
    assert "INFO" in result.stdout or result.returncode == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
