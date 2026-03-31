"""持有期收益率计算模块"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def calculate_holding_returns(
    data: pd.DataFrame,
    candidates: list[dict[str, Any]],
    holding_periods: list[int],
    screening_date: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """计算给定持有期的收益率
    
    Args:
        data: DataFrame with MultiIndex (trade_date, ts_code) and 'close' column
        candidates: List of dicts with at least 'ts_code'; may have 'name', 'confidence'
        holding_periods: List of holding period lengths in trading days
        screening_date: Optional screening date; if None, derived from data
    
    Returns:
        Dict with 'screening_date' (str), 'per_stock' (list of dicts), 'summary' (dict)
    """
    all_dates = sorted(data.index.get_level_values("trade_date").unique())
    if not all_dates:
        return {"screening_date": "", "per_stock": [], "summary": {}}

    if screening_date is None:
        max_period = max(holding_periods) if holding_periods else 0
        offset_idx = len(all_dates) - 1 - max_period
        screening_date = all_dates[offset_idx] if offset_idx >= 0 else all_dates[-1]

    screening_date_str = screening_date.strftime("%Y%m%d")
    try:
        screen_idx = list(all_dates).index(screening_date)
    except ValueError:
        return {"screening_date": screening_date_str, "per_stock": [], "summary": {}}

    per_stock_results = []
    for candidate in candidates:
        ts_code = candidate.get("ts_code", "")
        stock_name = candidate.get("name", ts_code)
        confidence = candidate.get("confidence", 0)
        stock_entry = {
            "ts_code": ts_code,
            "name": stock_name,
            "confidence": confidence,
        }
        try:
            stock_data = data.xs(ts_code, level="ts_code")
        except KeyError:
            for period in holding_periods:
                stock_entry[f"ret_{period}d"] = None
                stock_entry[f"ret_{period}d_note"] = "无数据"
            per_stock_results.append(stock_entry)
            continue

        if screening_date not in stock_data.index:
            for period in holding_periods:
                stock_entry[f"ret_{period}d"] = None
                stock_entry[f"ret_{period}d_note"] = "筛选日无数据"
            per_stock_results.append(stock_entry)
            continue

        screen_close = stock_data.loc[screening_date, "close"]
        for period in holding_periods:
            target_idx = screen_idx + period
            if target_idx < len(all_dates):
                target_date = all_dates[target_idx]
                if target_date in stock_data.index:
                    target_close = stock_data.loc[target_date, "close"]
                    ret = (target_close - screen_close) / screen_close
                    stock_entry[f"ret_{period}d"] = float(ret)
                    stock_entry[f"ret_{period}d_note"] = "ok"
                else:
                    stock_entry[f"ret_{period}d"] = None
                    stock_entry[f"ret_{period}d_note"] = "目标日无数据"
            else:
                stock_entry[f"ret_{period}d"] = None
                stock_entry[f"ret_{period}d_note"] = "数据不足"
        per_stock_results.append(stock_entry)

    summary = {}
    for period in holding_periods:
        key = f"ret_{period}d"
        valid_rets = [s[key] for s in per_stock_results if s.get(key) is not None]
        if valid_rets:
            summary[period] = {
                "count": len(valid_rets),
                "mean": float(np.mean(valid_rets)),
                "median": float(np.median(valid_rets)),
                "std": float(np.std(valid_rets)),
                "min": float(np.min(valid_rets)),
                "max": float(np.max(valid_rets)),
                "win_rate": float(sum(1 for r in valid_rets if r > 0) / len(valid_rets)),
                "total_stocks": len(per_stock_results),
                "valid_stocks": len(valid_rets),
            }
        else:
            summary[period] = {
                "count": 0,
                "mean": None,
                "note": "无有效收益率数据",
            }

    return {
        "screening_date": screening_date_str,
        "per_stock": per_stock_results,
        "summary": summary,
    }
