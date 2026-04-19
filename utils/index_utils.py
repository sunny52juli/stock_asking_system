"""指数工具辅助函数 - 统一的收益率预处理和合并逻辑."""
import polars as pl
from mcp_server.executors.index_selector import get_index_code


def prepare_index_returns(index_data: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """统一预处理指数收益率。
    
    Args:
        index_data: 指数数据 DataFrame (columns: trade_date, index_code, close)
        
    Returns:
        {index_code: DataFrame(trade_date, return)}
    """
    if 'index_code' not in index_data.columns:
        # 提供更详细的错误信息，帮助诊断
        error_msg = (
            f"指数数据缺少 index_code 列，当前列: {list(index_data.columns)}\n"
            f"提示：这通常意味着传入的是个股数据而非指数数据。"
            f"请检查数据源是否正确加载了指数数据。"
        )
        raise ValueError(error_msg)
    
    unique_indices = index_data['index_code'].unique().to_list()
    index_returns_map = {}
    
    for idx_code in unique_indices:
        idx_data = index_data.filter(pl.col('index_code') == idx_code).sort('trade_date')
        if len(idx_data) < 2:
            continue
        
        idx_returns = idx_data.with_columns(
            (pl.col('close') / pl.col('close').shift(1) - 1).alias('return')
        ).drop_nulls(subset=['return'])
        
        index_returns_map[idx_code] = idx_returns
    
    if not index_returns_map:
        raise ValueError("无法计算任何指数的收益率，请检查指数数据格式")
    
    return index_returns_map


def merge_stock_with_index_returns(
    stock_data: pl.DataFrame,
    index_returns_map: dict[str, pl.DataFrame],
    stock_col: str = "close"
) -> pl.DataFrame:
    """统一合并股票和指数收益率。
    
    Args:
        stock_data: 股票数据 DataFrame
        index_returns_map: 指数收益率映射
        stock_col: 股票价格列名
        
    Returns:
        DataFrame with columns: ts_code, index_code, stock_return, index_return
    """
    
    # 为每只股票映射对应的指数代码
    stock_with_index = stock_data.with_columns(
        pl.col('ts_code').map_elements(get_index_code, return_dtype=pl.Utf8).alias('index_code')
    )
    
    # 构建指数收益率查找表
    index_returns_list = []
    for idx_code, idx_df in index_returns_map.items():
        index_returns_list.append(
            idx_df.select(['trade_date', 'return']).with_columns(
                pl.lit(idx_code).alias('index_code')
            )
        )
    index_returns_table = pl.concat(index_returns_list)
    
    # 合并股票和指数收益率
    merged = stock_with_index.join(
        index_returns_table.rename({'return': 'index_return'}),
        on=['trade_date', 'index_code'],
        how='inner'
    )
    
    # 按股票分组排序并计算收益率
    stock_returns = merged.sort(['ts_code', 'trade_date']).with_columns(
        pl.col(stock_col).pct_change().over('ts_code').alias('stock_return')
    )
    
    # 清理空值
    stock_returns = stock_returns.drop_nulls(subset=['stock_return', 'index_return'])
    
    return stock_returns.select(['ts_code', 'index_code', 'stock_return', 'index_return'])
