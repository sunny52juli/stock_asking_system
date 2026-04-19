"""策略名称解析器 - 从配置文件查找匹配的策略."""

from __future__ import annotations

import re


from infrastructure.config.settings import get_settings
def find_strategy_name_from_config(query: str, screening_logic: dict) -> str:
    """从配置文件中查找匹配的策略名称。
    
    通过 query 或 screening_logic 中的 name 字段，在 settings.yaml 中查找对应的策略名。
    确保文件夹命名与配置文件中的策略名完全一致。
    
    Args:
        query: 用户查询字符串
        screening_logic: 筛选逻辑字典
        
    Returns:
        配置文件中的策略名称
        
    Raises:
        ValueError: 如果无法从配置中找到匹配的策略
    """
    
    settings = get_settings()
    
    # 遍历配置中的所有策略，查找匹配的
    for strategy_name, strategy_config in settings.strategies.items():
        # StrategyTemplateConfig 是 Pydantic 模型，使用属性访问
        config_query = strategy_config.query.strip() if strategy_config.query else ""
        
        # 方法1：精确匹配 query
        if query and query.strip() == config_query:
            return strategy_name
        
        # 方法2：模糊匹配 - query 包含策略名
        if query and strategy_name in query:
            return strategy_name
        
        # 方法3：检查 query 和 config_query 的相似度（关键词匹配）
        if query and config_query:
            query_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', query))
            config_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', config_query))
            
            # 如果有 50% 以上的关键词重叠，认为是同一个策略
            if query_keywords and config_keywords:
                overlap = len(query_keywords & config_keywords)
                total = len(query_keywords | config_keywords)
                if total > 0 and overlap / total >= 0.5:
                    return strategy_name
    
    # 如果没有找到匹配的策略，抛出异常
    raise ValueError(
        f"无法在配置文件中找到匹配的策略。\n"
        f"用户查询: {query}\n"
        f"screening_logic.name: {screening_logic.get('name', '')}\n"
        f"可用策略: {list(settings.strategies.keys())}"
    )
