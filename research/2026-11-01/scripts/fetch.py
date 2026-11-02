import sys, site; sys.path.insert(0, site.getusersitepackages())
import yfinance as yf, pandas as pd
out = sys.argv[1]
for label, kw in {
    "soxl_1d_yf": dict(tickers="SOXL", period="max", interval="1d"),
    "soxl_1h_yf": dict(tickers="SOXL", period="2y", interval="1h"),
    "soxl_5m_yf": dict(tickers="SOXL", period="60d", interval="5m"),
}.items():
    try:
        df = yf.download(**kw, progress=False, auto_adjust=False, prepost=False, threads=False)
        if df is None or len(df) == 0:
            print(label, "EMPTY"); continue
        df.to_csv(f"{out}/{label}.csv")
        print(label, "rows", len(df), "first", df.index[0], "last", df.index[-1])
    except Exception as e:
        print(label, "ERROR", type(e).__name__, str(e)[:200])
