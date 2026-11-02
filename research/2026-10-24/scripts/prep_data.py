import sys, site; sys.path.insert(0, site.getusersitepackages())
import json
import pandas as pd, numpy as np
data = sys.argv[1]; out = sys.argv[2]
with open(f"{data}/nasdaq_soxl.json") as f:
    j = json.load(f)
rows = j["data"]["tradesTable"]["rows"]
def num(s):
    s = str(s).replace(",", "").replace("$", "").strip()
    return float(s) if s not in ("N/A", "", "nan", "None") else np.nan
df = pd.DataFrame([{ "date": pd.to_datetime(r["date"]), "open": num(r["open"]), "high": num(r["high"]),
                     "low": num(r["low"]), "close": num(r["close"]), "volume": num(r["volume"]) } for r in rows])
df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
bad = df[["open","high","low"]].isna().any(axis=1)
print("rows with missing O/H/L:", int(bad.sum()), "dates:", [str(x.date()) for x in df.loc[bad,"date"].head(12)])
for c in ["open","high","low"]: df[c] = df[c].fillna(df["close"])
big = (df.close.pct_change().abs() > 0.5)
print("suspicious |ret|>50% rows (split check):", df.loc[big, ["date","close"]].to_dict("records"))
df.to_csv(f"{out}/soxl_daily_nasdaq.csv", index=False)
print("nasdaq daily:", df.date.min().date(), "->", df.date.max().date(), "rows", len(df))
# cross-check against yfinance daily (unadjusted close)
yf = pd.read_csv(f"{data}/soxl_1d_2y.csv", header=[0,1], index_col=0)
yf.columns = [c[0].lower() for c in yf.columns]
yf.index = pd.to_datetime(yf.index)
m = df.set_index("date").join(yf[["close"]], rsuffix="_yf", how="inner")
print("yf vs nasdaq close max abs diff (2y):", round((m.close - m.close_yf).abs().max(), 4))
# recent rows
d = df.set_index("date").copy()
d["ret"] = d.close.pct_change()*100
d["gap"] = (d.open/d.close.shift(1)-1)*100          # overnight: prev close -> open
d["intra"] = (d.close/d.open-1)*100                 # intraday: open -> close
d["range"] = (d.high-d.low)/d.close.shift(1)*100     # daily range as % of prev close
d["low_vs_pc"] = (d.low/d.close.shift(1)-1)*100     # how far below prev close the low got
d["high_vs_pc"] = (d.high/d.close.shift(1)-1)*100
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 20)
print("\n=== last 20 sessions ===")
print(d.tail(20).round(2).to_string())
def stats(x, name):
    x = x.dropna()
    q = x.quantile([.01,.05,.1,.25,.5,.75,.9,.95,.99])
    print(f"\n--- {name}: n={len(x)} mean={x.mean():.2f} std={x.std():.2f} mean|x|={x.abs().mean():.2f} median|x|={x.abs().median():.2f}")
    print("   pct:", " ".join(f"p{int(k*100)}={v:.1f}" for k,v in q.items()))
for win, lab in [(None,"ALL 10y"), (750,"last ~3y"), (250,"last 1y"), (60,"last 60d")]:
    sub = d if win is None else d.iloc[-win:]
    print(f"\n########## {lab} ##########")
    stats(sub.ret, "daily close-to-close ret %")
    stats(sub.gap, "overnight gap % (prev close->open)")
    stats(sub.intra, "intraday % (open->close)")
    stats(sub.range, "daily high-low range % of prev close")
    stats(sub.low_vs_pc, "low vs prev close %")
    r = sub.ret.dropna()
    print(f"   days |ret|>5%: {(r.abs()>5).mean()*100:.1f}%  >10%: {(r.abs()>10).mean()*100:.1f}%  >15%: {(r.abs()>15).mean()*100:.1f}%  worst={r.min():.1f} best={r.max():.1f}")
    print(f"   share of |ret| <= 0.5% (fee band): {(r.abs()<=0.5).mean()*100:.1f}%   up days: {(r>0).mean()*100:.1f}%")
# worst days list
print("\n=== 15 worst days (10y) ===")
print(d.ret.nsmallest(15).round(2).to_string())
print("\n=== Oct 2026 ===")
print(d.loc["2026-09-25":].round(2).to_string())
d.to_csv(f"{out}/soxl_daily_features.csv")
