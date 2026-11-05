"""Capture public quotes and historical context; never submit orders.

Run once to freeze inputs. Pass --offline to recompute from saved responses.
Historical open-to-next-open results are context, not a fitted forecast.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
SESSION_DATE = "2026-11-04"
JOBS = {
    "soxl_daily": ("SOXL", "10y", "1d", False),
    "soxl_intraday": ("SOXL", "60d", "5m", True),
    **{s.lower(): (s, "1d", "1m", False) for s in ["SOXX", "NVDA", "AMD", "QCOM", "ARM", "QQQ"]},
}


def download(item):
    key, (symbol, period, interval, extended) = item
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": period, "interval": interval, "includePrePost": str(extended).lower()}
    response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if payload["chart"].get("error"):
        raise RuntimeError(payload["chart"]["error"])
    record = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "url": response.url, "response": payload}
    (DATA / f"{key}_raw.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return key


def read(key):
    record = json.loads((DATA / f"{key}_raw.json").read_text())
    result = record["response"]["chart"]["result"][0]
    frame = pd.DataFrame(result["indicators"]["quote"][0], index=pd.to_datetime(result["timestamp"], unit="s", utc=True))
    frame.index = frame.index.tz_convert("America/New_York")
    frame.index.name = "timestamp_est_or_edt"
    frame = frame.dropna(subset=["open", "close"]).sort_index()
    return record, result, frame


def summary(returns):
    x = returns.dropna()
    if x.empty:
        return {"n": 0}
    n = len(x)
    p = (x > 0).mean()
    z = 1.96
    center = (p + z*z/(2*n))/(1+z*z/n)
    half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return {"n": n, "up_pct": p*100, "mean_pct": x.mean()*100,
            "median_pct": x.median()*100, "p10_pct": x.quantile(.1)*100,
            "p25_pct": x.quantile(.25)*100, "p75_pct": x.quantile(.75)*100,
            "p90_pct": x.quantile(.9)*100,
            "up_pct_wilson95": [100*(center-half), 100*(center+half)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not args.offline:
        with ThreadPoolExecutor(max_workers=4) as pool:
            print("Downloaded:", ", ".join(pool.map(download, JOBS.items())))

    snapshots = {}
    for key in JOBS:
        record, result, frame = read(key)
        meta = result["meta"]
        snapshots[key] = {
            "retrieved_at_utc": record["retrieved_at_utc"], "url": record["url"],
            "price": meta.get("regularMarketPrice"),
            "price_time_utc": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).isoformat(),
            "previous_close": meta.get("previousClose"),
            "high": meta.get("regularMarketDayHigh"), "low": meta.get("regularMarketDayLow"),
            "volume": meta.get("regularMarketVolume"),
        }
        if key in ("soxl_daily", "soxl_intraday"):
            frame.to_csv(DATA / f"{key}.csv")
    _, _, d = read("soxl_daily")
    d["date"] = d.index.date.astype(str)
    d["previous_close"] = d["close"].shift()
    d["gap"] = d["open"] / d["previous_close"] - 1
    d["prior_ma20"] = d["close"].rolling(20).mean().shift()
    d["open_to_next_open"] = d["open"].shift(-1) / d["open"] - 1
    d["elapsed_hours"] = (d.index.to_series().shift(-1) - d.index.to_series()).dt.total_seconds()/3600
    # No unfinished target; exact 24h excludes weekends, holidays and DST changes.
    usable = d[(d["date"] < SESSION_DATE) & d["elapsed_hours"].eq(24)].copy()
    groups = {
        "all_exact24h": usable,
        "recent60_sessions": usable.loc[usable.index.intersection(d[d["date"] < SESSION_DATE].tail(60).index)],
        "gap_minus6_to_minus2_pct": usable[usable["gap"].between(-.06, -.02)],
        "gap_minus6_to_minus2_below_ma20": usable[usable["gap"].between(-.06, -.02) & (usable["previous_close"] < usable["prior_ma20"])],
    }
    stats = {key: summary(group["open_to_next_open"]) for key, group in groups.items()}
    usable.to_csv(DATA / "historical_open_to_open.csv")
    today = d[d["date"].eq(SESSION_DATE)].iloc[-1]
    prior = d[d["date"] < SESSION_DATE]
    tr = pd.concat([prior["high"]-prior["low"], (prior["high"]-prior["close"].shift()).abs(), (prior["low"]-prior["close"].shift()).abs()], axis=1).max(axis=1)
    metrics = {"daily_open": today["open"], "previous_close": today["previous_close"],
               "gap_pct": today["gap"]*100, "prior_ma20": today["prior_ma20"],
               "prior_14day_mean_true_range": tr.tail(14).mean(),
               "prior_20day_close_return_sd_pct": prior["close"].pct_change().tail(20).std()*100,
               "first_historical_date": str(d.index[0]), "last_historical_date": str(d.index[-1])}
    _, intraday_result, intraday = read("soxl_intraday")
    quote_time = pd.to_datetime(intraday_result["meta"]["regularMarketTime"], unit="s", utc=True).tz_convert("America/New_York")
    first30 = intraday[(intraday.index.date.astype(str) == SESSION_DATE) & (intraday.index.hour == 9) & (intraday.index.minute >= 30)]
    first30 = first30[first30.index + pd.Timedelta(minutes=5) <= quote_time]
    if len(first30) == 6:
        metrics["first30"] = {"bar_open": first30.iloc[0]["open"], "close": first30.iloc[-1]["close"],
                               "high": first30["high"].max(), "low": first30["low"].min(),
                               "volume": int(first30["volume"].sum()),
                               "close_vs_daily_open_pct": (first30.iloc[-1]["close"] / today["open"] - 1)*100}
    output = {"metrics": metrics, "historical_context": stats, "snapshots": snapshots}
    (DATA / "analysis.json").write_text(json.dumps(output, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
