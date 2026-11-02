"""Detail for the shortlisted rules: yearly returns, 1/3 position size, parameter neighbours, equity curves for charts."""
import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Backtester, sma, rsi, atr, adx, run_length, net
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bt = Backtester(os.path.join(here, "data")); idx = bt.idx; n = len(idx)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
RULES = [
    ("A", ["CLV<0.2", "ATRhi"], "CC", "SOXL", "저가 근처 마감 & 변동성 큼 → 종가 매수, 다음날 종가 매도"),
    ("B", ["RSI2<25", "ret<-8%"], "CC", "SOXL", "RSI(2)<25 & 당일 -8% → 종가 매수, 다음날 종가 매도"),
    ("C", ["down2", "gap<-2%"], "O5C", "SOXL", "2일 연속 하락 & 시가 갭 -2% → 시가 매수, 5일째 종가 매도"),
    ("D", ["RSI2<25"], "SIG", "SOXL", "RSI(2)<25 → 다음날 시가 매수, 25 이상 되면 다음날 시가 매도"),
    ("E", ["ADX>25dn", "CLV<0.2"], "CC", "SOXL", "하락 추세(ADX) & 저가 근처 마감 → 종가 매수, 다음날 종가 매도"),
    ("F", ["RSI14<40", "ret<-8%"], "OC", "SOXL", "RSI(14)<40 & 당일 -8% → 다음날 시가 매수, 당일 종가 매도(데이트레이드)"),
    ("G", ["CLV<0.2"], "CC", "SOXL", "저가 근처 마감 → 종가 매수, 다음날 종가 매도 (단일 조건)"),
    ("S", ["ret>+8%", "ATRhi"], "CC", "SOXS", "당일 +8% & 변동성 큼 → 종가 SOXS 매수, 다음날 종가 매도"),
]
def metrics_from_lr(lr, f):
    dr = np.expm1(lr) * f; eq = np.cumprod(1 + dr); total = eq[-1] - 1
    dd = (eq / np.maximum.accumulate(eq) - 1).min()
    yrs = pd.Series(np.log1p(dr), index=idx).groupby(idx.year).sum()
    return dict(total=round(100 * total, 1), cagr=round(100 * ((1 + total) ** (1 / bt.years) - 1), 1), mdd=round(100 * dd, 1),
                sharpe=round(dr.mean() / dr.std() * np.sqrt(252), 2), yearly={int(y): round(100 * (np.exp(v) - 1), 1) for y, v in yrs.items()}), eq
curves = {}; rows = []; yearly = {}
for tag, keys, tpl, inst, desc in RULES:
    r = bt.run(keys, tpl, inst, keep=True)
    m1, eq1 = metrics_from_lr(r["lr"], 1.0); m3, eq3 = metrics_from_lr(r["lr"], 1 / 3)
    curves[f"{tag}"] = eq1; yearly[tag] = m1["yearly"]
    rows.append(dict(tag=tag, rule=desc, tpl=tpl, inst=inst, n=r["n"], win=r["win"], avg=r["avg"], pf=r["pf"], total=m1["total"], cagr=m1["cagr"], mdd=m1["mdd"],
                     sharpe=m1["sharpe"], tstat=r["tstat"], is_total=r["is_total"], oos_total=r["oos_total"], expo=r["expo"],
                     total_1_3=m3["total"], cagr_1_3=m3["cagr"], mdd_1_3=m3["mdd"]))
res = pd.DataFrame(rows); print(res.to_string(index=False)); res.to_csv(os.path.join(here, "data", "shortlist.csv"), index=False)
Y = pd.DataFrame(yearly).T; print("\nyearly % (full position):\n", Y.to_string())
Y.to_csv(os.path.join(here, "data", "shortlist_yearly.csv"))
# buy & hold and 'every day' baselines for the chart
O, C = bt.px["SOXL"]; curves["SOXL 보유"] = C / C[0]
r = bt.run(["ALL"], "OC", "SOXL", keep=True); curves["매일 시가→종가"] = np.exp(np.cumsum(r["lr"]))
pd.DataFrame(curves, index=idx).to_csv(os.path.join(here, "data", "shortlist_equity.csv"))
# ---- parameter neighbours (custom thresholds) ----
df = bt.soxl; Cc, Oo, Hh, Ll = df.close, df.open, df.high, df.low
full = bt.full; m = full.index.isin(idx)
clv_full = ((full.close - full.low) / (full.high - full.low)); clv = clv_full[m].to_numpy()
ret = full.close.pct_change()[m].to_numpy(); r2 = rsi(full.close, 2)[m].to_numpy(); r14 = rsi(full.close, 14)[m].to_numpy()
a14 = (atr(full, 14) / full.close); atr_med100 = (a14 > a14.rolling(100).median())[m].to_numpy(); atr_med60 = (a14 > a14.rolling(60).median())[m].to_numpy(); atr_med150 = (a14 > a14.rolling(150).median())[m].to_numpy()
gap = (full.open.shift(-1) / full.close - 1)[m].to_numpy(); dn = run_length(full.close.pct_change() < 0)[m].to_numpy()
ad, pdi, mdi = adx(full); adxdn = ((ad > 25) & (mdi > pdi))[m].to_numpy(); adxdn20 = ((ad > 20) & (mdi > pdi))[m].to_numpy()
nb = []
def add(name, sig, tpl, inst):
    r = bt.run_sig(sig, tpl, inst)
    if r: nb.append(dict(variant=name, tpl=tpl, inst=inst, n=r["n"], win=r["win"], avg=r["avg"], total=r["total"], cagr=r["cagr"], mdd=r["mdd"], tstat=r["tstat"], is_total=r["is_total"], oos_total=r["oos_total"]))
for th in (0.1, 0.2, 0.3, 0.4):
    add(f"A: CLV<{th} & ATR>100일중앙값", (clv < th) & atr_med100, "CC", "SOXL")
add("A: CLV<0.2 & ATR>60일중앙값", (clv < 0.2) & atr_med60, "CC", "SOXL"); add("A: CLV<0.2 & ATR>150일중앙값", (clv < 0.2) & atr_med150, "CC", "SOXL")
for rt in (-0.05, -0.06, -0.08, -0.10):
    for rs in (10, 25, 35):
        add(f"B: RSI2<{rs} & ret<{int(rt*100)}%", (r2 < rs) & (ret < rt), "CC", "SOXL")
for g in (-0.01, -0.02, -0.03, -0.04):
    for d in (1, 2, 3):
        add(f"C: down>={d} & gap<{int(g*100)}%", (dn >= d) & (gap < g), "O5C", "SOXL")
for rs in (10, 15, 25, 35):
    add(f"D: RSI2<{rs} SIG", r2 < rs, "SIG", "SOXL")
add("E: ADX>20dn & CLV<0.2", adxdn20 & (clv < 0.2), "CC", "SOXL"); add("E: ADX>25dn & CLV<0.3", adxdn & (clv < 0.3), "CC", "SOXL")
for rs in (30, 40, 50):
    for rt in (-0.05, -0.08, -0.10):
        add(f"F: RSI14<{rs} & ret<{int(rt*100)}%", (r14 < rs) & (ret < rt), "OC", "SOXL")
for rt in (0.05, 0.06, 0.08, 0.10):
    add(f"S: ret>+{int(rt*100)}% & ATR>100일중앙값", (ret > rt) & atr_med100, "CC", "SOXS")
NB = pd.DataFrame(nb); print("\nneighbours:\n", NB.to_string(index=False)); NB.to_csv(os.path.join(here, "data", "shortlist_neighbours.csv"), index=False)
