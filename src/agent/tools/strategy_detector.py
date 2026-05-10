"""策略描述检测器 - 使用 LLM 判断用户输入是否为有效的选股策略描述."""

from __future__ import annotations

import json
from typing import Any

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def is_strategy_description(user_input: str) -> bool:
    """判断用户输入是否为有效的选股策略描述.
    
    Args:
        user_input: 用户输入的文本
        
    Returns:
        True 如果是策略描述，False 如果是命令或无效输入
    """
    # 快速过滤：明显的命令或空输入
    if not user_input or len(user_input.strip()) < 2:
        return False
    
    input_lower = user_input.lower().strip()
    
    # 常见命令列表
    commands = [
        'help', 'h', '?', '帮助',
        'quit', 'exit', 'q', '退出',
        'edit', 'eidt', 'edti', 'edi', '编辑',
        'save', '保存',
        'skip', '跳过',
        'y', 'yes', '是',
        'n', 'no', '否',
    ]
    
    if input_lower in commands:
        return False
    
    # [OK] 检查是否包含策略相关的关键词（快速路径）
    strategy_keywords = [
        '股票', '选股', '筛选', '策略', 'beta', 'alpha', 'pe', 'pb',
        '估值', '分红', '波动', '跑赢', '大盘', '技术', '形态',
        '高估', '低估', '成长', '价值', '动量', '反转',
        '大于', '小于', '高于', '低于', '>', '<',
        '找出', '找到', '搜索', '查询',
        '涨幅', '跌幅', '成交量', '换手率',
    ]
    
    has_keyword = any(keyword in input_lower for keyword in strategy_keywords)
    
    # 如果包含策略关键词，直接判定为策略描述（避免调用 LLM）
    if has_keyword:
        return True
    
    # 对于不确定的情况，使用 LLM 进行判断
    return _llm_judge_strategy(user_input)


def _llm_judge_strategy(user_input: str) -> bool:
    """使用 LLM 判断输入是否为策略描述.
    
    Args:
        user_input: 用户输入
        
    Returns:
        True 如果是策略描述
    """
    try:
        from src.agent.core.agent_factory import create_agent
        
        agent = create_agent(agent_type="screening")
        
        system_prompt = """你是一个策略描述分类器。判断用户输入是否为有效的股票筛选策略描述。

判断标准：
- 策略描述：包含选股条件、指标要求、市场观点等（如"找出高波动的股票"）
- 非策略：命令、问候、无关内容、纯数字等

只返回 JSON 格式：{"is_strategy": true/false, "confidence": 0-1}"""

        response = agent.run(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=50
        )
        
        # 解析响应
        content = response.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        
        try:
            result = json.loads(content)
            is_strategy = result.get("is_strategy", False)
            confidence = result.get("confidence", 0)
            
            logger.debug(f"LLM 判断结果: is_strategy={is_strategy}, confidence={confidence}")
            
            # 置信度阈值
            return is_strategy and confidence > 0.7
            
        except json.JSONDecodeError:
            # 如果无法解析 JSON，保守处理：假设不是策略
            logger.warning(f"无法解析 LLM 响应: {content}")
            return False
            
    except Exception as e:
        logger.error(f"LLM 判断失败: {e}")
        # [OK] 修复：出错时采用保守策略，假设为非策略
        return False


def validate_and_suggest(user_input: str) -> dict[str, Any]:
    """验证用户输入并提供建议.
    
    Args:
        user_input: 用户输入
        
    Returns:
        包含验证结果的字典：
        {
            "is_valid": bool,  # 是否为有效策略描述
            "suggestion": str,  # 建议信息
            "type": str  # 类型：strategy/command/invalid
        }
    """
    if is_strategy_description(user_input):
        return {
            "is_valid": True,
            "suggestion": "",
            "type": "strategy"
        }
    
    # 检查是否为已知命令
    input_lower = user_input.lower().strip()
    known_commands = {
        'help': '查看帮助菜单',
        'quit': '退出系统',
        'edit': '编辑上次策略',
    }
    
    for cmd, desc in known_commands.items():
        if input_lower.startswith(cmd):
            return {
                "is_valid": False,
                "suggestion": f"这是命令：{desc}",
                "type": "command"
            }
    
    # 既不是策略也不是命令，可能是无效输入
    return {
        "is_valid": False,
        "suggestion": "⚠️ 这似乎不是有效的选股策略描述。\n\n💡 请尝试这样描述：\n   • '找出高波动且跑赢大盘的股票'\n   • '低估值高分红的蓝筹股'\n   • 'beta > 1.2 且 PE < 20 的成长股'\n\n📌 或者输入命令：help (帮助) | edit (编辑) | quit (退出)",
        "type": "invalid"
    }
