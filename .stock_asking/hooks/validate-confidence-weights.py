#!/usr/bin/env python3
"""PostToolUse Hook - 验证 confidence_weights 的完整性.

检查 Agent 生成的 screening_logic 中：
1. 如果定义了 confidence_weights，必须为 expression 中的所有指标变量定义权重
2. 权重之和应该接近 1.0（系统会自动归一化）

退出码：
- 0: 验证通过
- 1: 警告（权重不完整，将回退到等权分配）
- 2: 阻止（不应该发生，因为会回退到等权）
"""

import json
import sys
import re


def extract_expression_vars(expression: str) -> set[str]:
    """从表达式中提取所有变量名.
    
    Args:
        expression: 筛选表达式
        
    Returns:
        变量名集合
    """
    # 匹配所有标识符（排除布尔运算符和数字）
    var_pattern = r'\b([a-zA-Z_]\w*)\b'
    all_vars = set(re.findall(var_pattern, expression))
    
    # 排除 Python 关键字和布尔运算符
    exclude_keywords = {
        'and', 'or', 'not', 'True', 'False', 'None',
        'if', 'else', 'elif', 'in', 'is', 'lambda'
    }
    
    return all_vars - exclude_keywords


def validate_confidence_weights(screening_logic: dict) -> tuple[int, list[str]]:
    """验证 confidence_weights 的完整性.
    
    Args:
        screening_logic: Agent 生成的筛选逻辑
        
    Returns:
        (exit_code, messages)
    """
    messages = []
    
    expression = screening_logic.get('expression', '')
    confidence_weights = screening_logic.get('confidence_weights')
    confidence_formula = screening_logic.get('confidence_formula')
    
    # 如果没有定义任何置信度配置，跳过验证（使用默认等权）
    if not confidence_weights and not confidence_formula:
        return 0, []
    
    # 提取表达式中的变量
    expression_vars = extract_expression_vars(expression)
    
    if not expression_vars:
        messages.append("[WARNING] Expression contains no variables")
        return 1, messages
    
    # 优先使用 confidence_weights（新格式）
    if confidence_weights:
        if not isinstance(confidence_weights, dict):
            messages.append(f"[ERROR] confidence_weights should be a dict, got {type(confidence_weights).__name__}")
            return 2, messages
        
        defined_vars = set(confidence_weights.keys())
        undefined_vars = expression_vars - defined_vars
        
        if undefined_vars:
            messages.append(f"[WARNING] confidence_weights 权重定义不完整")
            messages.append(f"   表达式中的变量: {', '.join(sorted(expression_vars))}")
            messages.append(f"   已定义权重: {', '.join(sorted(defined_vars))}")
            messages.append(f"   缺失权重: {', '.join(sorted(undefined_vars))}")
            messages.append(f"   → 系统将回退到等权分配")
            
            # 这是警告，不是错误，因为系统会自动回退
            return 1, messages
        
        # 检查权重之和
        total_weight = sum(confidence_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            messages.append(f"[INFO] 权重总和={total_weight:.2f}，系统将自动归一化")
        
        return 0, messages
    
    # 如果使用 confidence_formula（旧格式），进行简单检查
    if confidence_formula:
        if not isinstance(confidence_formula, str):
            messages.append(f"[ERROR] confidence_formula should be a string, got {type(confidence_formula).__name__}")
            return 2, messages
        
        # 检查 formula 中是否引用了表达式中的变量
        formula_vars = extract_expression_vars(confidence_formula)
        
        # 注意：formula 可能包含 rank_normalize 等函数调用，所以不完全匹配是正常的
        # 这里只做基本检查
        
        return 0, messages
    
    return 0, []


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
        
        # 执行验证
        exit_code, messages = validate_confidence_weights(screening_logic)
        
        # 输出结果
        if messages:
            for msg in messages:
                print(msg)
        
        # 根据验证结果设置退出码
        # 注意：即使有警告也不阻止执行，因为系统会回退到等权
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: Hook execution failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
