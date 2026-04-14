"""
数据字段配置 - 定义系统支持的所有股票数据字段

设计原则：
1. 核心映射只定义一次（中文→英文）
2. 自动生成双向映射（支持中英文混用）
3. 提供字段验证、标准化、类型判断等功能
"""

from typing import ClassVar


class DataFields:
    """数据字段定义和验证"""

    # ==================== 核心字段映射（仅中文→英文） ====================
    # 这些是唯一的真实数据源，其他所有映射都从这里自动生成

    # 基础价格字段
    _PRICE_MAP: ClassVar[dict[str, str]] = {
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "收盘价": "close",
    }

    # 成交量字段
    _VOL_MAP: ClassVar[dict[str, str]] = {
        "成交量": "vol",
        "成交额": "amount",
    }

    # 基础信息字段
    _INFO_MAP: ClassVar[dict[str, str]] = {
        "date": "date",
        "code": "code",
        "ts_code": "ts_code",
        "name": "name",
    }

    # 衍生字段（系统自动计算）
    _DERIVED_MAP: ClassVar[dict[str, str]] = {
        "vwap": "vwap",  # 成交量加权平均价
        "pct_change": "pct_change",  # 日收益率
        "ret": "ret",  # 收益率
        "ret1": "ret1",  # 次日收益率
        "volatility": "volatility",  # 波动率
    }

    # 估值指标字段
    _VALUATION_MAP: ClassVar[dict[str, str]] = {
        "换手率": "turnover_rate",
        "自由流通换手率": "turnover_rate_f",
        "量比": "volume_ratio",
        "市盈率": "pe",
        "市盈率TTM": "pe_ttm",
        "市净率": "pb",
        "市销率": "ps",
        "市销率TTM": "ps_ttm",
        "股息率": "dv_ratio",
        "股息率TTM": "dv_ttm",
        "总股本": "total_share",
        "流通股本": "float_share",
        "自由流通股本": "free_share",
        "总市值": "total_mv",
        "流通市值": "circ_mv",
    }

    # 行业/市场字段
    _CATEGORY_MAP: ClassVar[dict[str, str]] = {
        "industry": "industry",
        "market": "market",
    }

    # ==================== 自动生成的完整映射 ====================

    @staticmethod
    def _build_bidirectional_mapping(source_map: dict[str, str]) -> dict[str, str]:
        """
        从单向映射生成双向映射（支持中英文混用）

        Args:
            source_map: 原始映射（如 {"开盘价": "open"}）

        Returns:
            双向映射（如 {"开盘价": "open", "open": "open"}）
        """
        result = {}
        for cn, en in source_map.items():
            result[cn] = en  # 中文→英文
            result[en] = en  # 英文→英文（自映射，用于标准化）
        return result

    # 双向映射字典（自动生成）
    PRICE_FIELDS: ClassVar[dict[str, str]] = _build_bidirectional_mapping(_PRICE_MAP)
    VOL_FIELDS: ClassVar[dict[str, str]] = _build_bidirectional_mapping(_VOL_MAP)
    VALUATION_FIELDS: ClassVar[dict[str, str]] = _build_bidirectional_mapping(_VALUATION_MAP)
    INFO_FIELDS: ClassVar[dict[str, str]] = _INFO_MAP  # 已经是英文，不需要双向
    DERIVED_FIELDS: ClassVar[dict[str, str]] = _DERIVED_MAP  # 已经是英文
    CATEGORY_FIELDS: ClassVar[dict[str, str]] = _CATEGORY_MAP  # 已经是英文

    # 合并所有字段
    ALL_FIELDS: ClassVar[dict[str, str]] = {
        **PRICE_FIELDS,
        **VOL_FIELDS,
        **VALUATION_FIELDS,
        **INFO_FIELDS,
        **DERIVED_FIELDS,
        **CATEGORY_FIELDS,
    }

    # 必需字段（数据验证时检查）
    REQUIRED_FIELDS: ClassVar[list[str]] = ["date", "code", "open", "high", "low", "close", "vol"]
    
    # 数值字段（需要数值类型）
    NUMERIC_FIELDS: ClassVar[list[str]] = [
        # 价格字段
        "open", "high", "low", "close",
        # 成交量字段
        "vol", "amount",
        # 估值指标字段
        "turnover_rate", "turnover_rate_f", "volume_ratio",
        "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        "dv_ratio", "dv_ttm",
        "total_share", "float_share", "free_share",
        "total_mv", "circ_mv",
        # 衍生字段
        "vwap", "pct_change", "ret", "volatility",
    ]

    @classmethod
    def is_valid_field(cls, field_name: str) -> bool:
        """
        检查字段是否有效

        Args:
            field_name: 字段名（中文或英文）

        Returns:
            是否为有效字段
        """
        return field_name in cls.ALL_FIELDS

    @classmethod
    def normalize_field(cls, field_name: str) -> str:
        """
        标准化字段名（中文转英文）

        Args:
            field_name: 字段名（中文或英文）

        Returns:
            标准化后的英文字段名
        """
        return cls.ALL_FIELDS.get(field_name, field_name)

    @classmethod
    def get_field_type(cls, field_name: str) -> str:
        """
        获取字段类型
    
        Args:
            field_name: 字段名
    
        Returns:
            字段类型：'price', 'vol', 'valuation', 'info', 'derived', 'category', 'unknown'
        """
        normalized = cls.normalize_field(field_name)
    
        if normalized in cls._PRICE_MAP.values():
            return "price"
        elif normalized in cls._VOL_MAP.values():
            return "vol"
        elif normalized in cls._VALUATION_MAP.values():
            return "valuation"
        elif normalized in cls._INFO_MAP.values():
            return "info"
        elif normalized in cls._DERIVED_MAP.values():
            return "derived"
        elif normalized in cls._CATEGORY_MAP.values():
            return "category"
        else:
            return "unknown"

    @classmethod
    def get_all_field_names(cls, include_chinese: bool = True) -> list[str]:
        """
        获取所有字段名列表

        Args:
            include_chinese: 是否包含中文字段名

        Returns:
            字段名列表
        """
        if include_chinese:
            return list(cls.ALL_FIELDS.keys())
        else:
            return list(set(cls.ALL_FIELDS.values()))

    @classmethod
    def get_field_description(cls, field_name: str) -> str:
        """
        获取字段描述
    
        Args:
            field_name: 字段名
    
        Returns:
            字段描述
        """
        descriptions = {
            # 基础价格字段
            "open": "开盘价",
            "high": "最高价",
            "low": "最低价",
            "close": "收盘价",
            # 成交量字段
            "vol": "成交量（手）",
            "amount": "成交金额（元）",
            # 基础信息字段
            "date": "交易日期",
            "code": "股票代码",
            "ts_code": "股票代码（Tushare 格式）",
            "name": "股票名称",
            # 估值指标字段
            "turnover_rate": "换手率（%）",
            "turnover_rate_f": "换手率（自由流通股）",
            "volume_ratio": "量比",
            "pe": "市盈率（总市值/净利润）",
            "pe_ttm": "市盈率（TTM）",
            "pb": "市净率",
            "ps": "市销率",
            "ps_ttm": "市销率（TTM）",
            "dv_ratio": "股息率（%）",
            "dv_ttm": "股息率（TTM）（%）",
            "total_share": "总股本（万股）",
            "float_share": "流通股本（万股）",
            "free_share": "自由流通股本（万股）",
            "total_mv": "总市值（万元）",
            "circ_mv": "流通市值（万元）",
            # 衍生字段
            "vwap": "成交量加权平均价",
            "pct_change": "日收益率",
            "ret": "收益率",
            "ret1": "次日收益率",
            "volatility": "波动率",
            # 行业/市场字段
            "industry": "所属行业",
            "market": "所属市场",
        }
    
        normalized = cls.normalize_field(field_name)
        return descriptions.get(normalized, "未知字段")

    @classmethod
    def validate_fields_in_expression(cls, expression: str) -> dict[str, list[str]]:
        """
        验证表达式中使用的字段是否有效

        Args:
            expression: 因子表达式

        Returns:
            验证结果字典 {'valid': [...], 'invalid': [...]}
        """
        import re

        # 提取表达式中的中文字段（如"收盘价"）
        chinese_fields = re.findall(r"[\u4e00-\u9fa5]+", expression)

        # 提取表达式中的英文字段（如"close"）
        # 排除常见的函数名和关键字
        exclude_words = {
            "abs",
            "log",
            "sqrt",
            "max",
            "min",
            "sum",
            "mean",
            "std",
            "rolling",
            "pct",
            "lag",
            "rank",
            "zscore",
            "clip",
            "and",
            "or",
            "not",
            "if",
            "else",
            "for",
            "in",
        }
        english_fields = [
            word for word in re.findall(r"\b[a-z_]+\b", expression) if word not in exclude_words
        ]

        all_fields = chinese_fields + english_fields

        valid_fields = []
        invalid_fields = []

        for field in all_fields:
            if cls.is_valid_field(field):
                valid_fields.append(field)
            else:
                invalid_fields.append(field)

        return {"valid": list(set(valid_fields)), "invalid": list(set(invalid_fields))}

    @classmethod
    def get_field_examples(cls) -> dict[str, str]:
        """
        获取字段使用示例

        Returns:
            字段使用示例字典
        """
        return {
            "价格字段": "收盘价, 开盘价, 最高价, 最低价",
            "成交量字段": "成交量, 成交额",
            "基础表达式": "(最高价 - 最低价) / (收盘价 + 0.0001)",
            "工具调用": 'rolling_mean("收盘价", 20)',
            "复合表达式": "(收盘价 - 开盘价) * 成交量",
        }


