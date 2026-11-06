#!/usr/bin/env python3
"""
Fetch live & historical market data for KORU 24h forecast (2026-11-06 10:42 KST base).
Saves all outputs under research/2026-11-06/koru-data/argon/.
"""
import json
import datetime as dt
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

now_kst = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
print(f"Fetch started at KST: {now_kst.isoformat()}")

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 1. Naver Finance realtime (KOSPI, KOSDAQ, Samsung, SK Hynix, KODEX MSCI Korea TR, LG Energy, etc.)
naver_targets = {
    "KOSPI": "https://m.stock.naver.com/api/index/KOSPI/basic",
    "KOSDAQ": "https://m.stock.naver.com/api/index/KOSDAQ/basic",
    "KOSPI_trend": "https://m.stock.naver.com/api/index/KOSPI/trend",
    "005930": "https://m.stock.naver.com/api/stock/005930/basic",
    "000660": "https://m.stock.naver.com/api/stock/000660/basic",
    "278540": "https://m.stock.naver.com/api/stock/278540/basic",
    "373220": "https://m.stock.naver.com/api/stock/373220/basic",
    "005380": "https://m.stock.naver.com/api/stock/005380/basic",
    "105560": "https://m.stock.naver.com/api/stock/105560/basic",
}
naver_data = {"fetched_at_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S")}
for k, url in naver_targets.items():
    try:
        naver_data[k] = fetch_json(url)
    except Exception as e:
        naver_data[k] = {"error": str(e)}

with open(f"{OUT_DIR}/forecast_naver_realtime.json", "w", encoding="utf-8") as f:
    json.dump(naver_data, f, ensure_ascii=False, indent=2)

# 2. Nasdaq historical API for KORU & EWY to cross-verify official closes
nasdaq_data = {}
for sym in ["KORU", "EWY", "SOXX", "SOXL"]:
    url = f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass=etf&fromdate=2026-10-15&todate=2026-11-06&limit=30"
    try:
        res = fetch_json(url)
        rows = res.get("data", {}).get("tradesTable", {}).get("rows", [])
        nasdaq_data[sym] = rows[:10]
    except Exception as e:
        nasdaq_data[sym] = {"error": str(e)}

with open(f"{OUT_DIR}/forecast_nasdaq_recent.json", "w", encoding="utf-8") as f:
    json.dump(nasdaq_data, f, ensure_ascii=False, indent=2)

# 3. yfinance 1m data (5d, prepost=True) for key US & KR tickers & futures
tickers_1m = [
    "KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "AMD", "QCOM", "ARM",
    "SPY", "QQQ", "ES=F", "NQ=F", "KRW=X", "^KS11", "^KQ11",
    "005930.KS", "000660.KS", "278540.KS", "^VIX", "^TNX", "DX-Y.NYB",
    "SKHY", "SMSN.IL"
]

snapshot_1m = {"fetched_at_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"), "tickers": {}}
kst_tz = dt.timezone(dt.timedelta(hours=9))
base_cutoff_kst = dt.datetime(2026, 11, 6, 10, 42, 59, tzinfo=kst_tz)

for sym in tickers_1m:
    try:
        df = yf.Ticker(sym).history(period="5d", interval="1m", prepost=True)
        if df.empty:
            df = yf.Ticker(sym).history(period="5d", interval="5m", prepost=True)
        if df.empty:
            snapshot_1m["tickers"][sym] = {"empty": True}
            continue
        df_kst = df.copy()
        df_kst.index = df_kst.index.tz_convert(kst_tz)
        if sym in ["KORU", "EWY", "278540.KS", "^KS11", "005930.KS", "000660.KS", "KRW=X", "ES=F", "NQ=F", "SOXX", "MU"]:
            safe = sym.replace("^", "").replace("=", "").replace(".", "_")
            df_kst.tail(600).to_csv(f"{OUT_DIR}/forecast_{safe}_intraday.csv")
        # Latest bar at or before 10:42 KST
        before_base = df_kst[df_kst.index <= base_cutoff_kst]
        last_base = before_base.iloc[-1] if not before_base.empty else None
        last_now = df_kst.iloc[-1]
        snapshot_1m["tickers"][sym] = {
            "base_bar_kst": str(before_base.index[-1]) if last_base is not None else None,
            "base_close": float(last_base["Close"]) if last_base is not None else None,
            "base_high": float(last_base["High"]) if last_base is not None else None,
            "base_low": float(last_base["Low"]) if last_base is not None else None,
            "latest_bar_kst": str(df_kst.index[-1]),
            "latest_close": float(last_now["Close"]),
        }
    except Exception as e:
        snapshot_1m["tickers"][sym] = {"error": str(e)}

