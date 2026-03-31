"""
表达式工具模块
提供表达式解析、变量推断、命名空间构建等功能
用于支持因子表达式的智能计算
"""

import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# 定义辅助函数（避免循环导入）
def _get_groupby_key(data: pd.DataFrame, key: str):
    """
    获取分组键，适配双索引结构

    支持三种数据格式：
    1. 双索引 (trade_date, ts_code) - 多股票时间序列
    2. 单索引 ts_code - 单日期多股票（预筛选阶段）
    3. 单索引 trade_date - 单股票时间序列（批量筛选阶段）

    Args:
        data: 数据DataFrame（可能是双索引）
        key: 分组键名称（'ts_code' 或 'trade_date'）

    Returns:
        分组键（Series或Index level），如果是单股票/单日期数据且无法分组则返回None
    """
    if isinstance(data.index, pd.MultiIndex):
        # 双索引情况，从索引中获取
        if key in data.index.names:
            return data.index.get_level_values(key)
        else:
            raise ValueError(f"索引中不存在 {key}")
    else:
        # 单索引情况
        # 1. 先检查索引名称是否匹配
        if data.index.name == key:
            return data.index
        # 2. 再检查列中是否存在
        elif key in data.columns:
            return data[key]
        else:
            # 3. 单股票/单日期数据，无法按该key分组
            # 返回None，让调用方决定如何处理
            return None

# 添加config目录到路径
config_path = Path(__file__).parent.parent.parent / "prompt"
sys.path.insert(0, str(config_path))

try:
    from data_fields import DataFields, get_field_suggestion
except ImportError:
    # 如果导入失败，使用默认配置
    class DataFields:
        FIELD_MAP = {
            '开盘价': 'open',
            '最高价': 'high',
            '最低价': 'low',
            '收盘价': 'close',
            '成交量': 'vol',  # 修复：使用正确的字段名 vol
            '成交额': 'amount'
        }

        @classmethod
        def is_valid_field(cls, field_name: str) -> bool:
            return field_name in cls.FIELD_MAP or field_name in cls.FIELD_MAP.values()

        @classmethod
        def normalize_field(cls, field_name: str) -> str:
            return cls.FIELD_MAP.get(field_name, field_name)

        @classmethod
        def validate_fields_in_expression(cls, expression: str) -> dict[str, list[str]]:
            return {'valid': [], 'invalid': []}

    def get_field_suggestion(field: str) -> str:
        return "请使用标准字段"