# 常见错误字段映射（帮助用户纠正）
COMMON_FIELD_ERRORS: dict[str, str] = {
    "换手率": '成交量 / rolling_mean("成交量", 60)',
    "市值": "不支持，请使用价格和成交量相关字段",
    "涨停价": "不支持，请使用价格字段计算",
    "跌停价": "不支持，请使用价格字段计算",
    "昨收": 'lag("收盘价", 1)',
    "涨跌幅": 'pct_change("收盘价", 1)',
    "振幅": '(最高价 - 最低价) / lag("收盘价", 1)',
    "量比": '成交量 / rolling_mean("成交量", 5)',
}


def get_field_suggestion(invalid_field: str) -> str:
    """
    为无效字段提供建议

    Args:
        invalid_field: 无效的字段名

    Returns:
        建议信息
    """
    if invalid_field in COMMON_FIELD_ERRORS:
        return f"建议使用: {COMMON_FIELD_ERRORS[invalid_field]}"
    else:
        return f"该字段不存在，请使用标准字段：{', '.join(DataFields.PRICE_FIELDS.keys())}"


# 导出便捷访问
AVAILABLE_FIELDS = DataFields.get_all_field_names(include_chinese=True)
REQUIRED_FIELDS = DataFields.REQUIRED_FIELDS
NUMERIC_FIELDS = DataFields.NUMERIC_FIELDS


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("数据字段配置测试")
    print("=" * 60)

    # 1. 显示所有可用字段
    print("\n1. 所有可用字段:")
    print(f"   中文字段: {list(DataFields.PRICE_FIELDS.keys())[:4]}")
    print(f"   英文字段: {list(DataFields.PRICE_FIELDS.values())[:4]}")
    print(f"   总计: {len(DataFields.get_all_field_names(include_chinese=False))} 个标准字段")

    # 2. 字段验证
    print("\n2. 字段验证:")
    test_fields = ["收盘价", "close", "换手率", "turnover"]
    for field in test_fields:
        is_valid = DataFields.is_valid_field(field)
        print(f"   {field}: {'✅ 有效' if is_valid else '❌ 无效'}")
        if not is_valid:
            print(f"      {get_field_suggestion(field)}")

    # 3. 字段标准化
    print("\n3. 字段标准化:")
    test_fields = ["收盘价", "成交量", "open"]
    for field in test_fields:
        normalized = DataFields.normalize_field(field)
        print(f"   {field} → {normalized}")

    # 4. 表达式验证
    print("\n4. 表达式验证:")
    test_expressions = [
        "(收盘价 - 开盘价) / (收盘价 + 0.0001)",
        "换手率 * 成交量",
        "rolling_mean(close, 20)",
    ]
    for expr in test_expressions:
        result = DataFields.validate_fields_in_expression(expr)
        print(f"   表达式: {expr}")
        print(f"   有效字段: {result['valid']}")
        print(f"   无效字段: {result['invalid']}")

    # 5. 字段示例
    print("\n5. 字段使用示例:")
    examples = DataFields.get_field_examples()
    for category, example in examples.items():
        print(f"   {category}: {example}")

    print("\n" + "=" * 60)

