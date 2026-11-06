"""KORU 24h forecast (2026-11-06) — 과거 데이터 수집 (Claude Fable Max).
일봉 전체 기간 + 1시간봉 730일(KORU·EWY·SOXX는 시간외 포함). 원본은 hist/ 아래 pickle (용량 때문에 작업 뒤 삭제, 재실행하면 다시 받음).
실행: python3 fc_fetch_hist.py
"""
import sys, time
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent / "hist"
OUT.mkdir(exist_ok=True)

def fetch(sym, **kw):
    for i in range(3):
        try:
            df = yf.Ticker(sym).history(**kw)
            if len(df):
                return df
        except Exception as e:  # noqa
            print("retry", sym, e, file=sys.stderr)
        time.sleep(2 + 2 * i)
    return pd.DataFrame()

def safe(s):
    return s.replace("^", "").replace("=", "_").replace(".", "_")

print("fetched_at_kst", pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S"))
for s in ["EWY", "KORU", "^KS11", "SPY", "QQQ", "^SOX", "SOXX", "MU", "278540.KS", "KRW=X", "SKHY", "^VIX", "005930.KS", "000660.KS", "^GSPC", "ES=F", "NQ=F"]:
    df = fetch(s, period="max", interval="1d", auto_adjust=False)
    df.to_pickle(OUT / f"d_{safe(s)}.pkl")
    print(f"{s:10s} 1d rows={len(df):5d} {str(df.index[0])[:10]} → {str(df.index[-1])[:10]} lastClose={df['Close'].iloc[-1]}")
    r = fetch(s, period="10d", interval="1d", auto_adjust=False)
    r.to_pickle(OUT / f"r_{safe(s)}.pkl")
for s in ["KORU", "EWY", "SOXX", "SPY"]:
    df = fetch(s, period="730d", interval="1h", prepost=True, auto_adjust=False)
    df.to_pickle(OUT / f"h_{safe(s)}.pkl")
    print(f"{s:10s} 1h rows={len(df):5d} {df.index[0]} → {df.index[-1]}")
for s in ["^KS11", "KRW=X", "ES=F", "278540.KS"]:
    df = fetch(s, period="730d", interval="1h", auto_adjust=False)
    df.to_pickle(OUT / f"h_{safe(s)}.pkl")
    print(f"{s:10s} 1h rows={len(df):5d} {df.index[0]} → {df.index[-1]}")
