#!/usr/bin/env python3
"""Fetch exact 1m, 5m, 15m, 1h, and daily market data for SOXL 2026-11-05 review."""

import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
KST = ZoneInfo("Asia/Seoul")
EST = ZoneInfo("America/New_York")

fetched_at_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
print(f"Fetching data at {fetched_at_kst} ...")

TICKERS_1M = [
    "SOXL", "SOXS", "SOXX", "SMH",
    "NVDA", "AMD", "AVGO", "MU", "QCOM", "ARM", "TSM", "ASML", "INTC", "MRVL", "SMCI",
    "QQQ", "SPY", "DIA", "NQ=F", "^VIX", "^TNX"
]

def save_1m(sym, fname):
    t = yf.Ticker(sym)
    df = t.history(period="5d", interval="1m", prepost=True, auto_adjust=False)
    if df.empty:
        print(f"WARNING: empty 1m for {sym}")
        return df
    df = df.copy()
    df["ts_est"] = df.index.tz_convert(EST).strftime("%Y-%m-%d %H:%M:%S")
    df["ts_kst"] = df.index.tz_convert(KST).strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(os.path.join(OUT_DIR, fname), index=True)
    return df

soxl_1m = save_1m("SOXL", "soxl_1m_5d.csv")
soxx_1m = save_1m("SOXX", "soxx_1m_5d.csv")
nvda_1m = save_1m("NVDA", "nvda_1m_5d.csv")
amd_1m = save_1m("AMD", "amd_1m_5d.csv")
mu_1m = save_1m("MU", "mu_1m_5d.csv")
avgo_1m = save_1m("AVGO", "avgo_1m_5d.csv")
qcom_1m = save_1m("QCOM", "qcom_1m_5d.csv")
arm_1m = save_1m("ARM", "arm_1m_5d.csv")
qqq_1m = save_1m("QQQ", "qqq_1m_5d.csv")
spy_1m = save_1m("SPY", "spy_1m_5d.csv")
nq_1m = save_1m("NQ=F", "nq_1m_5d.csv")
vix_1m = save_1m("^VIX", "vix_1m_5d.csv")

# Also fetch 15m for SOXL to check Codex's "two consecutive 15m bars" invalidation rule!
soxl_15m = yf.Ticker("SOXL").history(period="5d", interval="15m", prepost=True, auto_adjust=False)
if not soxl_15m.empty:
    soxl_15m = soxl_15m.copy()
    soxl_15m["ts_est"] = soxl_15m.index.tz_convert(EST).strftime("%Y-%m-%d %H:%M:%S")
    soxl_15m["ts_kst"] = soxl_15m.index.tz_convert(KST).strftime("%Y-%m-%d %H:%M:%S")
    soxl_15m.to_csv(os.path.join(OUT_DIR, "soxl_15m_5d.csv"), index=True)

# Fetch daily bars for all key tickers (last 30d)
daily_summary = {}
for sym in TICKERS_1M + ["^KS11", "005930.KS", "000660.KS", "KRW=X"]:
    try:
        d = yf.Ticker(sym).history(period="1mo", interval="1d", auto_adjust=False)
        if not d.empty:
            rows = []
            for idx, r in d.tail(6).iterrows():
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(r["Open"]), 4),
                    "high": round(float(r["High"]), 4),
                    "low": round(float(r["Low"]), 4),
                    "close": round(float(r["Close"]), 4),
                    "volume": int(r["Volume"]) if not pd.isna(r["Volume"]) else 0,
                })
            daily_summary[sym] = rows
    except Exception as e:
        print(f"Daily error {sym}: {e}")

with open(os.path.join(OUT_DIR, "daily_summary.json"), "w", encoding="utf-8") as f:
    json.dump({"fetched_at_kst": fetched_at_kst, "daily": daily_summary}, f, ensure_ascii=False, indent=2)

# Fetch Nasdaq official historical daily for SOXL to cross-check exact open/close
try:
    req = urllib.request.Request(
        "https://api.nasdaq.com/api/quote/SOXL/historical?assetclass=etf&fromdate=2026-10-20&todate=2026-11-06&limit=30",
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        nasdaq_json = json.loads(resp.read().decode("utf-8"))
    with open(os.path.join(OUT_DIR, "nasdaq_soxl_daily.json"), "w", encoding="utf-8") as f:
        json.dump(nasdaq_json, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"Nasdaq API error: {e}")

# Fetch Naver Korean market basic info
naver_data = {}
for code, path in [("KOSPI", "index/KOSPI/basic"), ("005930", "stock/005930/basic"), ("000660", "stock/000660/basic")]:
    try:
        req = urllib.request.Request(
            f"https://m.stock.naver.com/api/{path}",
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            naver_data[code] = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Naver error {code}: {e}")

with open(os.path.join(OUT_DIR, "naver_kr_realtime.json"), "w", encoding="utf-8") as f:
    json.dump({"fetched_at_kst": fetched_at_kst, "data": naver_data}, f, ensure_ascii=False, indent=2)

# Print key SOXL checkpoints!
print("\n=== SOXL DAILY (yfinance) ===")
for r in daily_summary.get("SOXL", []):
    print(r)

print("\n=== SOXL KEY 1-MINUTE CHECKPOINTS ===")
if not soxl_1m.empty:
    target_ksts = [
        "2026-11-04 23:30:00",
        "2026-11-05 00:05:00",
        "2026-11-05 00:17:00",
        "2026-11-05 00:30:00",
        "2026-11-05 05:59:00",
        "2026-11-05 06:00:00",
        "2026-11-05 09:59:00",
        "2026-11-05 18:00:00",
        "2026-11-05 22:30:00",
        "2026-11-05 23:29:00",
        "2026-11-05 23:30:00",
        "2026-11-05 23:31:00",
        "2026-11-06 00:04:00",
        "2026-11-06 00:05:00",
        "2026-11-06 05:59:00",
        "2026-11-06 06:00:00",
    ]
    for tk in target_ksts:
        sub = soxl_1m[soxl_1m["ts_kst"] <= tk].tail(2)
        print(f"--- Up to {tk} KST ---")
        for _, row in sub.iterrows():
            print(f"  {row['ts_kst']} ({row['ts_est']} EST) | O={row['Open']:.4f} H={row['High']:.4f} L={row['Low']:.4f} C={row['Close']:.4f} V={int(row['Volume'])}")
    print("--- Latest 3 1m bars ---")
    for _, row in soxl_1m.tail(3).iterrows():
        print(f"  {row['ts_kst']} ({row['ts_est']} EST) | O={row['Open']:.4f} H={row['High']:.4f} L={row['Low']:.4f} C={row['Close']:.4f} V={int(row['Volume'])}")
