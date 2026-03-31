"""Fund dataset registration: FUND_NAV."""

from datahub.core.dataset import Dataset, DatasetMeta, DatasetRegistry, FetchStep

# FUND_NAV: 基金净值数据 - 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.FUND_NAV,
        domain="fund",
        partition_by="date",
        key_columns=["ts_code", "nav_date"],
        storage_path="fund/nav",
        date_column="nav_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="基金净值数据",
    ),
    pipeline=[
        FetchStep(
            api_name="fund_nav",
            param_mapping={"nav_date": "date"},
            fields=None,
            merge_on=[],
        ),
    ],
)

# FUND_BASIC: 基金基本信息 - 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.FUND_BASIC,
        domain="fund",
        partition_by="none",
        key_columns=["ts_code"],
        storage_path="fund/basic",
        date_column="",
        code_column="ts_code",
        partition_key_template="basic",
        description="基金基本信息",
    ),
    pipeline=[
        FetchStep(
            api_name="fund_basic",
            param_mapping={},
            fixed_params={"market": "E"},
            fields=[
                "ts_code",
                "name",
                "management",
                "custodian",
                "fund_type",
                "found_date",
                "due_date",
                "list_date",
                "issue_date",
                "delist_date",
                "issue_amount",
                "m_fee",
                "c_fee",
                "duration_year",
                "p_value",
                "min_amount",
                "exp_return",
                "benchmark",
                "status",
                "invest_type",
                "type",
                "trustee",
                "purc_startdate",
                "redm_startdate",
                "market",
            ],
            merge_on=[],
        ),
    ],
)

# FUND_PORTFOLIO: 基金持仓（季报披露）- 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.FUND_PORTFOLIO,
        domain="fund",
        partition_by="date",
        key_columns=["ts_code", "ann_date", "end_date"],
        storage_path="fund/portfolio",
        date_column="ann_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="基金持仓（季报披露）",
    ),
    pipeline=[
        FetchStep(
            api_name="fund_portfolio",
            param_mapping={"ts_code": "code"},
            fields=[
                "ts_code",
                "ann_date",
                "end_date",
                "symbol",
                "mkv",
                "amount",
                "stk_mkv_ratio",
                "stk_float_ratio",
            ],
            merge_on=[],
        ),
    ],
)

# FUND_DIVIDEND: 基金分红数据 - 单步管道
DatasetRegistry.register(
    DatasetMeta(
        dataset=Dataset.FUND_DIVIDEND,
        domain="fund",
        partition_by="date",
        key_columns=["ts_code", "ann_date"],
        storage_path="fund/dividend",
        date_column="ann_date",
        code_column="ts_code",
        partition_key_template="{date}",
        description="基金分红（每份分红金额/除权日/支付日）",
    ),
    pipeline=[
        FetchStep(
            api_name="fund_div",
            param_mapping={"ts_code": "code"},
            fields=[
                "ts_code",
                "ann_date",
                "imp_anndate",
                "base_date",
                "div_proc",
                "pay_per_unit",
                "net_ex_date",
                "ex_date",
                "pay_date",
                "earpay_date",
                "net_nav",
                "ex_nav",
                "ex_dnavpershare",
                "unit_total",
                "reinvest_nav",
                "record_date",
            ],
            merge_on=[],
            optional=True,
        ),
    ],
)
