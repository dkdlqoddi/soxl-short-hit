"""1분봉(시간외 포함) 수집 — KORU 11/5 회차 복기용 (Claude Fable Max).
실행: python3 research/2026-11-06/koru-data/claude/fetch_1m.py
"""
import sys, time, datetime as dt
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent
US = ["KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "SPY", "QQQ", "SKHY", "QCOM", "ARM"]
KR = ["^KS11", "005930.KS", "000660.KS", "278540.KS", "KRW=X"]

def fetch(sym, prepost):
    for i in range(3):
        try:
            df = yf.Ticker(sym).history(period="5d", interval="1m", prepost=prepost, auto_adjust=False)
            if len(df):
                return df
        except Exception as e:  # noqa
            print("retry", sym, e, file=sys.stderr)
        time.sleep(2)
    return pd.DataFrame()

now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
print("fetched_at_kst", now.strftime("%Y-%m-%d %H:%M:%S"))
for sym in US + KR:
    df = fetch(sym, prepost=sym in US)
    if df.empty:
        print(sym, "EMPTY"); continue
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = df.index.tz_convert("Asia/Seoul")
    df.index.name = "kst"
    name = sym.replace("^", "").replace("=", "_").replace(".", "_")
    df.round(4).to_csv(OUT / f"m1_{name}.csv")
    print(f"{sym:10s} rows={len(df):5d} {df.index[0]} → {df.index[-1]} last={df['Close'].iloc[-1]:.4f}")
