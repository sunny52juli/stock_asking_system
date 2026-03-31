"""CLI argument definitions: subparsers and options per product/action."""

from __future__ import annotations

import argparse
from typing import Any


def _add_common_date_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date", type=str, help="Single date YYYYMMDD")
    parser.add_argument("--start-date", type=str, dest="start_date", help="Range start YYYYMMDD")
    parser.add_argument("--end-date", type=str, dest="end_date", help="Range end YYYYMMDD")


def _add_codes_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--codes", type=str, help="Comma-separated codes (e.g. 000001.SZ,600000.SH)"
    )
    parser.add_argument("--fields", type=str, help="Comma-separated field names")


def _parse_list(s: str | None) -> list[str] | None:
    if s is None or s.strip() == "":
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="datahub",
        description="Query datahub financial data (stock, fund, index, news, feature). Output is JSON.",
    )
    root.add_argument(
        "--root", type=str, default=None, help="Cache root (default: env DATA_CACHE_ROOT)"
    )
    root.add_argument("--mode", type=str, default="auto", choices=["local", "auto", "remote"])
    root.add_argument(
        "--token", type=str, default=None, help="Tushare token (default: env DATA_SOURCE_TOKEN)"
    )
    root.add_argument("--version", action="store_true", help="Print version and exit")

    sub = root.add_subparsers(dest="product", required=False, metavar="product")

    # ---- stock ----
    stock_p = sub.add_parser("stock", help="Stock data")
    stock_actions = stock_p.add_subparsers(dest="action", required=True)

    p = stock_actions.add_parser("price", help="Daily quotes (single date or range)")
    _add_common_date_args(p)
    _add_codes_fields(p)

    p = stock_actions.add_parser("universe", help="Stock basic listing (universe)")
    # no args

    p = stock_actions.add_parser("universe-by-index", help="Index constituents")
    p.add_argument("index_code", type=str, help="Index code (e.g. 000300.SH)")
    _add_common_date_args(p)

    p = stock_actions.add_parser("available-dates", help="Available trade dates")
    # no args

    p = stock_actions.add_parser("latest-date", help="Latest available date")
    # no args

    # ---- fund ----
    fund_p = sub.add_parser("fund", help="Fund data")
    fund_actions = fund_p.add_subparsers(dest="action", required=True)

    p = fund_actions.add_parser("nav", help="Fund NAV (single date or range)")
    _add_common_date_args(p)
    _add_codes_fields(p)

    p = fund_actions.add_parser("universe", help="Fund universe (basic list)")
    p.add_argument("--market", type=str, default="CN")
    p.add_argument("--fund-type", type=str, dest="fund_type", default=None)
    p.add_argument("--status", type=str, default="active")

    p = fund_actions.add_parser("available-dates", help="Available NAV dates")
    p = fund_actions.add_parser("latest-date", help="Latest NAV date")

    # ---- index ----
    index_p = sub.add_parser("index", help="Index data")
    index_actions = index_p.add_subparsers(dest="action", required=True)

    p = index_actions.add_parser("members", help="Index constituents")
    p.add_argument("index_code", type=str, help="Index code (e.g. 000300.SH)")
    _add_common_date_args(p)

    p = index_actions.add_parser("level", help="Index level (OHLC) over range")
    p.add_argument("index_code", type=str, help="Index code")
    p.add_argument("--start-date", type=str, dest="start_date", required=True)
    p.add_argument("--end-date", type=str, dest="end_date", required=True)
    p.add_argument("--freq", type=str, default="daily")

    p = index_actions.add_parser("available-dates", help="Available dates")
    p.add_argument("--index-code", type=str, dest="index_code", default=None)
    p = index_actions.add_parser("latest-date", help="Latest date")
    p.add_argument("--index-code", type=str, dest="index_code", default=None)

    # ---- news ----
    news_p = sub.add_parser("news", help="News/sentiment data")
    news_actions = news_p.add_subparsers(dest="action", required=True)

    p = news_actions.add_parser("sentiment", help="Sentiment scores")
    p.add_argument("--code", type=str, default=None)
    _add_common_date_args(p)
    p.add_argument(
        "--source", type=str, default="combined", choices=["news", "social", "analyst", "combined"]
    )
    p.add_argument("--window", type=int, default=7)

    p = news_actions.add_parser("events", help="Events")
    p.add_argument("--code", type=str, default=None)
    p.add_argument("--start-date", type=str, dest="start_date", default=None)
    p.add_argument("--end-date", type=str, dest="end_date", default=None)
    p.add_argument(
        "--event-type",
        type=str,
        dest="event_type",
        default="all",
        choices=[
            "earnings",
            "guidance",
            "ma",
            "management",
            "buyback",
            "strategic",
            "regulatory",
            "all",
        ],
    )

    # ---- feature ----
    feature_p = sub.add_parser("feature", help="Factor/feature data")
    feature_actions = feature_p.add_subparsers(dest="action", required=True)

    p = feature_actions.add_parser("snapshot", help="Factor snapshot at a date")
    p.add_argument("--factors", type=str, required=True, help="Comma-separated factor names")
    p.add_argument("--date", type=str, required=True, help="Date YYYYMMDD")
    p.add_argument("--universe", type=str, default=None, help="Comma-separated codes (optional)")

    p = feature_actions.add_parser("list-factors", help="List available factors")
    p = feature_actions.add_parser("available-dates", help="Available dates for factors")
    p.add_argument("--factor", type=str, dest="factor", default=None)

    return root


def get_opts(ns: argparse.Namespace) -> dict[str, Any]:
    """Convert namespace to kwargs for handlers; parse list strings."""
    opts: dict[str, Any] = {
        "root": getattr(ns, "root", None),
        "mode": getattr(ns, "mode", "auto"),
        "token": getattr(ns, "token", None),
    }
    if hasattr(ns, "date") and ns.date is not None:
        opts["date"] = ns.date
    if hasattr(ns, "start_date") and getattr(ns, "start_date", None) is not None:
        opts["start_date"] = ns.start_date
    if hasattr(ns, "end_date") and getattr(ns, "end_date", None) is not None:
        opts["end_date"] = ns.end_date
    if hasattr(ns, "codes") and ns.codes is not None:
        opts["codes"] = _parse_list(ns.codes)
    if hasattr(ns, "fields") and ns.fields is not None:
        opts["fields"] = _parse_list(ns.fields)
    if hasattr(ns, "index_code") and getattr(ns, "index_code", None) is not None:
        opts["index_code"] = ns.index_code
    if hasattr(ns, "market"):
        opts["market"] = getattr(ns, "market", "CN")
    if hasattr(ns, "fund_type"):
        opts["fund_type"] = getattr(ns, "fund_type", None)
    if hasattr(ns, "status"):
        opts["status"] = getattr(ns, "status", "active")
    if hasattr(ns, "freq"):
        opts["freq"] = getattr(ns, "freq", "daily")
    if hasattr(ns, "code"):
        opts["code"] = getattr(ns, "code", None)
    if hasattr(ns, "source"):
        opts["source"] = getattr(ns, "source", "combined")
    if hasattr(ns, "window"):
        opts["window"] = getattr(ns, "window", 7)
    if hasattr(ns, "event_type"):
        opts["event_type"] = getattr(ns, "event_type", "all")
    if hasattr(ns, "factors"):
        opts["factors"] = _parse_list(getattr(ns, "factors", "")) or []
    if hasattr(ns, "factor"):
        opts["factor"] = getattr(ns, "factor", None)
    if hasattr(ns, "universe"):
        opts["universe"] = _parse_list(getattr(ns, "universe", ""))
    return opts