# ==================== 因子回测字段映射 ====================
# 用于因子表达式解析的字段映射（支持中英文）
# 这是唯一的数据源,其他模块应该从这里导入

FIELD_MAPPING = {
    # 基础价格字段
    "开盘价": "open",
    "最高价": "high",
    "最低价": "low",
    "收盘价": "close",
    "前收盘": "pre_close",
    "涨跌额": "change",
    "涨跌幅": "pct_chg",
    # 成交量字段
    "成交量": "vol",
    "成交额": "amount",
    # 基础信息字段
    "股票代码": "ts_code",
    "股票名称": "name",
    "地域": "area",
    "行业": "industry",
    "市场": "market",
    "上市日期": "list_date",
    # 估值指标字段
    "换手率": "turnover_rate",
    "自由流通换手率": "turnover_rate_f",
    "量比": "volume_ratio",
    "市盈率": "pe",
    "市盈率TTM": "pe_ttm",
    "市净率": "pb",
    "市销率": "ps",
    "市销率TTM": "ps_ttm",
    "股息率": "dv_ratio",
    "股息率TTM": "dv_ttm",
    "总股本": "total_share",
    "流通股本": "float_share",
    "自由流通股本": "free_share",
    "总市值": "total_mv",
    "流通市值": "circ_mv",
    # 复权因子
    "复权因子": "adj_factor",
    # 资金流向字段
    "小单买入量": "buy_sm_vol",
    "小单买入额": "buy_sm_amount",
    "小单卖出量": "sell_sm_vol",
    "小单卖出额": "sell_sm_amount",
    "中单买入量": "buy_md_vol",
    "中单买入额": "buy_md_amount",
    "中单卖出量": "sell_md_vol",
    "中单卖出额": "sell_md_amount",
    "大单买入量": "buy_lg_vol",
    "大单买入额": "buy_lg_amount",
    "大单卖出量": "sell_lg_vol",
    "大单卖出额": "sell_lg_amount",
    "特大单买入量": "buy_elg_vol",
    "特大单买入额": "buy_elg_amount",
    "特大单卖出量": "sell_elg_vol",
    "特大单卖出额": "sell_elg_amount",
    "净流入量": "net_mf_vol",
    "净流入额": "net_mf_amount",
    # 融资融券字段
    "融资余额": "rzye",
    "融券余额": "rqye",
    "融资买入额": "rzmre",
    "融券余量": "rqyl",
    "融资偿还额": "rzche",
    "融券偿还量": "rqchl",
    "融券卖出量": "rqmcl",
    "融资融券余额": "rzrqye",
    # 衍生字段
    "均价": "vwap",
    "收益率": "ret",
    "次日收益率": "ret1",
    "波动率": "volatility",
}

