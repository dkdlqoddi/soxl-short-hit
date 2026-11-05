"""Freeze KORU public data and compute descriptive historical context.

Use --offline for an unchanged snapshot. No fitted prediction or trading orders.
After-hours bars are indicative: Yahoo often reports zero extended-hours volume.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "koru-data"
DATA.mkdir(exist_ok=True)
JOBS = {
    "koru_daily": ("KORU", "10y", "1d", False),
    "koru_intraday": ("KORU", "60d", "5m", True),
    **{key: (symbol, "5d", "5m", True) for key, symbol in {
        "ewy": "EWY", "soxx": "SOXX", "qcom": "QCOM", "arm": "ARM",
        "nvda": "NVDA", "mu": "MU", "usdkrw": "KRW=X",
        "kospi": "^KS11", "samsung": "005930.KS", "skhynix": "000660.KS",
    }.items()},
}


def download(item):
    key, (symbol, period, interval, extended) = item
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
    params = {"range": period, "interval": interval, "includePrePost": str(extended).lower(), "events": "div,splits"}
    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload["chart"].get("error"):
        raise RuntimeError(payload["chart"]["error"])
    record = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "url": r.url, "response": payload}
    (DATA / f"{key}_raw.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return key


def read(key):
    record = json.loads((DATA / f"{key}_raw.json").read_text())
    result = record["response"]["chart"]["result"][0]
    bars = pd.DataFrame(result["indicators"]["quote"][0], index=pd.to_datetime(result["timestamp"], unit="s", utc=True))
    bars.index.name = "timestamp_utc"
    bars = bars.dropna(subset=["close"]).sort_index()
    return record, result, bars


def summary(s):
    x = s.dropna()
    if len(x) == 0:
        return {"n": 0}
    n = len(x)
    p = (x > 0).mean()
    z = 1.96
    center = (p + z*z/(2*n))/(1+z*z/n)
    half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return {"n": n, "up_pct": p*100, "mean_pct": x.mean()*100,
            "median_pct": x.median()*100,
            **{f"p{q}_pct": x.quantile(q/100)*100 for q in [10, 25, 75, 90]},
            "up_pct_wilson95": [100*(center-half), 100*(center+half)]}


def finite_json(value):
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not args.offline:
        with ThreadPoolExecutor(max_workers=4) as pool:
            print("Downloaded:", ", ".join(pool.map(download, JOBS.items())))

    snapshots = {}
    for key in JOBS:
        record, result, bars = read(key)
        meta = result["meta"]
        last = bars.iloc[-1]
        snapshots[key] = {"url": record["url"], "retrieved_at_utc": record["retrieved_at_utc"],
                          "last_bar_time_utc": bars.index[-1].isoformat(), "last_bar_close": last["close"],
                          "regular_market_price": meta.get("regularMarketPrice"),
                          "regular_market_time_utc": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).isoformat(),
                          "previous_close": meta.get("previousClose"),
                          "regular_day_high": meta.get("regularMarketDayHigh"),
                          "regular_day_low": meta.get("regularMarketDayLow"), "currency": meta.get("currency")}
        if key in ["koru_daily", "koru_intraday"]:
            bars.to_csv(DATA / f"{key}.csv")

    _, result, d = read("koru_daily")
    d.index = pd.Index(d.index.tz_convert("America/New_York").date, name="us_date")
    d["day_return"] = d["close"].pct_change()
    d["ma20"] = d["close"].rolling(20).mean()
    d["close_location"] = (d["close"]-d["low"])/(d["high"]-d["low"])
    d["next_close_return"] = d["close"].shift(-1)/d["close"]-1
    tr = pd.concat([d["high"]-d["low"], (d["high"]-d["close"].shift()).abs(), (d["low"]-d["close"].shift()).abs()], axis=1).max(axis=1)
    latest = d.iloc[-1]
    history = d.dropna(subset=["next_close_return"])
    daily_groups = {
        "all_next_trading_day": history,
        "last60_trading_days": history.tail(60),
        "down3pct_below_ma20": history[(history["day_return"] <= -.03) & (history["close"] < history["ma20"])],
        "down3pct_below_ma20_low_close": history[(history["day_return"] <= -.03) & (history["close"] < history["ma20"]) & (history["close_location"] <= .2)],
    }
    daily_stats = {key: summary(group["next_close_return"]) for key, group in daily_groups.items()}
    history.to_csv(DATA / "daily_context.csv")

    _, _, bars = read("koru_intraday")
    base_time = bars.index[-1]
    base_price = bars.iloc[-1]["close"]
    premium = base_price/latest["close"]-1
    low_close_group = daily_groups["down3pct_below_ma20_low_close"]
    threshold_context = {"current_afterhours_premium_pct": premium*100,
                         "n": len(low_close_group),
                         "historical_next_close_return_exceeds_current_premium_pct": (low_close_group["next_close_return"] > premium).mean()*100,
                         "median_next_close_price_if_applied_to_today_close": latest["close"]*(1+low_close_group["next_close_return"].median()),
                         "note": "Illustrative close-to-close threshold comparison, not a historical after-hours strategy or forecast probability."}
    # Historic cuts use the latest completed 5-minute boundary near today's quote.
    # A bar starting at the cut is excluded; its close would contain future trades.
    floor = base_time.floor("5min")
    offset = floor - floor.normalize()
    rows = []
    for day in pd.date_range(bars.index[0].normalize(), floor.normalize(), freq="D", tz="UTC"):
        cut = day + offset
        eligible = bars[(bars.index + pd.Timedelta(minutes=5) <= cut) & (bars.index + pd.Timedelta(minutes=5) >= cut-pd.Timedelta(minutes=10))]
        if eligible.empty:
            continue
        bar_time = eligible.index[-1]
        us_day = cut.tz_convert("America/New_York").date()
        if us_day not in d.index:
            continue
        price = eligible.iloc[-1]["close"]
        daily = d.loc[us_day]
        rows.append({"cut_utc": cut, "bar_start_utc": bar_time, "price": price,
                     "lag_minutes": (cut-(bar_time+pd.Timedelta(minutes=5))).total_seconds()/60,
                     "afterhours_return": price/daily["close"]-1,
                     "day_return": daily["day_return"], "close_below_ma20": bool(daily["close"] < daily["ma20"])})
    a = pd.DataFrame(rows).set_index("cut_utc")
    a["next_cut"] = a.index.to_series().shift(-1)
    a["next_bar_start_utc"] = a["bar_start_utc"].shift(-1)
    a["next_price"] = a["price"].shift(-1)
    a["return_24h"] = a["next_price"]/a["price"]-1
    relaxed = a[(a["next_cut"]-a.index.to_series()).dt.total_seconds().eq(86400) & (a["next_cut"] <= base_time)]
    timing_sensitivity = summary(relaxed.loc[(relaxed["day_return"] <= -.03) & (relaxed["afterhours_return"] > 0), "return_24h"])
    a = a[(a["next_cut"]-a.index.to_series()).dt.total_seconds().eq(86400)
          & (a["next_bar_start_utc"]-a["bar_start_utc"]).dt.total_seconds().eq(86400)
          & (a["next_cut"] <= base_time)]
    groups = {
        "all_exact24h": a,
        "afterhours_positive": a[a["afterhours_return"] > 0],
        "down3pct_then_afterhours_positive": a[(a["day_return"] <= -.03) & (a["afterhours_return"] > 0)],
    }
    ah_stats = {key: summary(group["return_24h"]) for key, group in groups.items()}
    a.to_csv(DATA / "afterhours_24h_context.csv")

    output = {
        "base_price": base_price, "base_time_utc": base_time.isoformat(),
        "base_time_kst": base_time.tz_convert("Asia/Seoul").isoformat(),
        "forecast_end_kst": (base_time+pd.Timedelta(hours=24)).tz_convert("Asia/Seoul").isoformat(),
        "historical_cut_kst": floor.tz_convert("Asia/Seoul").strftime("%H:%M"),
        "daily_latest": {"date": str(d.index[-1]), **latest.to_dict(),
                         "mean_true_range14": tr.tail(14).mean(),
                         "close_return_sd20_pct": d["day_return"].tail(20).std()*100,
                         "daily_history_start": str(d.index[0])},
        "daily_context": daily_stats, "afterhours_24h_context": ah_stats,
        "baseline_threshold_context": threshold_context,
        "afterhours_endpoint_lag_sensitivity": timing_sensitivity,
        "snapshots": snapshots,
        "limits": ["Yahoo bars do not establish executable bid/ask quotes.",
                   "Daily statistics include weekends and are not 24-hour after-hours outcomes.",
                   "After-hours statistics use completed 5-minute bars near the current time, with at most 10-minute endpoint lag.",
                   "Conditions selected for current-market comparison; not out-of-sample validation."],
    }
    output = finite_json(output)
    (DATA / "analysis.json").write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str, allow_nan=False))


if __name__ == "__main__":
    main()
