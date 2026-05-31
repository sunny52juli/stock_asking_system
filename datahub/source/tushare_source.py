import logging
import time
from typing import Any
import tushare as ts
import polars as pl


from infrastructure.config.settings import get_settings
from datahub.core.source import DataSource

logger = logging.getLogger(__name__)


class TushareSource(DataSource):
    def __init__(
        self,
        token: str | None = None,
        max_retry: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.token = token or get_settings().data.source_token
        if not self.token:
            raise ValueError("Tushare token not configured")
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.max_retry = max_retry
        self.retry_delay = retry_delay

    @property
    def name(self) -> str:
        return "Tushare"

    def call(self, api_name: str, params: dict[str, Any]) -> "pl.DataFrame | None":
        for attempt in range(self.max_retry):
            try:
                api_fn = getattr(self.pro, api_name)
                # 只在debug级别记录API调用详情，避免刷屏
                logger.debug(f"调用 Tushare API: {api_name}, 参数: {params}")
                result = api_fn(**params)
                if result is not None and not result.empty:
                    # Convert pandas DataFrame to polars immediately
                    logger.debug(f"API {api_name} 成功，返回 {len(result)} 条记录")
                    return pl.from_pandas(result)
                # 空结果只在debug级别记录
                logger.debug(f"API {api_name} 返回空结果")
                return None
            except Exception as e:
                error_msg = str(e)
                logger.error(f"API {api_name} 第 {attempt + 1} 次尝试失败: {error_msg}")
                if attempt < self.max_retry - 1:
                    wait = (attempt + 1) * self.retry_delay
                    logger.warning(
                        "API %s attempt %d failed: %s, retry in %.1fs",
                        api_name,
                        attempt + 1,
                        error_msg,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "API %s failed after %d attempts: %s",
                        api_name,
                        self.max_retry,
                        error_msg,
                    )
                    # 特别提示积分不足的情况
                    if "积分" in error_msg or "permission" in error_msg.lower() or "权限" in error_msg:
                        logger.error("💡 提示：可能是Tushare积分不足，请检查您的积分等级和API权限要求")
                    return None
        return None
    
    def fetch(
        self,
        api_name: str,
        params: dict[str, Any],
        fields: list[str] | None = None,
    ) -> "pl.DataFrame | None":
        """Fetch data from Tushare API.
        
        Args:
            api_name: API 名称
            params: 参数字典
            fields: 需要返回的字段列表（可选）
            
        Returns:
            Polars DataFrame 或 None
        """
        # 如果指定了 fields，添加到参数中
        if fields:
            params['fields'] = ','.join(fields)
        
        # 调用 call 方法
        return self.call(api_name, params)

    def ping(self) -> bool:
        result = self.call("stock_basic", {"exchange": "", "list_status": "L", "limit": "1"})
        return result is not None
