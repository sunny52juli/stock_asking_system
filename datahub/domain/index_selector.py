"""指数选择器 - 根据股票代码自动选择合适的基准指数."""

from __future__ import annotations


# 指数代码映射规则 - 基于确定的交易所/板块分类
INDEX_MAPPING = {
    # 科创板 (688xxx) - 上海证券交易所科创板
    "688": "000688.SH",  # 科创50指数
    
    # 创业板 (300xxx, 301xxx) - 深圳证券交易所创业板
    "300": "399006.SZ",  # 创业板指
    "301": "399006.SZ",
    
    # 北交所 (8xxxxx, 4xxxxx, 9xxxxx) - 北京证券交易所
    "8": "899050.BJ",    # 北证50成份指数
    "4": "899050.BJ",
    "9": "899050.BJ",
    
    # 上海证券交易所主板 (600, 601, 603, 605)
    "600": "000001.SH",  # 上证综合指数
    "601": "000001.SH",
    "603": "000001.SH",
    "605": "000001.SH",
    
    # 深圳证券交易所主板 (000, 001, 002, 003)
    "000": "399001.SZ",  # 深证成份指数
    "001": "399001.SZ",
    "002": "399001.SZ",  # 原中小板已合并到主板
    "003": "399001.SZ",
}

# 默认指数（无法匹配时使用）
DEFAULT_INDEX = "000300.SH"  # 沪深300（全市场代表）


def get_index_code(ts_code: str) -> str:
    """根据股票代码获取对应的基准指数代码.
    
    Args:
        ts_code: 股票代码，如 '688981.SH', '300750.SZ'
        
    Returns:
        指数代码，如 '000688.SH' (科创50)
        
    Examples:
        >>> get_index_code('688981.SH')
        '000688.SH'  # 科创板 -> 科创50
        
        >>> get_index_code('300750.SZ')
        '399006.SZ'  # 创业板 -> 创业板指
        
        >>> get_index_code('600519.SH')
        '000300.SH'  # 主板 -> 沪深300
    """
    if not ts_code or len(ts_code) < 6:
        return DEFAULT_INDEX
    
    # 提取股票代码前缀（去掉 .SH/.SZ/.BJ 后缀）
    code_prefix = ts_code[:3]
    first_digit = ts_code[0]
    
    # 优先匹配3位前缀
    if code_prefix in INDEX_MAPPING:
        return INDEX_MAPPING[code_prefix]
    
    # 匹配1位前缀（北交所）
    if first_digit in INDEX_MAPPING:
        return INDEX_MAPPING[first_digit]
    
    # 默认返回沪深300
    return DEFAULT_INDEX


def get_index_name(index_code: str) -> str:
    """获取指数名称.
    
    Args:
        index_code: 指数代码
        
    Returns:
        指数名称
    """
    index_names = {
        # 交易所综合指数（确定性分类）
        "000001.SH": "上证指数",      # 上海证券交易所综合指数
        "399001.SZ": "深证成指",      # 深圳证券交易所成份指数
        "899050.BJ": "北证50",        # 北京证券交易所50成份指数
        
        # 板块指数
        "000688.SH": "科创50",        # 科创板50成份指数
        "399006.SZ": "创业板指",      # 创业板指数
        
        # 宽基指数（备选）
        "000300.SH": "沪深300",       # 沪深300指数（默认）
        "000016.SH": "上证50",        # 上证50指数
        "399330.SZ": "深证100",       # 深证100指数
        "000905.SH": "中证500",       # 中证500指数
        "000852.SH": "中证1000",      # 中证1000指数
        "399005.SZ": "中小板指",      # 中小企业板指数（历史）
    }
    return index_names.get(index_code, index_code)


if __name__ == "__main__":
    # 测试所有板块的股票代码映射
    test_codes = [
        # 科创板 - 上交所科创板
        ("688981.SH", "中芯国际"),
        ("688256.SH", "寒武纪"),
        
        # 创业板 - 深交所创业板
        ("300750.SZ", "宁德时代"),
        ("300059.SZ", "东方财富"),
        ("301234.SZ", "新股票示例"),
        
        # 上交所主板
        ("600519.SH", "贵州茅台"),
        ("601318.SH", "中国平安"),
        ("600036.SH", "招商银行"),
        ("603259.SH", "药明康德"),
        ("605117.SH", "德业股份"),
        
        # 深交所主板（含原中小板）
        ("000001.SZ", "平安银行"),
        ("000858.SZ", "五粮液"),
        ("000333.SZ", "美的集团"),
        ("002001.SZ", "新和成"),
        ("002415.SZ", "海康威视"),
        
        # 北交所
        ("832802.BJ", "贝特瑞"),
        ("835185.BJ", "利通电子"),
    ]
    
    print("=" * 80)
    print("指数映射规则 - 基于确定的交易所/板块分类")
    print("=" * 80)
    print(f"{'股票代码':<15} {'股票名称':<12} {'指数代码':<12} {'指数名称':<15} {'说明'}")
    print("-" * 80)
    
    for code, name in test_codes:
        index_code = get_index_code(code)
        index_name = get_index_name(index_code)
        
        # 添加说明
        if "688" in code:
            desc = "上交所-科创板"
        elif code.startswith(("300", "301")):
            desc = "深交所-创业板"
        elif code.startswith(("600", "601", "603", "605")):
            desc = "上交所-主板"
        elif code.startswith(("000", "001", "002", "003")):
            desc = "深交所-主板"
        elif code.startswith(("8", "4", "9")):
            desc = "北交所"
        else:
            desc = "未知"
        
        print(f"{code:<15} {name:<12} {index_code:<12} {index_name:<15} {desc}")
    
    print("=" * 80)
    print("\n✅ 映射规则说明：")
    print("   • 科创板 → 科创50指数 (000688.SH)")
    print("   • 创业板 → 创业板指 (399006.SZ)")
    print("   • 上交所主板 → 上证指数 (000001.SH)")
    print("   • 深交所主板 → 深证成指 (399001.SZ)")
    print("   • 北交所 → 北证50 (899050.BJ)")
    print("   • 其他 → 沪深300 (000300.SH) [默认]")
    print("=" * 80)
