"""行业查询工具 - 获取可用行业列表."""

from __future__ import annotations

import json


from datahub import get_available_industries as get_available_industries_from_data
from infrastructure.errors.exceptions import DataLoadError
def create_get_available_industries(data_fn):
    """创建 get_available_industries 桥接工具.

    Args:
        data_fn: 返回当前数据 DataFrame 的函数

    Returns:
        get_available_industries 函数
    """

    def get_available_industries() -> str:
        """获取可用行业列表."""
        
        try:
            data = data_fn()
            
            # 支持两种返回格式：DataFrame 或 (DataFrame, index_data)
            if isinstance(data, tuple) and len(data) == 2:
                data, _ = data
            
            if data is None or data.empty:
                raise DataLoadError("No data available")
            industry_list = get_available_industries_from_data(data)
            return json.dumps({"industries": industry_list}, ensure_ascii=False)
        except DataLoadError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"error": f"Failed to get industries: {e}"}, ensure_ascii=False
            )

    return get_available_industries
