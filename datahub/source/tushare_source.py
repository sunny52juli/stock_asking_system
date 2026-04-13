import logging
import time
from typing import Any

import pandas as pd
import tushare as ts

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

    def call(self, api_name: str, params: dict[str, Any]) -> pd.DataFrame | None:
        for attempt in range(self.max_retry):
            try:
                api_fn = getattr(self.pro, api_name)
                result = api_fn(**params)
                if result is not None and not result.empty:
                    return result
                return None
            except Exception as e:
                if attempt < self.max_retry - 1:
                    wait = (attempt + 1) * self.retry_delay
                    logger.warning(
                        "API %s attempt %d failed: %s, retry in %.1fs",
                        api_name,
                        attempt + 1,
                        e,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "API %s failed after %d attempts: %s",
                        api_name,
                        self.max_retry,
                        e,
                    )
                    return None
        return None

    def ping(self) -> bool:
        result = self.call("stock_basic", {"exchange": "", "list_status": "L", "limit": "1"})
        return result is not None
