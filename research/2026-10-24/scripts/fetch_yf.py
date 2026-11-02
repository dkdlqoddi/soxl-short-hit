import sys, yfinance as yf, pandas as pd
out = sys.argv[1]
ok = {}
for label, kw in {
    "soxl_5m_5d": dict(tickers="SOXL", period="5d", interval="5m"),
    "soxl_1h_60d": dict(tickers="SOXL", period="60d", interval="1h"),
    "soxl_1d_2y": dict(tickers="SOXL", period="2y", interval="1d"),
}.items():
    try:
        df = yf.download(**kw, progress=False, auto_adjust=False, prepost=True, threads=False)
        if df is None or len(df) == 0:
            print(label, "EMPTY"); continue
        df.to_csv(f"{out}/{label}.csv")
        print(label, "rows", len(df), "first", df.index[0], "last", df.index[-1])
    except Exception as e:
        print(label, "ERROR", type(e).__name__, str(e)[:200])
