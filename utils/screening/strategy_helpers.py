"""策略工具函数 - 提供策略模板和查询."""

from infrastructure.config.settings import load_settings


def get_strategy_templates() -> dict:
    """获取所有策略模板."""
    settings = load_settings()
    return settings.strategies


def get_user_queries() -> list[str]:
    """获取所有策略的查询列表."""
    templates = get_strategy_templates()
    
    if not templates:
        return []
    
    queries = [t.query for t in templates.values() if t.query]
    return queries


def get_strategy_config(name: str) -> dict | None:
    """获取指定策略的配置.
    
    Args:
        name: 策略名称
        
    Returns:
        策略配置字典，包含 query, strategy_num, observation_period_days
    """
    templates = get_strategy_templates()
    if name not in templates:
        return None
    
    template = templates[name]
    return {
        "query": template.query,
        "strategy_num": template.strategy_num,
        "observation_period_days": template.observation_period_days,
    }
