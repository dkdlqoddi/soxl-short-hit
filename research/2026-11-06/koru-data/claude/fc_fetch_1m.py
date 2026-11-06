"""KORU 24h forecast (2026-11-06 base 10:42 KST): fetch 1-minute bars incl. pre/post for the last 5 days."""
import sys, os, time
import pandas as pd
import yfinance as yf

OUT = os.path.dirname(os.path.abspath(__file__))
SYMS = ["KORU", "EWY", "SOXX", "MU", "SPY", "QQQ", "SKHY", "NVDA", "^KS11", "005930.KS", "000660.KS", "278540.KS", "KRW=X", "^VIX", "ES=F", "NQ=F"]
for s in SYMS:
    try:
        df = yf.Ticker(s).history(period="5d", interval="1m", prepost=True)
        if df.empty:
            print(s, "EMPTY"); continue
        df.index = df.index.tz_convert("Asia/Seoul")
        fn = os.path.join(OUT, "fc_m1_" + s.replace("^", "").replace("=", "_").replace(".", "_") + ".csv")
        df[["Open", "High", "Low", "Close", "Volume"]].to_csv(fn)
        last = df.iloc[-1]
        print(f"{s:10s} rows={len(df):5d} last={df.index[-1]} close={last['Close']:.4f} vol={last['Volume']}")
    except Exception as e:
        print(s, "ERR", e)
    time.sleep(0.3)