# Detailed KORU & EWY session breakdown for 2026-11-05 US regular & after-market
for sym in ["KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA"]:
    df = yf.Ticker(sym).history(period="5d", interval="1m", prepost=True)
    if not df.empty:
        est_tz = df.index.tz
        d_reg = df[(df.index >= "2026-11-05 09:30:00") & (df.index < "2026-11-05 16:00:00")]
        d_ah = df[(df.index >= "2026-11-05 16:00:00") & (df.index <= "2026-11-05 20:00:00")]
        d_ah_morning = df[(df.index >= "2026-11-05 18:00:00") & (df.index <= "2026-11-05 20:00:00")] # 08:00~10:00 KST
        d_ah_krx = df[(df.index >= "2026-11-05 19:00:00") & (df.index <= "2026-11-05 20:00:00")] # 09:00~10:00 KST
        snapshot_1m["tickers"][sym]["us_1105_reg"] = {
            "open": float(d_reg["Open"].iloc[0]) if not d_reg.empty else None,
            "high": float(d_reg["High"].max()) if not d_reg.empty else None,
            "low": float(d_reg["Low"].min()) if not d_reg.empty else None,
            "close_1m": float(d_reg["Close"].iloc[-1]) if not d_reg.empty else None,
            "vol": int(d_reg["Volume"].sum()) if not d_reg.empty else 0,
        }
        snapshot_1m["tickers"][sym]["us_1105_ah_full"] = {
            "open": float(d_ah["Open"].iloc[0]) if not d_ah.empty else None,
            "high": float(d_ah["High"].max()) if not d_ah.empty else None,
            "high_time_kst": str(d_ah["High"].idxmax().tz_convert(kst_tz)) if not d_ah.empty else None,
            "low": float(d_ah["Low"].min()) if not d_ah.empty else None,
            "low_time_kst": str(d_ah["Low"].idxmin().tz_convert(kst_tz)) if not d_ah.empty else None,
            "close": float(d_ah["Close"].iloc[-1]) if not d_ah.empty else None,
            "close_time_kst": str(d_ah.index[-1].tz_convert(kst_tz)) if not d_ah.empty else None,
            "vol": int(d_ah["Volume"].sum()) if not d_ah.empty else 0,
        }
        snapshot_1m["tickers"][sym]["us_1105_ah_0900_1000_kst"] = {
            "open": float(d_ah_krx["Open"].iloc[0]) if not d_ah_krx.empty else None,
            "high": float(d_ah_krx["High"].max()) if not d_ah_krx.empty else None,
            "low": float(d_ah_krx["Low"].min()) if not d_ah_krx.empty else None,
            "close": float(d_ah_krx["Close"].iloc[-1]) if not d_ah_krx.empty else None,
            "vol": int(d_ah_krx["Volume"].sum()) if not d_ah_krx.empty else 0,
        }

with open(f"{OUT_DIR}/forecast_snapshot_1m.json", "w", encoding="utf-8") as f:
    json.dump(snapshot_1m, f, ensure_ascii=False, indent=2)

print("Saved forecast_naver_realtime.json, forecast_nasdaq_recent.json, forecast_snapshot_1m.json")
