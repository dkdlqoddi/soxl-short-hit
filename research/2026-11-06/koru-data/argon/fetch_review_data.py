#!/usr/bin/env python3
import json
import os
from datetime import datetime
import pytz
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"
os.makedirs(OUT_DIR, exist_ok=True)

kst = pytz.timezone("Asia/Seoul")
est = pytz.timezone("America/New_York")
now_kst = datetime.now(kst)
print(f"Data collection started at: {now_kst.strftime('%Y-%m-%d %H:%M:%S KST')}")

# 1. Fetch 1m prepost data for US ETFs & stocks over last 5d
us_1m_tickers = ["KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "QCOM", "ARM", "SPY", "QQQ", "SKHY"]
for sym in us_1m_tickers:
    try:
        df = yf.Ticker(sym).history(period="5d", interval="1m", prepost=True)
        if not df.empty:
            df = df.copy()
            df.index = df.index.tz_convert(est)
            df["ts_est"] = df.index.strftime("%Y-%m-%d %H:%M:%S%z")
            df["ts_kst"] = df.index.tz_convert(kst).strftime("%Y-%m-%d %H:%M:%S%z")
            # Filter window from 2026-11-05 05:00 KST to latest
            mask = df.index.tz_convert(kst) >= pd.Timestamp("2026-11-05 05:00:00", tz=kst)
            sub = df.loc[mask]
            sub.to_csv(os.path.join(OUT_DIR, f"{sym.lower()}_1m_window.csv"))
            print(f"[{sym}] 1m rows in window: {len(sub)}, first={sub['ts_kst'].iloc[0] if len(sub) else 'N/A'}, last={sub['ts_kst'].iloc[-1] if len(sub) else 'N/A'}, last_close={sub['Close'].iloc[-1] if len(sub) else 'N/A'}")
    except Exception as e:
        print(f"[{sym}] 1m error: {e}")

# 2. Fetch 5m data for Korean & FX & London GDR tickers
kr_fx_tickers = {
    "KS11": "^KS11",
    "KQ11": "^KQ11",
    "005930": "005930.KS",
    "000660": "000660.KS",
    "278540": "278540.KS",
    "373220": "373220.KS", # LG Energy Solution
    "006400": "006400.KS", # Samsung SDI
    "KRWX": "KRW=X",
    "VIX": "^VIX",
    "TNX": "^TNX",
    "CLF": "CL=F",
    "SMSN": "SMSN.IL",
}
for name, sym in kr_fx_tickers.items():
    try:
        df5 = yf.Ticker(sym).history(period="5d", interval="5m", prepost=True)
        if not df5.empty:
            df5 = df5.copy()
            df5["ts_kst"] = df5.index.tz_convert(kst).strftime("%Y-%m-%d %H:%M:%S%z")
            mask = df5.index.tz_convert(kst) >= pd.Timestamp("2026-11-04 08:00:00", tz=kst)
            df5.loc[mask].to_csv(os.path.join(OUT_DIR, f"{name.lower()}_5m_window.csv"))
            print(f"[{sym}] 5m rows: {len(df5.loc[mask])}, last_kst={df5['ts_kst'].iloc[-1]}, last_close={df5['Close'].iloc[-1]:.4f}")
    except Exception as e:
        print(f"[{sym}] 5m error: {e}")

# 3. Fetch daily bars for last 15 trading days for US & KR key tickers
daily_syms = ["KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "AMD", "QCOM", "ARM", "SPY", "QQQ", "^DJI", "^GSPC", "^IXIC", "^VIX", "^TNX", "CL=F", "KRW=X", "^KS11", "^KQ11", "005930.KS", "000660.KS", "278540.KS", "SKHY", "SMSN.IL"]
daily_summary = {}
for sym in daily_syms:
    try:
        dfd = yf.Ticker(sym).history(period="1mo", interval="1d")
        if not dfd.empty:
            records = []
            for idx, row in dfd.tail(8).iterrows():
                d_str = idx.strftime("%Y-%m-%d")
                records.append({
                    "date": d_str,
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                })
            daily_summary[sym] = records
    except Exception as e:
        print(f"[{sym}] daily error: {e}")

with open(os.path.join(OUT_DIR, "daily_recent.json"), "w", encoding="utf-8") as f:
    json.dump({"fetched_at_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S KST"), "data": daily_summary}, f, ensure_ascii=False, indent=2)

# 4. Fetch Naver Mobile JSON API for real-time Korean market (2026-11-06 morning + 11/5 close info)
naver_urls = {
    "KOSPI": "https://m.stock.naver.com/api/index/KOSPI/basic",
    "KOSDAQ": "https://m.stock.naver.com/api/index/KOSDAQ/basic",
    "KOSPI_trend": "https://m.stock.naver.com/api/index/KOSPI/trend",
    "KOSPI_price": "https://m.stock.naver.com/api/index/KOSPI/price?pageSize=10&page=1",
    "005930_basic": "https://m.stock.naver.com/api/stock/005930/basic",
    "005930_price": "https://m.stock.naver.com/api/stock/005930/price?pageSize=10&page=1",
    "005930_trend": "https://m.stock.naver.com/api/stock/005930/trend",
    "000660_basic": "https://m.stock.naver.com/api/stock/000660/basic",
    "000660_price": "https://m.stock.naver.com/api/stock/000660/price?pageSize=10&page=1",
    "000660_trend": "https://m.stock.naver.com/api/stock/000660/trend",
    "278540_basic": "https://m.stock.naver.com/api/stock/278540/basic",
    "278540_price": "https://m.stock.naver.com/api/stock/278540/price?pageSize=10&page=1",
}
naver_data = {"fetched_at_kst": datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S KST")}
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
for k, url in naver_urls.items():
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            naver_data[k] = json.loads(resp.read().decode("utf-8"))
        print(f"[Naver {k}] OK")
    except Exception as e:
        print(f"[Naver {k}] error: {e}")

with open(os.path.join(OUT_DIR, "naver_realtime.json"), "w", encoding="utf-8") as f:
    json.dump(naver_data, f, ensure_ascii=False, indent=2)

print("Done!")