class ExpressionParser:
    """表达式解析器 - 处理中文字段映射和变量推断"""

    # 使用DataFields的字段映射
    FIELD_MAP = DataFields.FIELD_MAP if hasattr(DataFields, 'FIELD_MAP') else {
        '开盘价': 'open',
        '最高价': 'high',
        '最低价': 'low',
        '收盘价': 'close',
        '成交量': 'vol',  # 修复：使用正确的字段名 vol
        '成交额': 'amount'
    }

    @classmethod
    def validate_expression_fields(cls, expr: str) -> dict[str, Any]:
        """
        验证表达式中使用的字段是否有效

        Args:
            expr: 表达式字符串

        Returns:
            验证结果字典 {'valid': bool, 'invalid_fields': [...], 'suggestions': {...}}
        """
        result = DataFields.validate_fields_in_expression(expr)

        validation = {
            'valid': len(result['invalid']) == 0,
            'invalid_fields': result['invalid'],
            'valid_fields': result['valid'],
            'suggestions': {}
        }

        # 为无效字段提供建议
        for field in result['invalid']:
            validation['suggestions'][field] = get_field_suggestion(field)

        return validation

    @classmethod
    def parse_expression(cls, expr: str) -> str:
        """
        解析表达式，替换中文字段名和中文变量名

        处理两类中文：
        1. 基础字段：开盘价 -> open
        2. 中文变量：20日low -> low_20d, 20日平均vol -> vol_avg_20d

        Args:
            expr: 原始表达式

        Returns:
            解析后的表达式
        """
        parsed = expr

        # 1. 替换基础字段
        for cn, en in cls.FIELD_MAP.items():
            parsed = parsed.replace(cn, en)

        # 2. 处理中文变量名
        # 模式1: N日字段名 -> 字段名_Nd (如: 20日low -> low_20d)
        pattern1 = r'(\d+)日(open|high|low|close|vol|amount)'
        parsed = re.sub(pattern1, r'\2_\1d', parsed)

        # 模式2: N日平均字段名 -> 字段名_avg_Nd (如: 20日平均vol -> vol_avg_20d)
        pattern2 = r'(\d+)日平均(open|high|low|close|vol|amount)'
        parsed = re.sub(pattern2, r'\2_avg_\1d', parsed)

        # 模式3: N日最高字段名 -> 字段名_max_Nd (如: 20日最高价 -> high_max_20d)
        pattern3 = r'(\d+)日最高(open|high|low|close|vol|amount)'
        parsed = re.sub(pattern3, r'\2_max_\1d', parsed)

        # 模式4: N日最低字段名 -> 字段名_min_Nd (如: 20日最低价 -> low_min_20d)
        pattern4 = r'(\d+)日最低(open|high|low|close|vol|amount)'
        parsed = re.sub(pattern4, r'\2_min_\1d', parsed)

        return parsed

    @classmethod
    def infer_variable(cls, var_name: str, data: pd.DataFrame) -> pd.Series | None:
        """
        根据变量名智能推断并计算变量值

        支持的模式：
        - MA{n}: n日移动平均（如 MA5, MA20）
        - EMA{n}: n日指数移动平均（如 EMA12）
        - STD{n}: n日标准差（如 STD20）
        - RSI{n}: n日RSI（如 RSI14）
        - MOM{n}: n日动量（如 MOM5）
        - VOL{n}: n日成交量均值（如 VOL20）
        - {field}_{n}d: n日字段值（如 low_20d -> 20日最低价的滚动最小值）
        - {field}_avg_{n}d: n日字段平均值（如 vol_avg_20d -> 20日平均成交量）
        - {field}_max_{n}d: n日字段最大值（如 high_max_20d -> 20日最高价）
        - {field}_min_{n}d: n日字段最小值（如 low_min_20d -> 20日最低价）

        Args:
            var_name: 变量名
            data: 数据DataFrame

        Returns:
            计算后的 Series，如果无法推断则返回 None
        """
        # ⚠️ 第一优先级：检查是否是数据中的列（直接使用，不推断）
        # 这样可以确保使用 SKILL.md 中定义的标准字段
        if var_name in data.columns:
            return data[var_name]

        # ⚠️ 第二优先级：尝试推断衍生变量（仅用于 SKILL.md 中定义的复合变量）
        # 模式1: {field}_{n}d - n日字段值（滚动最小值/最大值）
        field_nd_match = re.match(r'(open|high|low|close|vol|amount)_(\d+)d', var_name, re.IGNORECASE)
        if field_nd_match:
            field = field_nd_match.group(1).lower()
            window = int(field_nd_match.group(2))

            # 根据字段类型选择合适的聚合方法
            if field in ['low']:
                return data.groupby('ts_code')[field].transform(lambda x: x.rolling(window).min())
            elif field in ['high']:
                return data.groupby('ts_code')[field].transform(lambda x: x.rolling(window).max())
            else:
                return data.groupby('ts_code')[field].transform(lambda x: x.rolling(window).mean())

        # 模式2: {field}_avg_{n}d - n日字段平均值
        field_avg_match = re.match(r'(open|high|low|close|vol|amount)_avg_(\d+)d', var_name, re.IGNORECASE)
        if field_avg_match:
            field = field_avg_match.group(1).lower()
            window = int(field_avg_match.group(2))
            return data.groupby('ts_code')[field].transform(lambda x: x.rolling(window).mean())

        # 模式3: {field}_max_{n}d - n日字段最大值
        field_max_match = re.match(r'(open|high|low|close|vol|amount)_max_(\d+)d', var_name, re.IGNORECASE)
        if field_max_match:
            field = field_max_match.group(1).lower()
            window = int(field_max_match.group(2))
            return data.groupby('ts_code')[field].transform(lambda x: x.rolling(window).max())

        # 模式4: {field}_min_{n}d - n日字段最小值
        field_min_match = re.match(r'(open|high|low|close|vol|amount)_min_(\d+)d', var_name, re.IGNORECASE)
        if field_min_match:
            field = field_min_match.group(1).lower()
            window = int(field_min_match.group(2))
            return data.groupby('ts_code')[field].transform(lambda x: x.rolling(window).min())

        # MA{n}: 移动平均
        ma_match = re.match(r'MA(\d+)', var_name, re.IGNORECASE)
        if ma_match:
            window = int(ma_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).mean())

        # ma_{n} 或 ma{n}: 移动平均（支持两种格式）
        ma_underscore_match = re.match(r'ma_(\d+)', var_name, re.IGNORECASE)
        if ma_underscore_match:
            window = int(ma_underscore_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).mean())

        # ema_{n} 或 ema{n}: 指数移动平均
        ema_underscore_match = re.match(r'ema_(\d+)', var_name, re.IGNORECASE)
        if ema_underscore_match:
            span = int(ema_underscore_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.ewm(span=span).mean())

        # std_{n} 或 std{n}: 标准差
        std_underscore_match = re.match(r'std_(\d+)', var_name, re.IGNORECASE)
        if std_underscore_match:
            window = int(std_underscore_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).std())

        # rsi_{n} 或 rsi{n}: RSI 指标
        rsi_underscore_match = re.match(r'rsi_(\d+)', var_name, re.IGNORECASE)
        if rsi_underscore_match:
            window = int(rsi_underscore_match.group(1))

            def calc_rsi(x):
                delta = x.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
                rs = gain / (loss + 1e-8)
                return 100 - (100 / (1 + rs))

            return data.groupby('ts_code')['close'].transform(calc_rsi)

        # mom_{n} 或 mom{n}: 动量
        mom_underscore_match = re.match(r'mom_(\d+)', var_name, re.IGNORECASE)
        if mom_underscore_match:
            periods = int(mom_underscore_match.group(1))
            return data.groupby('ts_code')['close'].pct_change(periods)

        # EMA{n}: 指数移动平均
        ema_match = re.match(r'EMA(\d+)', var_name, re.IGNORECASE)
        if ema_match:
            span = int(ema_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.ewm(span=span).mean())

        # STD{n}: 标准差
        std_match = re.match(r'STD(\d+)', var_name, re.IGNORECASE)
        if std_match:
            window = int(std_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).std())

        # RSI{n}: RSI指标
        rsi_match = re.match(r'RSI(\d+)', var_name, re.IGNORECASE)
        if rsi_match:
            window = int(rsi_match.group(1))

            def calc_rsi(x):
                delta = x.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
                rs = gain / (loss + 1e-8)
                return 100 - (100 / (1 + rs))

            return data.groupby('ts_code')['close'].transform(calc_rsi)

        # MOM{n}: 动量（n日收益率）
        mom_match = re.match(r'MOM(\d+)', var_name, re.IGNORECASE)
        if mom_match:
            periods = int(mom_match.group(1))
            return data.groupby('ts_code')['close'].pct_change(periods)

        # VOL{n}: 成交量均值
        vol_match = re.match(r'VOL(\d+)', var_name, re.IGNORECASE)
        if vol_match:
            window = int(vol_match.group(1))
            return data.groupby('ts_code')['vol'].transform(lambda x: x.rolling(window).mean())

        # 检查是否是数据中的列（优先检查，包括 vol_ratio）
        if var_name in data.columns:
            return data[var_name]

        # volume_ratio / vol_ratio: 成交量比率（当日成交量/过去 N 日平均成交量）
        # 支持的模式：volume_ratio, vol_ratio, volume_ratio_20, vol_ratio_10 等
        # 注意：如果数据中没有 vol_ratio 列，则自动计算
        vol_ratio_match = re.match(r'(?:volume|vol)_ratio(?:_(\d+))?', var_name, re.IGNORECASE)
        if vol_ratio_match:
            window = int(vol_ratio_match.group(1)) if vol_ratio_match.group(1) else 20  # 默认 20 日
            vol_ma = data.groupby('ts_code')['vol'].transform(lambda x: x.rolling(window).mean())
            return data['vol'] / vol_ma

        # SKEW{n}: 偏度
        skew_match = re.match(r'SKEW(\d+)', var_name, re.IGNORECASE)
        if skew_match:
            window = int(skew_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).skew())

        # KURT{n}: 峰度
        kurt_match = re.match(r'KURT(\d+)', var_name, re.IGNORECASE)
        if kurt_match:
            window = int(kurt_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).kurt())

        # MAX{n}: 滚动最大值
        max_match = re.match(r'MAX(\d+)', var_name, re.IGNORECASE)
        if max_match:
            window = int(max_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).max())

        # MIN{n}: 滚动最小值
        min_match = re.match(r'MIN(\d+)', var_name, re.IGNORECASE)
        if min_match:
            window = int(min_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).min())

        # RANK{n}: 时间序列排名
        rank_match = re.match(r'RANK(\d+)', var_name, re.IGNORECASE)
        if rank_match:
            window = int(rank_match.group(1))
            return data.groupby('ts_code')['close'].transform(lambda x: x.rolling(window).rank(pct=True))

        # 无法推断
        return None