# 函数映射（用于因子表达式解析）
FUNCTION_MAPPING = {
    "均值": "mean",
    "标准差": "std",
    "最大值": "max",
    "最小值": "min",
    "中位数": "median",
    "移动平均": "rolling_mean",
    "排名": "rank",
    "对数": "log",
    "绝对值": "abs",
    "滞后": "shift",
}

# ==================== 字段文档说明 ====================
# 为每个字段提供详细说明（用于自动生成文档）

FIELD_DESCRIPTIONS = {
    # 基础价格字段
    "open": "当日开盘价",
    "high": "当日最高价",
    "low": "当日最低价",
    "close": "当日收盘价",
    "pre_close": "前一交易日收盘价",
    "change": "涨跌额（元）",
    "pct_chg": "涨跌幅（%）",
    # 成交量字段
    "vol": "当日成交量（手）",
    "amount": "当日成交金额（千元）",
    # 基础信息字段
    "ts_code": "股票代码（如：000001.SZ）",
    "name": "股票名称",
    "area": "所属地域",
    "industry": "所属行业",
    "market": "所属市场（主板/创业板/科创板等）",
    "list_date": "上市日期",
    # 估值指标字段
    "turnover_rate": "换手率（%）",
    "turnover_rate_f": "换手率（自由流通股）",
    "volume_ratio": "量比",
    "pe": "市盈率（总市值/净利润，亏损的PE为空）",
    "pe_ttm": "市盈率（TTM，滚动12个月）",
    "pb": "市净率（总市值/净资产）",
    "ps": "市销率",
    "ps_ttm": "市销率（TTM）",
    "dv_ratio": "股息率（%）",
    "dv_ttm": "股息率（TTM）（%）",
    "total_share": "总股本（万股）",
    "float_share": "流通股本（万股）",
    "free_share": "自由流通股本（万股）",
    "total_mv": "总市值（万元）",
    "circ_mv": "流通市值（万元）",
    # 复权因子
    "adj_factor": "复权因子（用于计算前复权和后复权价格）",
    # 资金流向字段
    "buy_sm_vol": "小单买入量（手）",
    "buy_sm_amount": "小单买入金额（万元）",
    "sell_sm_vol": "小单卖出量（手）",
    "sell_sm_amount": "小单卖出金额（万元）",
    "buy_md_vol": "中单买入量（手）",
    "buy_md_amount": "中单买入金额（万元）",
    "sell_md_vol": "中单卖出量（手）",
    "sell_md_amount": "中单卖出金额（万元）",
    "buy_lg_vol": "大单买入量（手）",
    "buy_lg_amount": "大单买入金额（万元）",
    "sell_lg_vol": "大单卖出量（手）",
    "sell_lg_amount": "大单卖出金额（万元）",
    "buy_elg_vol": "特大单买入量（手）",
    "buy_elg_amount": "特大单买入金额（万元）",
    "sell_elg_vol": "特大单卖出量（手）",
    "sell_elg_amount": "特大单卖出金额（万元）",
    "net_mf_vol": "净流入量（手）",
    "net_mf_amount": "净流入额（万元）",
    # 融资融券字段
    "rzye": "融资余额（元）",
    "rqye": "融券余额（元）",
    "rzmre": "融资买入额（元）",
    "rqyl": "融券余量（股）",
    "rzche": "融资偿还额（元）",
    "rqchl": "融券偿还量（股）",
    "rqmcl": "融券卖出量（股）",
    "rzrqye": "融资融券余额（元）",
    # 衍生字段
    "vwap": "成交量加权平均价 = 成交额 / 成交量",
    "ret": "收益率（同pct_change）",
    "ret1": "次日收益率（用于回测）",
    "volatility": "波动率",
}

