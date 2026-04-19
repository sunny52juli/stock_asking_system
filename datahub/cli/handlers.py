"""CLI handlers: call datahub APIs and screening_scripts JSON."""

from __future__ import annotations

import json
from typing import Any

from datahub.core.exceptions import DataNotFoundError
from datahub.entries import Feature, Fund, Index, News, Stock


def df_to_json(df: pd.DataFrame) -> str:
    """Serialize DataFrame to JSON records; dates as ISO."""
    if df is None or df.empty:
        return "[]"
    return df.to_json(orient="records", date_format="iso", force_ascii=False)


def list_to_json(lst: list[str]) -> str:
    """Serialize list of strings to JSON array."""
    return json.dumps(lst, ensure_ascii=False)


def err_json(msg: str, code: str | None = None) -> str:
    """Error payload for stdout (single line JSON)."""
    out: dict[str, Any] = {"ok": False, "error": msg}
    if code:
        out["code"] = code
    return json.dumps(out, ensure_ascii=False)


def _opts_repo(opts: dict[str, Any]) -> dict[str, Any]:
    root = opts.get("root")
    mode = opts.get("mode", "auto")
    token = opts.get("token")
    return {"root": root, "mode": mode, "token": token}


# ---- stock ----
def run_stock_price(opts: dict[str, Any]) -> int:
    date = opts.get("date")
    start_date = opts.get("start_date")
    end_date = opts.get("end_date")
    if date is None and (start_date is None or end_date is None):
        print(err_json("Provide either --date or (--start-date and --end-date)"))
        return 2
    try:
        s = Stock(**_opts_repo(opts))
        df = s.price(
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=opts.get("codes"),
            fields=opts.get("fields"),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


def run_stock_universe(opts: dict[str, Any]) -> int:
    try:
        s = Stock(**_opts_repo(opts))
        df = s.universe()
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


def run_stock_universe_by_index(opts: dict[str, Any]) -> int:
    index_code = opts.get("index_code")
    if not index_code:
        print(err_json("index_code (positional) is required"))
        return 2
    date = opts.get("date")
    start_date = opts.get("start_date")
    end_date = opts.get("end_date")
    if date is None and (start_date is None or end_date is None):
        print(err_json("Provide either --date or (--start-date and --end-date)"))
        return 2
    try:
        s = Stock(**_opts_repo(opts))
        df = s.universe_by_index(
            index_code,
            date=date,
            start_date=start_date,
            end_date=end_date,
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


def run_stock_available_dates(opts: dict[str, Any]) -> int:
    try:
        s = Stock(**_opts_repo(opts))
        lst = s.available_dates()
        print(list_to_json(lst))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


# Deleted: run_stock_latest_date - 避免使用 latest_date() 导致未来函数问题


# ---- fund ----
def run_fund_nav(opts: dict[str, Any]) -> int:
    date = opts.get("date")
    start_date = opts.get("start_date")
    end_date = opts.get("end_date")
    if date is None and (start_date is None or end_date is None):
        print(err_json("Provide either --date or (--start-date and --end-date)"))
        return 2
    try:
        f = Fund(**_opts_repo(opts))
        df = f.nav(
            date=date,
            start_date=start_date,
            end_date=end_date,
            codes=opts.get("codes"),
            fields=opts.get("fields"),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


def run_fund_universe(opts: dict[str, Any]) -> int:
    try:
        f = Fund(**_opts_repo(opts))
        df = f.universe(
            market=opts.get("market", "CN"),
            fund_type=opts.get("fund_type"),
            status=opts.get("status", "active"),
            fields=opts.get("fields"),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


def run_fund_available_dates(opts: dict[str, Any]) -> int:
    try:
        f = Fund(**_opts_repo(opts))
        lst = f.available_dates()
        print(list_to_json(lst))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


# Deleted: run_fund_latest_date - 避免使用 latest_date() 导致未来函数问题


# ---- index ----
def run_index_members(opts: dict[str, Any]) -> int:
    index_code = opts.get("index_code")
    if not index_code:
        print(err_json("index_code (positional) is required"))
        return 2
    date = opts.get("date")
    start_date = opts.get("start_date")
    end_date = opts.get("end_date")
    if date is None and (start_date is None or end_date is None):
        print(err_json("Provide either --date or (--start-date and --end-date)"))
        return 2
    try:
        idx = Index(**_opts_repo(opts))
        df = idx.members(
            index_code,
            date=date,
            start_date=start_date,
            end_date=end_date,
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


def run_index_level(opts: dict[str, Any]) -> int:
    index_code = opts.get("index_code")
    start_date = opts.get("start_date")
    end_date = opts.get("end_date")
    if not index_code or not start_date or not end_date:
        print(err_json("index_code, --start-date and --end-date are required"))
        return 2
    try:
        idx = Index(**_opts_repo(opts))
        df = idx.level(
            index_code,
            start_date=start_date,
            end_date=end_date,
            freq=opts.get("freq", "daily"),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


def run_index_available_dates(opts: dict[str, Any]) -> int:
    try:
        idx = Index(**_opts_repo(opts))
        lst = idx.available_dates(opts.get("index_code"))
        print(list_to_json(lst))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


# Deleted: run_index_latest_date - 避免使用 latest_date() 导致未来函数问题


# ---- news ----
def run_news_sentiment(opts: dict[str, Any]) -> int:
    try:
        n = News(**_opts_repo(opts))
        df = n.sentiment(
            code=opts.get("code"),
            date=opts.get("date"),
            start_date=opts.get("start_date"),
            end_date=opts.get("end_date"),
            source=opts.get("source", "combined"),
            window=opts.get("window", 7),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


def run_news_events(opts: dict[str, Any]) -> int:
    try:
        n = News(**_opts_repo(opts))
        df = n.events(
            code=opts.get("code"),
            start_date=opts.get("start_date"),
            end_date=opts.get("end_date"),
            event_type=opts.get("event_type", "all"),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


# ---- feature ----
def run_feature_snapshot(opts: dict[str, Any]) -> int:
    factors = opts.get("factors")
    date = opts.get("date")
    if not factors or not date:
        print(err_json("--factors and --date are required"))
        return 2
    try:
        fe = Feature(**_opts_repo(opts))
        df = fe.snapshot(
            factors=factors,
            date=date,
            universe=opts.get("universe"),
        )
        print(df_to_json(df))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1
    except ValueError as e:
        print(err_json(str(e)))
        return 2


def run_feature_list_factors(opts: dict[str, Any]) -> int:
    try:
        fe = Feature(**_opts_repo(opts))
        lst = fe.list_factors()
        print(list_to_json(lst))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


def run_feature_available_dates(opts: dict[str, Any]) -> int:
    try:
        fe = Feature(**_opts_repo(opts))
        lst = fe.available_dates(opts.get("factor"))
        print(list_to_json(lst))
        return 0
    except DataNotFoundError as e:
        print(err_json(str(e), "DataNotFoundError"))
        return 1


# Dispatch map: (product, action) -> handler
HANDLERS: dict[tuple[str, str], Any] = {
    ("stock", "price"): run_stock_price,
    ("stock", "universe"): run_stock_universe,
    ("stock", "universe-by-index"): run_stock_universe_by_index,
    ("stock", "available-dates"): run_stock_available_dates,
    # Deleted: ("stock", "latest-date") - 避免使用 latest_date() 导致未来函数问题
    ("fund", "nav"): run_fund_nav,
    ("fund", "universe"): run_fund_universe,
    ("fund", "available-dates"): run_fund_available_dates,
    # Deleted: ("fund", "latest-date") - 避免使用 latest_date() 导致未来函数问题
    ("index", "members"): run_index_members,
    ("index", "level"): run_index_level,
    ("index", "available-dates"): run_index_available_dates,
    # Deleted: ("index", "latest-date") - 避免使用 latest_date() 导致未来函数问题
    ("news", "sentiment"): run_news_sentiment,
    ("news", "events"): run_news_events,
    ("feature", "snapshot"): run_feature_snapshot,
    ("feature", "list-factors"): run_feature_list_factors,
    ("feature", "available-dates"): run_feature_available_dates,
}


def run(product: str | None, action: str | None, opts: dict[str, Any]) -> int:
    if product is None or action is None:
        return 0  # parser will print help
    key = (product, action)
    handler = HANDLERS.get(key)
    if handler is None:
        print(err_json(f"Unknown product/action: {product}/{action}"))
        return 2
    try:
        return handler(opts)
    except Exception as e:
        print(err_json(str(e)))
        return 1