class NamespaceBuilder:
    """命名空间构建器 - 为表达式评估提供完整的变量和函数环境"""

    @staticmethod
    def build_namespace(data: pd.DataFrame, computed_vars: dict[str, Any] = None) -> dict[str, Any]:
        """
        构建表达式的命名空间

        Args:
            data: 数据DataFrame
            computed_vars: 已计算的变量字典

        Returns:
            包含所有需要的变量和函数的命名空间字典
        """
        if computed_vars is None:
            computed_vars = {}

        # 辅助函数：智能分组操作
        # 当数据是单股票时间序列（无ts_code分组键）时，直接操作Series
        # 当数据是多股票数据（有ts_code分组键）时，按ts_code分组后操作
        def _grouped_transform(values, operation):
            """按ts_code分组执行transform操作，单股票数据则直接操作"""
            ts_code_key = _get_groupby_key(data, 'ts_code')
            if ts_code_key is None:
                # 单股票数据，直接操作
                return operation(values)
            else:
                return values.groupby(ts_code_key).transform(operation)

        def _grouped_pct_change(values, periods=1):
            """按ts_code分组计算百分比变化，单股票数据则直接计算"""
            ts_code_key = _get_groupby_key(data, 'ts_code')
            if ts_code_key is None:
                return values.pct_change(periods)
            else:
                return values.groupby(ts_code_key).pct_change(periods)

        def _grouped_shift(values, periods=1):
            """按ts_code分组执行shift操作，单股票数据则直接操作"""
            ts_code_key = _get_groupby_key(data, 'ts_code')
            if ts_code_key is None:
                return values.shift(periods)
            else:
                return values.groupby(ts_code_key).shift(periods)

        def _grouped_rolling_corr(x, y, window):
            """按ts_code分组计算滚动相关系数，单股票数据则直接计算"""
            ts_code_key = _get_groupby_key(data, 'ts_code')
            if ts_code_key is None:
                return x.rolling(window).corr(y)
            else:
                return x.groupby(ts_code_key).rolling(window).corr(y.groupby(ts_code_key))

        def _cross_section_transform(values, operation):
            """按trade_date分组执行截面操作，单日期数据则直接操作"""
            trade_date_key = _get_groupby_key(data, 'trade_date')
            if trade_date_key is None:
                return operation(values)
            else:
                return values.groupby(trade_date_key).transform(operation)

        def _cross_section_rank(values):
            """按trade_date分组排名，单日期数据则直接排名"""
            trade_date_key = _get_groupby_key(data, 'trade_date')
            if trade_date_key is None:
                return values.rank(pct=True)
            else:
                return values.groupby(trade_date_key).rank(pct=True)

        # 定义数学函数
        def log_transform(x):
            """对数变换，处理负值和零值"""
            return np.log(np.abs(x) + 1) * np.sign(x)

        def abs_value(x):
            """绝对值函数"""
            return np.abs(x)

        def sqrt_transform(x):
            """平方根变换，处理负值"""
            return np.sqrt(np.abs(x)) * np.sign(x)

        def rank_transform(x):
            """排名变换（横截面）"""
            if isinstance(x, pd.Series):
                return x.rank(pct=True)
            return x

        def zscore_transform(x):
            """标准化变换（时间序列）"""
            if isinstance(x, pd.Series):
                return (x - x.mean()) / (x.std() + 1e-8)
            return x

        def zscore_normalize(x):
            """Z-score标准化（截面）- 按日期分组标准化"""
            if isinstance(x, pd.Series):
                return _cross_section_transform(x, lambda g: (g - g.mean()) / (g.std() + 1e-8))
            return x

        def rank_normalize(x):
            """排名标准化（截面）- 按日期分组排名"""
            if isinstance(x, pd.Series):
                return _cross_section_rank(x)
            return x

        # 定义滚动窗口函数
        def rolling_mean(values, window=5):
            """滚动平均函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).mean())
            return values

        def rolling_std(values, window=5):
            """滚动标准差函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).std())
            return values

        def rolling_max(values, window=5):
            """滚动最大值函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).max())
            return values

        def rolling_min(values, window=5):
            """滚动最小值函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).min())
            return values

        def rolling_sum(values, window=5):
            """滚动求和函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).sum())
            return values

        def ewm_mean(values, span=12):
            """指数加权移动平均函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.ewm(span=span).mean())
            return values

        def correlation(x, y, window=20):
            """滚动相关系数函数"""
            if isinstance(x, str):
                x = data[x]
            if isinstance(y, str):
                y = data[y]
            if isinstance(x, pd.Series) and isinstance(y, pd.Series):
                return _grouped_rolling_corr(x, y, window)
            return None

        def ts_rank(values, window=10):
            """时间序列排名函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).rank(pct=True))
            return values

        def decay_linear(values, window=10):
            """线性衰减加权平均函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                weights = np.arange(1, window + 1)
                return _grouped_transform(values,
                    lambda x: x.rolling(window).apply(lambda y: np.dot(y, weights[-len(y):]) / weights[-len(y):].sum(), raw=True)
                )
            return values

        def pct_change(values, periods=1):
            """百分比变化函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_pct_change(values, periods)
            return values

        def lag(values, periods=1):
            """滞后函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_shift(values, periods)
            return values

        def delta(values, periods=1):
            """差分函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                lagged = _grouped_shift(values, periods)
                return values - lagged
            return values

        def rsi(values, window=14):
            """RSI指标函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                def calc_rsi(x):
                    delta = x.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
                    rs = gain / (loss + 1e-8)
                    return 100 - (100 / (1 + rs))
                return _grouped_transform(values, calc_rsi)
            return values

        def ma(values, window=20):
            """移动平均函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).mean())
            return values

        def ema(values, span=12):
            """指数移动平均函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.ewm(span=span).mean())
            return values

        def std(values, window=20):
            """标准差函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).std())
            return values

        def skew(values, window=20):
            """偏度函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).skew())
            return values

        def kurt(values, window=20):
            """峰度函数"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_transform(values, lambda x: x.rolling(window).kurt())
            return values

        def momentum(values, periods=10):
            """动量函数（收益率）"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return _grouped_pct_change(values, periods)
            return values

        def volume_ma(window=20):
            """成交量移动平均函数"""
            if 'vol' in data.columns:
                return _grouped_transform(data['vol'], lambda x: x.rolling(window).mean())
            return pd.Series(np.nan, index=data.index)

        def bollinger_position(values, window=20, num_std=2):
            """布林带位置函数 - 返回价格在布林带中的相对位置"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                def calc_bb_pos(x):
                    ma = x.rolling(window).mean()
                    std = x.rolling(window).std()
                    upper = ma + num_std * std
                    lower = ma - num_std * std
                    return (x - lower) / (upper - lower + 1e-8)
                return _grouped_transform(values, calc_bb_pos)
            return values

        def macd_func(values, fast=12, slow=26, signal=9):
            """
            MACD函数 - 返回MACD柱状图

            Args:
                values: 价格序列
                fast: 快线周期，默认12
                slow: 慢线周期，默认26
                signal: 信号线周期，默认9

            Returns:
                MACD柱状图 = DIF - DEA
            """
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                def calc_macd(x):
                    # 计算快慢均线
                    ema_fast = x.ewm(span=fast, adjust=False).mean()
                    ema_slow = x.ewm(span=slow, adjust=False).mean()
                    # DIF线（差离值）
                    dif = ema_fast - ema_slow
                    # DEA线（信号线）
                    dea = dif.ewm(span=signal, adjust=False).mean()
                    # MACD柱状图
                    macd = (dif - dea) * 2
                    return macd
                return _grouped_transform(values, calc_macd)
            return values

        def volatility(values, window=20):
            """波动率函数 - 返回收益率的标准差"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                def calc_vol(x):
                    returns = x.pct_change()
                    return returns.rolling(window).std()
                return _grouped_transform(values, calc_vol)
            return values

        def ts_argmax(values, window=10):
            """时间序列最大值位置函数 - 返回窗口内最大值的位置"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                def calc_argmax(x):
                    return x.rolling(window).apply(lambda y: y.argmax() if len(y) > 0 else np.nan, raw=False)
                return _grouped_transform(values, calc_argmax)
            return values

        def ts_argmin(values, window=10):
            """时间序列最小值位置函数 - 返回窗口内最小值的位置"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                def calc_argmin(x):
                    return x.rolling(window).apply(lambda y: y.argmin() if len(y) > 0 else np.nan, raw=False)
                return _grouped_transform(values, calc_argmin)
            return values

        def clip_func(values, lower=None, upper=None):
            """截断函数 - 将值限制在指定范围内"""
            if isinstance(values, str):
                values = data[values]
            if isinstance(values, pd.Series):
                return values.clip(lower=lower, upper=upper)
            return values

        def max_of(x, y):
            """返回两个值的最大值"""
            if isinstance(x, str):
                x = data[x]
            if isinstance(y, str):
                y = data[y]
            return np.maximum(x, y)

        def min_of(x, y):
            """返回两个值的最小值"""
            if isinstance(x, str):
                x = data[x]
            if isinstance(y, str):
                y = data[y]
            return np.minimum(x, y)

        # 构建命名空间
        namespace = {
            # 已计算的变量
            **computed_vars,

            # NumPy和Pandas
            'np': np,
            'pd': pd,

            # 数学函数
            'log_transform': log_transform,
            'abs_value': abs_value,
            'abs': np.abs,
            'sqrt': np.sqrt,
            'sqrt_transform': sqrt_transform,
            'log': np.log,
            'exp': np.exp,
            'sign': np.sign,
            'max': np.maximum,
            'min': np.minimum,

            # 统计函数
            'rank': rank_transform,
            'zscore': zscore_transform,
            'zscore_normalize': zscore_normalize,
            'rank_normalize': rank_normalize,

            # 滚动窗口函数
            'rolling_mean': rolling_mean,
            'rolling_std': rolling_std,
            'rolling_max': rolling_max,
            'rolling_min': rolling_min,
            'rolling_sum': rolling_sum,

            # 指数加权函数
            'ewm_mean': ewm_mean,

            # 统计函数
            'correlation': correlation,
            'ts_rank': ts_rank,

            # 特征工程函数
            'decay_linear': decay_linear,

            # 时间序列变换函数
            'pct_change': pct_change,
            'lag': lag,
            'delta': delta,

            # 技术指标函数
            'rsi': rsi,
            'ma': ma,
            'ema': ema,
            'std': std,
            'skew': skew,
            'kurt': kurt,
            'momentum': momentum,
            'volume_ma': volume_ma,
            'bollinger_position': bollinger_position,
            'macd': macd_func,
            'volatility': volatility,

            # 特征工程函数
            'ts_argmax': ts_argmax,
            'ts_argmin': ts_argmin,

            # 组合函数
            'clip': clip_func,
            'max_of': max_of,
            'min_of': min_of,
        }

        # 添加数据中的所有列到命名空间（确保所有数据字段都可用）
        # 这样可以避免 "name 'xxx' is not defined" 错误
        for col in data.columns:
            if col not in namespace:  # 避免覆盖已定义的函数
                namespace[col] = data[col]

        # 添加索引字段到命名空间（如果是 MultiIndex）
        if isinstance(data.index, pd.MultiIndex):
            for level_name in data.index.names:
                if level_name and level_name not in namespace:
                    namespace[level_name] = data.index.get_level_values(level_name)
        elif data.index.name and data.index.name not in namespace:
            # 单索引情况
            namespace[data.index.name] = data.index

        return namespace

    @staticmethod
    def extract_variables(expr: str) -> set:
        """
        从表达式中提取所有变量名

        Args:
            expr: 表达式字符串

        Returns:
            变量名集合
        """
        # 匹配标识符（变量名）
        var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        variables = set(re.findall(var_pattern, expr))

        # Python关键字
        python_keywords = {
            'np', 'pd', 'and', 'or', 'not', 'in', 'is',
            'if', 'else', 'for', 'while', 'def', 'class',
            'return', 'True', 'False', 'None'
        }

        # 过滤关键字
        return variables - python_keywords


