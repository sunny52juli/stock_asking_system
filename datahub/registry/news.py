"""News dataset registrations."""

from datahub.core.dataset import Dataset, DatasetMeta, DatasetRegistry, FetchStep

DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.STOCK_ANNOUNCEMENT,
        domain="news",
        partition_by="date",
        key_columns=["ts_code", "ann_date"],
        storage_path="news/announcement",
        date_column="ann_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="上市公司公告（定期/临时）",
    ),
    pipeline=[
        FetchStep(
            api_name="anns",
            param_mapping={"ts_code": "code", "start_date": "start_date", "end_date": "end_date"},
            fields=["ts_code", "ann_date", "ann_type", "title", "content"],
            optional=True,
        ),
    ],
)

DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.ANALYST_REPORT,
        domain="news",
        partition_by="date",
        key_columns=["ts_code", "report_date"],
        storage_path="news/analyst_report",
        date_column="report_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="分析师研报评级（买入/增持/中性/减持/卖出）",
    ),
    pipeline=[
        FetchStep(
            api_name="report_rc",
            param_mapping={"ts_code": "code", "start_date": "start_date", "end_date": "end_date"},
            fields=[
                "ts_code",
                "report_date",
                "report_title",
                "report_type",
                "classify",
                "org_name",
                "analyst_name",
                "rating_code",
                "rating_type",
                "pre_rating_code",
                "pre_rating_type",
                "abstract",
            ],
            optional=True,
        ),
    ],
)

DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.EARNINGS_FORECAST,
        domain="news",
        partition_by="date",
        key_columns=["ts_code", "ann_date", "end_date"],
        storage_path="news/earnings_forecast",
        date_column="ann_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="上市公司盈利预告",
    ),
    pipeline=[
        FetchStep(
            api_name="forecast",
            param_mapping={"ts_code": "code", "start_date": "start_date", "end_date": "end_date"},
            fields=[
                "ts_code",
                "ann_date",
                "end_date",
                "type",
                "p_change_min",
                "p_change_max",
                "net_profit_min",
                "net_profit_max",
                "last_parent_net",
                "first_ann_date",
                "summary",
                "change_reason",
            ],
            optional=True,
        ),
    ],
)
