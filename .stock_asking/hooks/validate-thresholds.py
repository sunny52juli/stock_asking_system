#!/usr/bin/env python3
"""PostToolUse Hook - 验证 run_screening 工具的阈值合理性.

基于 .stock_asking/rules/tool-value-ranges.md 的规则，
检查 Agent 生成的 screening_logic 中的阈值是否在合理范围内。

退出码：
- 0: 验证通过
- 1: 警告（阈值可疑但允许）
- 2: 阻止（阈值明显错误）
"""

import json
import sys
import re
from pathlib import Path


def parse_tool_value_ranges(md_file: Path) -> dict[str, dict]:
    """从 tool-value-ranges.md 解析工具范围配置.
    
    Args:
        md_file: markdown 文件路径
        
    Returns:
        工具范围字典 {tool_name: {'min': ..., 'max': ..., 'description': ...}}
    """
    if not md_file.exists():
        print(f"WARNING: {md_file} not found, using empty rules", file=sys.stderr)
        return {}
    
    content = md_file.read_text(encoding='utf-8')
    ranges = {}
    
    # 匹配表格行：| `tool_name` | range | example | description |
    table_pattern = r'\|\s*`([^`]+)`\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+?)\s*\|'
    
    for match in re.finditer(table_pattern, content):
        tool_name = match.group(1).strip()
        range_str = match.group(2).strip()
        description = match.group(4).strip()
        
        # 解析范围字符串
        min_val, max_val = None, None
        
        # 处理 "0-1" 或 "-1 到 1" 格式
        range_match = re.search(r'(-?\d+(?:\.\d+)?)\s*[-到]\s*(-?\d+(?:\.\d+)?)', range_str)
        if range_match:
            min_val = float(range_match.group(1))
            max_val = float(range_match.group(2))
        # 处理 "可正可负" 或 "同输入列" 等文本描述
        elif '可正可负' in range_str or '无固定范围' in range_str or '同输入列' in range_str:
            min_val, max_val = None, None
        # 处理 "通常 0-2" 格式
        else:
            numbers = re.findall(r'-?\d+(?:\.\d+)?', range_str)
            if len(numbers) >= 2:
                min_val = float(numbers[0])
                max_val = float(numbers[1])
            elif len(numbers) == 1:
                min_val = float(numbers[0])
        
        ranges[tool_name] = {
            'min': min_val,
            'max': max_val,
            'description': description
        }
    
    return ranges


def validate_thresholds(screening_logic: dict, tool_ranges: dict) -> tuple[int, list[str], list[str]]:
    """验证筛选逻辑中的阈值是否合理.
    
    Args:
        screening_logic: Agent 生成的筛选逻辑
        tool_ranges: 从 tool-value-ranges.md 解析的工具范围
        
    Returns:
        (exit_code, warnings, errors)
    """
    warnings = []
    errors = []
    
    expression = screening_logic.get('expression', '')
    tools = screening_logic.get('tools', [])
    
    # 构建变量名到工具名的映射
    var_to_tool = {}
    for tool in tools:
        if isinstance(tool, dict):
            var_to_tool[tool.get('var', '')] = tool.get('tool', '')
    
    # 提取 expression 中的所有比较表达式
    comparison_pattern = r'([a-zA-Z_]\w*)\s*([<>]=?)\s*(-?[0-9]+\.?[0-9]*)'
    comparisons = re.findall(comparison_pattern, expression)
    
    for var_name, operator, threshold_str in comparisons:
        try:
            threshold = float(threshold_str)
        except ValueError:
            continue
        
        # 获取该变量对应的工具
        tool_name = var_to_tool.get(var_name, '')
        
        # 如果没有找到工具定义，跳过（可能是基础字段）
        if not tool_name:
            continue
        
        # 查找工具的范围配置（支持前缀匹配）
        range_config = None
        for key, config in tool_ranges.items():
            if var_name.startswith(key) or tool_name == key:
                range_config = config
                break
        
        if not range_config:
            continue
        
        # 检查阈值是否在合理范围内
        min_val = range_config['min']
        max_val = range_config['max']
        description = range_config['description']
        
        # 检查下限
        if min_val is not None and threshold < min_val:
            errors.append(
                f"[ERROR] Variable '{var_name}' ({tool_name}) threshold {threshold} below minimum {min_val}\n"
                f"   Description: {description}"
            )
        
        # 检查上限
        if max_val is not None and threshold > max_val:
            errors.append(
                f"[ERROR] Variable '{var_name}' ({tool_name}) threshold {threshold} exceeds maximum {max_val}\n"
                f"   Description: {description}"
            )
        
        # 警告：接近边界值
        if max_val is not None and threshold > max_val * 0.9:
            warnings.append(
                f"[WARNING] Variable '{var_name}' threshold {threshold} close to upper limit {max_val}\n"
                f"   Description: {description}"
            )
    
    # 确定退出码
    if errors:
        return 2, warnings, errors
    elif warnings:
        return 1, warnings, []
    else:
        return 0, [], []


def main():
    """主函数."""
    try:
        # 从 stdin 读取 payload
        payload = json.load(sys.stdin)
        
        # 提取工具输出
        output_str = payload.get('output', '')
        
        # 尝试解析为 JSON
        try:
            screening_logic = json.loads(output_str)
        except json.JSONDecodeError:
            # 如果不是 JSON，可能是错误消息，跳过验证
            print("INFO: Output is not JSON, skipping validation")
            sys.exit(0)
        
        # 只验证 run_screening 工具的输出
        if not isinstance(screening_logic, dict):
            sys.exit(0)
        
        # 动态加载 tool-value-ranges.md
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent.parent
        md_file = project_root / '.stock_asking' / 'rules' / 'tool-value-ranges.md'
        tool_ranges = parse_tool_value_ranges(md_file)
        
        if not tool_ranges:
            print("WARNING: No tool ranges loaded, skipping validation", file=sys.stderr)
            sys.exit(0)
        
        # 执行验证
        exit_code, warnings, errors = validate_thresholds(screening_logic, tool_ranges)
        
        # 输出结果
        if warnings:
            print("WARNINGS:")
            for warning in warnings:
                print(f"  {warning}")
        
        if errors:
            print("ERRORS:")
            for error in errors:
                print(f"  {error}")
            print("\n[TIP] Refer to .stock_asking/rules/tool-value-ranges.md to adjust thresholds")
        
        # 根据验证结果设置退出码
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"ERROR: Hook execution failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
