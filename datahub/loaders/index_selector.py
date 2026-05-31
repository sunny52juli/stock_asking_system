"""指数选择器 - 根据股票代码自动选择合适的基准指数."""

from __future__ import annotations


class IndexSelector:
    """指数选择器 - 根据股票代码自动选择合适的基准指数.
    
    基于确定的交易所/板块分类规则进行映射。
    """
    
    # 指数代码映射规则
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
    
    # 指数名称映射
    INDEX_NAMES = {
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
    
    @classmethod
    def get_index_code(cls, ts_code: str) -> str:
        """根据股票代码获取对应的基准指数代码.
        
        Args:
            ts_code: 股票代码，如 '688981.SH', '300750.SZ'
            
        Returns:
            指数代码，如 '000688.SH' (科创50)
            
        Examples:
            >>> IndexSelector.get_index_code('688981.SH')
            '000688.SH'  # 科创板 -> 科创50
            
            >>> IndexSelector.get_index_code('300750.SZ')
            '399006.SZ'  # 创业板 -> 创业板指
            
            >>> IndexSelector.get_index_code('600519.SH')
            '000300.SH'  # 主板 -> 沪深300
        """
        if not ts_code or len(ts_code) < 6:
            return cls.DEFAULT_INDEX
        
        # 提取股票代码前缀（去掉 .SH/.SZ/.BJ 后缀）
        code_prefix = ts_code[:3]
        first_digit = ts_code[0]
        
        # 优先匹配3位前缀
        if code_prefix in cls.INDEX_MAPPING:
            return cls.INDEX_MAPPING[code_prefix]
        
        # 匹配1位前缀（北交所）
        if first_digit in cls.INDEX_MAPPING:
            return cls.INDEX_MAPPING[first_digit]
        
        # 默认返回沪深300
        return cls.DEFAULT_INDEX
    
    @classmethod
    def get_index_name(cls, index_code: str) -> str:
        """获取指数名称.
        
        Args:
            index_code: 指数代码
            
        Returns:
            指数名称
        """
        return cls.INDEX_NAMES.get(index_code, index_code)
    
    @classmethod
    def get_index_info(cls, ts_code: str) -> dict[str, str]:
        """获取股票的指数信息.
        
        Args:
            ts_code: 股票代码
            
        Returns:
            包含指数代码和名称的字典
        """
        index_code = cls.get_index_code(ts_code)
        index_name = cls.get_index_name(index_code)
        return {
            "ts_code": ts_code,
            "index_code": index_code,
            "index_name": index_name,
        }


# 便捷函数（保持向后兼容）
def get_index_code(ts_code: str) -> str:
    """根据股票代码获取对应的基准指数代码（便捷函数）."""
    return IndexSelector.get_index_code(ts_code)


def get_index_name(index_code: str) -> str:
    """获取指数名称（便捷函数）."""
    return IndexSelector.get_index_name(index_code)
