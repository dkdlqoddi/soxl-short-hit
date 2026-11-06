"""KORU 24h forecast (2026-11-06) 공통 로더 (Claude Fable Max). hist/*.pkl (fc_fetch_hist.py) 사용."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
H = D / "hist"
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 40)

def safe(s):
    return s.replace("^", "").replace("=", "_").replace(".", "_")

def dl(sym, tz):
    """일봉. period=max의 마지막 종가 NaN은 10일 일봉(r_*.pkl)으로 보충."""
    df = pd.read_pickle(H / f"d_{safe(sym)}.pkl")
    rp = H / f"r_{safe(sym)}.pkl"
    def norm(x):
        idx = x.index.tz_convert(tz) if x.index.tz is not None else x.index
        x = x[["Open", "High", "Low", "Close", "Volume"]].copy()
        x.index = pd.to_datetime(idx.strftime("%Y-%m-%d"))
        return x[~x.index.duplicated(keep="last")]
    df = norm(df)
    if rp.exists():
        r = norm(pd.read_pickle(rp))
        for d in r.index:
            if d in df.index:
                for c in ["Open", "High", "Low", "Close"]:
                    if pd.isna(df.loc[d, c]) and not pd.isna(r.loc[d, c]):
                        df.loc[d, c] = r.loc[d, c]
            else:
                df.loc[d] = r.loc[d]
    # yfinance 일봉은 10:05~11:00 KST 조회 시 최신 미국 종가가 NaN → 09:44 KST 조회분(d1_recent_all.csv)의 공식 종가로 보충
    if sym in PATCH_1105 and pd.Timestamp("2026-11-05") in df.index and pd.isna(df.loc["2026-11-05", "Close"]):
        df.loc["2026-11-05", "Close"] = PATCH_1105[sym]
    # ^KS11 일봉에 11/5 행이 빠져 있음 → 네이버 일봉 값으로 보충
    if sym == "^KS11" and pd.Timestamp("2026-11-05") not in df.index:
        df.loc[pd.Timestamp("2026-11-05")] = [5580.09, 5586.46, 5336.88, 5383.80, 0]
    return df.sort_index()

PATCH_1105 = {"EWY": 131.65, "KORU": 6.53, "SPY": 733.00, "QQQ": 647.05, "SOXX": 131.90, "MU": 656.39, "SKHY": 123.90}

def hl(sym, tz):
    df = pd.read_pickle(H / f"h_{safe(sym)}.pkl")
    df.index = df.index.tz_convert(tz)
    return df[["Open", "High", "Low", "Close", "Volume"]]

def m1(sym):
    df = pd.read_csv(D / f"fc_m1_{safe(sym)}.csv", index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Asia/Seoul")
    return df

def summ(x, pct=True):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return {"n": 0}
    m = 100 if pct else 1
    q = lambda p: round(float(x.quantile(p) * m), 2)
    return {"n": int(len(x)), "up": round(float((x > 0).mean() * 100), 1), "mean": round(float(x.mean() * m), 2),
            "median": q(.5), "p05": q(.05), "p10": q(.10), "q25": q(.25), "q75": q(.75), "p90": q(.90), "p95": q(.95),
            "min": round(float(x.min() * m), 2), "max": round(float(x.max() * m), 2)}

def ols(y, X, names):
    y = np.asarray(y, float); X = np.asarray(X, float)
    if X.ndim == 1: X = X.reshape(-1, 1)
    X1 = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ b
    r2 = 1 - (res @ res) / ((y - y.mean()) ** 2).sum()
    return {"n": int(len(y)), "r2": round(float(r2), 3), "coef": {k: round(float(v), 3) for k, v in zip(["const"] + names, b)},
            "resid_sd": round(float(res.std(ddof=X1.shape[1])), 3)}

def dump(obj, name):
    (D / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
