"""Index dataset registrations."""

from datahub.core.dataset import Dataset, DatasetMeta, DatasetRegistry, FetchStep

# INDEX_DAILY: 指数日线行情 - 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.INDEX_DAILY,
        domain="index",
        partition_by="date",
        key_columns=["ts_code", "trade_date"],
        storage_path="index/daily",
        date_column="trade_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="指数日线行情（开高低收量额）",
    ),
    pipeline=[
        FetchStep(
            api_name="index_daily",
            param_mapping={"trade_date": "date", "ts_code": "index_code"},
            fields=[
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "change",
                "pct_chg",
                "vol",
                "amount",
            ],
            merge_on=[],
        ),
    ],
)

# INDEX_VALUATION: 指数估值指标 - 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.INDEX_VALUATION,
        domain="index",
        partition_by="date",
        key_columns=["ts_code", "trade_date"],
        storage_path="index/valuation",
        date_column="trade_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="指数估值（PE/PB/PS/股息率/换手率）",
    ),
    pipeline=[
        FetchStep(
            api_name="index_dailybasic",
            param_mapping={"trade_date": "date", "ts_code": "index_code"},
            fields=[
                "ts_code",
                "trade_date",
                "total_mv",
                "float_mv",
                "total_share",
                "float_share",
                "free_share",
                "turnover_rate",
                "turnover_rate_f",
                "pe",
                "pe_ttm",
                "pb",
            ],
            merge_on=[],
            optional=True,
        ),
    ],
)

# INDEX_BASIC: 指数基本信息列表快照 - 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.INDEX_BASIC,
        domain="index",
        partition_by="none",
        key_columns=["ts_code"],
        storage_path="index/basic",
        date_column="",
        code_column="ts_code",
        partition_key_template="basic",
        description="指数基本信息（名称/发布机构/基日/编制方法）",
    ),
    pipeline=[
        FetchStep(
            api_name="index_basic",
            param_mapping={},
            fixed_params={"market": "SSE"},
            fields=[
                "ts_code",
                "name",
                "fullname",
                "market",
                "publisher",
                "index_type",
                "category",
                "base_date",
                "base_point",
                "list_date",
                "weight_rule",
                "desc",
                "exp_date",
            ],
            merge_on=[],
            optional=True,
        ),
    ],
)