# ==================== 文档生成工具 ====================


def generate_field_markdown():
    """
    从 FIELD_MAPPING 自动生成 Markdown 格式的字段文档
    用于更新 SKILL.md 中的字段列表部分
    """
    # 按类别组织字段
    categories = {
        "基础价格字段": ["open", "high", "low", "close", "pre_close", "change", "pct_chg"],
        "成交量字段": ["vol", "amount"],
        "基础信息字段": ["ts_code", "name", "area", "industry", "market", "list_date"],
        "估值指标字段（每日指标）": [
            "turnover_rate",
            "turnover_rate_f",
            "volume_ratio",
            "pe",
            "pe_ttm",
            "pb",
            "ps",
            "ps_ttm",
            "dv_ratio",
            "dv_ttm",
            "total_share",
            "float_share",
            "free_share",
            "total_mv",
            "circ_mv",
        ],
        "复权因子字段": ["adj_factor"],
        "资金流向字段（个股资金流）": [
            "buy_sm_vol",
            "buy_sm_amount",
            "sell_sm_vol",
            "sell_sm_amount",
            "buy_md_vol",
            "buy_md_amount",
            "sell_md_vol",
            "sell_md_amount",
            "buy_lg_vol",
            "buy_lg_amount",
            "sell_lg_vol",
            "sell_lg_amount",
            "buy_elg_vol",
            "buy_elg_amount",
            "sell_elg_vol",
            "sell_elg_amount",
            "net_mf_vol",
            "net_mf_amount",
        ],
        "融资融券字段": ["rzye", "rqye", "rzmre", "rqyl", "rzche", "rqchl", "rqmcl", "rzrqye"],
        "衍生字段（系统自动计算）": ["vwap", "ret", "ret1", "volatility"],
    }

    # 生成 Markdown
    markdown = []
    markdown.append("## ⚠️ 可用数据字段（重要约束）\n")
    markdown.append("### 标准字段（必须使用以下字段，不得编造）\n")
    markdown.append("系统提供以下标准化的股票数据字段，**所有因子构建必须且只能使用这些字段**：\n")

    for category, fields in categories.items():
        markdown.append(f"\n#### {category}")
        for field in fields:
            # 查找中文名称
            chinese_names = [cn for cn, en in FIELD_MAPPING.items() if en == field]
            chinese_part = " / ".join([f"`{cn}`" for cn in chinese_names]) if chinese_names else ""

            # 获取描述
            description = FIELD_DESCRIPTIONS.get(field, "")

            # 格式化输出
            if chinese_part:
                markdown.append(f"- {chinese_part} / `{field}` - {description}")
            else:
                markdown.append(f"- `{field}` - {description}")

    return "\n".join(markdown)


