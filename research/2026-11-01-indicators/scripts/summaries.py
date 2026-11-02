import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, numpy as np, pandas as pd
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 50)
S = pd.read_csv(os.path.join(here, "data", "singles.csv")); P = pd.read_csv(os.path.join(here, "data", "pairs.csv"))
S1 = S[S.a != "ALL"]
print("=== singles by category (SOXL): share of condition×template with CAGR>0, best ===")
rows = []
for inst in ("SOXL", "SOXS"):
    for cat, g in S1[S1.inst == inst].groupby("cat"):
        b = g.sort_values("cagr", ascending=False).iloc[0]
        rb = g[(g.n >= 50) & (g.is_total > 0) & (g.oos_total > 0)]
        rows.append(dict(inst=inst, cat=cat, n_conds=g.a.nunique(), tests=len(g), pos_pct=round(100 * (g.cagr > 0).mean(), 1), robust=len(rb),
                         best=b.label, best_tpl=b.tpl, best_cagr=b.cagr, best_mdd=b.mdd, best_n=b.n, best_oos=b.oos_total))
cat = pd.DataFrame(rows); print(cat.to_string(index=False)); cat.to_csv(os.path.join(here, "data", "summary_by_category.csv"), index=False)
print("\n=== by template (singles+pairs, SOXL): share CAGR>0, median CAGR, robust count ===")
A = pd.concat([S1, P[~P.redundant]])
rows = []
for inst in ("SOXL", "SOXS"):
    for tpl, g in A[A.inst == inst].groupby("tpl"):
        rb = g[(g.n >= 50) & (g.is_total > 0) & (g.oos_total > 0)]
        rows.append(dict(inst=inst, tpl=tpl, tests=len(g), pos_pct=round(100 * (g.cagr > 0).mean(), 1), median_cagr=g.cagr.median(), robust=len(rb), robust_pct=round(100 * len(rb) / len(g), 1)))
tp = pd.DataFrame(rows); print(tp.to_string(index=False)); tp.to_csv(os.path.join(here, "data", "summary_by_template.csv"), index=False)
print("\n=== representative trend / momentum singles (SOXL): best template and SIG ===")
keys = ["C>SMA20", "C>SMA50", "C>SMA200", "SMA5>SMA20", "SMA20>SMA50", "SMA50>SMA200", "EMA9>EMA21", "EMA9xUp", "MACD>Sig", "MACDxUp", "ADX>25up", "C>HH20", "C>HH55", "RSI14>60", "RSI14>70", "RSI2>90", "C>BBup", "up2", "up3", "ret>+5%", "CLV>0.8", "SOXX>SMA200"]
rows = []
for k in keys:
    g = S1[(S1.a == k) & (S1.inst == "SOXL")]
    if g.empty: continue
    b = g.sort_values("cagr", ascending=False).iloc[0]; sg = g[g.tpl == "SIG"]
    rows.append(dict(cond=b.label, best_tpl=b.tpl, best_cagr=b.cagr, best_mdd=b.mdd, best_n=b.n, best_oos=b.oos_total,
                     sig_cagr=sg.cagr.iloc[0] if len(sg) else np.nan, sig_mdd=sg.mdd.iloc[0] if len(sg) else np.nan, sig_n=sg.n.iloc[0] if len(sg) else np.nan))
tr = pd.DataFrame(rows); print(tr.to_string(index=False)); tr.to_csv(os.path.join(here, "data", "summary_trend_singles.csv"), index=False)
print("\n=== representative mean-reversion singles (SOXL): best template ===")
keys = ["RSI2<10", "RSI2<25", "RSI14<30", "RSI14<40", "C<BBlo", "%B<0.2", "StochK<20", "StochxUp", "CCI<-100", "ret<-5%", "ret<-8%", "down2", "down3", "CLV<0.2", "dev<-10%", "gap<-2%", "gap<-4%", "VIX>25", "VIX↑10%", "Vol>1.5x", "C<SMA5", "C<SMA10"]
rows = []
for k in keys:
    g = S1[(S1.a == k) & (S1.inst == "SOXL")]
    if g.empty: continue
    b = g.sort_values("cagr", ascending=False).iloc[0]
    rows.append(dict(cond=b.label, best_tpl=b.tpl, n=b.n, win=b.win, avg=b.avg, cagr=b.cagr, mdd=b.mdd, is_total=b.is_total, oos_total=b.oos_total, tstat=b.tstat))
mr = pd.DataFrame(rows); print(mr.to_string(index=False)); mr.to_csv(os.path.join(here, "data", "summary_meanrev_singles.csv"), index=False)
print("\n=== SOXS singles: best 10 by CAGR (any) ===")
print(S1[S1.inst == "SOXS"].sort_values("cagr", ascending=False).head(10)[["label", "tpl", "n", "win", "avg", "cagr", "mdd", "is_total", "oos_total", "tstat"]].to_string(index=False))
print("\n=== weekday singles (SOXL/SOXS) best templates ===")
w = S1[S1.cat == "달력"].sort_values("cagr", ascending=False).head(10)
print(w[["label", "tpl", "inst", "n", "win", "avg", "cagr", "mdd", "is_total", "oos_total", "tstat"]].to_string(index=False))
