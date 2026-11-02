"""Download daily history for SOXL, SOXS, SOXX and VIX with yfinance into <data_dir>/<ticker>_1d.csv (single header)."""
import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, pandas as pd, yfinance as yf
out = sys.argv[1]
for tk, name in [("SOXL", "soxl"), ("SOXS", "soxs"), ("SOXX", "soxx"), ("^VIX", "vix")]:
    df = yf.download(tk, period="max", interval="1d", auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    df.index.name = "date"
    df.to_csv(os.path.join(out, f"{name}_1d.csv"))
    print(name, df.index[0].date(), df.index[-1].date(), len(df))