def print_field_summary():
    """打印字段统计摘要"""
    print("=" * 80)
    print("字段映射配置摘要")
    print("=" * 80)
    print(f"\n✅ 总字段数量: {len(set(FIELD_MAPPING.values()))}")
    print(f"✅ 中文别名数量: {len(FIELD_MAPPING)}")
    print(f"✅ 函数映射数量: {len(FUNCTION_MAPPING)}")

    # 按类别统计
    categories = {
        "基础价格": ["open", "high", "low", "close", "pre_close", "change", "pct_chg"],
        "成交量": ["vol", "amount"],
        "基础信息": ["ts_code", "name", "area", "industry", "market", "list_date"],
        "估值指标": [
            "turnover_rate",
            "turnover_rate_f",
            "volume_ratio",
            "pe",
            "pe_ttm",
            "pb",
            "ps",
            "ps_ttm",
            "dv_ratio",
            "dv_ttm",
            "total_share",
            "float_share",
            "free_share",
            "total_mv",
            "circ_mv",
        ],
        "复权因子": ["adj_factor"],
        "资金流向": [
            "buy_sm_vol",
            "buy_sm_amount",
            "sell_sm_vol",
            "sell_sm_amount",
            "buy_md_vol",
            "buy_md_amount",
            "sell_md_vol",
            "sell_md_amount",
            "buy_lg_vol",
            "buy_lg_amount",
            "sell_lg_vol",
            "sell_lg_amount",
            "buy_elg_vol",
            "buy_elg_amount",
            "sell_elg_vol",
            "sell_elg_amount",
            "net_mf_vol",
            "net_mf_amount",
        ],
        "融资融券": ["rzye", "rqye", "rzmre", "rqyl", "rzche", "rqchl", "rqmcl", "rzrqye"],
        "衍生字段": ["vwap", "ret", "ret1", "volatility"],
    }

    print("\n📊 字段分类统计:")
    for category, fields in categories.items():
        print(f"  - {category}: {len(fields)} 个字段")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # 打印摘要
    print_field_summary()

    # 生成 Markdown 文档
    print("\n\n📝 生成的 Markdown 文档:\n")
    print(generate_field_markdown())

    print("\n\n💡 使用说明:")
    print("1. 将上述 Markdown 内容复制到 SKILL.md 的字段部分")
    print("2. 或者在代码中调用 generate_field_markdown() 自动更新")
    print("3. 这样可以保证 SKILL.md 和代码配置始终一致")