class ExpressionEvaluator:
    """表达式评估器 - 完整的表达式计算流程"""

    def __init__(self, data: pd.DataFrame):
        """
        初始化评估器

        Args:
            data: 数据DataFrame
        """
        self.data = data
        self.parser = ExpressionParser()
        self.namespace_builder = NamespaceBuilder()
        self.computed_vars = {}

    def evaluate(self, expr: str, computed_vars: dict[str, Any] = None) -> pd.Series:
        """
        评估表达式

        Args:
            expr: 原始表达式
            computed_vars: 已计算的变量

        Returns:
            计算结果Series
        """
        if computed_vars:
            self.computed_vars.update(computed_vars)

        # 1. 解析表达式
        parsed_expr = self.parser.parse_expression(expr)
        print(f"   📝 解析后的表达式: {parsed_expr}")

        # 2. 构建基础命名空间
        namespace = self.namespace_builder.build_namespace(self.data, self.computed_vars)

        # 3. 提取变量并智能推断缺失的变量
        variables = self.namespace_builder.extract_variables(parsed_expr)
        known_vars = set(namespace.keys())
        missing_vars = variables - known_vars

        for var in missing_vars:
            inferred_value = self.parser.infer_variable(var, self.data)
            if inferred_value is not None:
                namespace[var] = inferred_value
                print(f"   🔍 智能推断变量: {var}")
            else:
                print(f"   ⚠️ 无法推断变量: {var}")

        # 4. 评估表达式
        try:
            result = eval(parsed_expr, {"__builtins__": {}}, namespace)

            # 转换为Series
            if not isinstance(result, pd.Series):
                result = pd.Series(result)

            # 检查结果
            nan_count = result.isna().sum()
            total = len(result)
            print(f"   📊 计算结果: 长度={total}, NaN={nan_count} ({nan_count/total*100:.1f}%)")

            return result

        except Exception as e:
            print(f"   ❌ 表达式评估失败: {e}")
            print(f"   表达式: {parsed_expr}")
            print(f"   可用变量: {list(namespace.keys())}")
            raise

    def add_computed_var(self, name: str, value: Any):
        """添加已计算的变量"""
        self.computed_vars[name] = value

    def clear_computed_vars(self):
        """清空已计算的变量"""
        self.computed_vars.clear()


# 便捷函数
def parse_expression(expr: str) -> str:
    """解析表达式（便捷函数）"""
    return ExpressionParser.parse_expression(expr)


def infer_variable(var_name: str, data: pd.DataFrame) -> pd.Series | None:
    """推断变量（便捷函数）"""
    return ExpressionParser.infer_variable(var_name, data)


def build_namespace(data: pd.DataFrame, computed_vars: dict[str, Any] = None) -> dict[str, Any]:
    """构建命名空间（便捷函数）"""
    return NamespaceBuilder.build_namespace(data, computed_vars)


def evaluate_expression(expr: str, data: pd.DataFrame, computed_vars: dict[str, Any] = None) -> pd.Series:
    """评估表达式（便捷函数）"""
    evaluator = ExpressionEvaluator(data)
    return evaluator.evaluate(expr, computed_vars)
