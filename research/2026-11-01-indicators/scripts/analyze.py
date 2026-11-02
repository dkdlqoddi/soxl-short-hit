import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, numpy as np, pandas as pd
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
S = pd.read_csv(os.path.join(here, "data", "singles.csv")); P = pd.read_csv(os.path.join(here, "data", "pairs.csv"))
cols = ["label", "tpl", "inst", "n", "win", "avg", "pf", "total", "cagr", "mdd", "sharpe", "tstat", "is_total", "oos_total", "pos_years", "worst_year"]
print("=== baselines (no condition) ===")
print(S[S.a == "ALL"][cols].to_string(index=False))
print("\n=== share of strategies with CAGR>0 after fees: singles %.1f%%, pairs %.1f%%" % (100 * (S.cagr > 0).mean(), 100 * (P.cagr > 0).mean()))
robust = lambda d: d[(d.n >= 50) & (d.is_total > 0) & (d.oos_total > 0)]
print("\n=== top singles by CAGR, n>=50, IS>0 & OOS>0 ===")
for inst in ("SOXL", "SOXS"):
    d = robust(S[(S.inst == inst) & (S.a != "ALL")]).sort_values("cagr", ascending=False).head(15)
    print(f"--- {inst}"); print(d[cols].to_string(index=False))
print("\n=== top pairs by CAGR, n>=50, IS>0 & OOS>0, non-redundant ===")
PR = P[~P.redundant]
for inst in ("SOXL", "SOXS"):
    d = robust(PR[PR.inst == inst]).sort_values("cagr", ascending=False).head(25)
    print(f"--- {inst}"); print(d[cols].to_string(index=False))
print("\n=== top pairs by Sharpe (same filter) ===")
for inst in ("SOXL", "SOXS"):
    d = robust(PR[PR.inst == inst]).sort_values("sharpe", ascending=False).head(10)
    print(f"--- {inst}"); print(d[cols].to_string(index=False))
print("\n=== best per template (pairs+singles, robust) ===")
A = pd.concat([S[S.a != "ALL"], PR]); AR = robust(A)
print(AR.sort_values("cagr", ascending=False).groupby(["tpl", "inst"]).head(1).sort_values(["tpl", "inst"])[cols].to_string(index=False))
print("\n=== IS-selected top 30 (by IS total, n>=50) and how they did OOS ===")
d = A[A.n >= 50].sort_values("is_total", ascending=False).head(30)
print(d[["label", "tpl", "inst", "n", "is_total", "oos_total", "cagr", "mdd"]].to_string(index=False))
print("OOS positive among IS-top30: %d/30; median OOS %.1f%%" % ((d.oos_total > 0).sum(), d.oos_total.median()))
d = A[A.n >= 50].sort_values("is_total", ascending=False).head(200)
print("IS-top200: OOS positive %d/200, median OOS %.1f%%, median IS %.1f%%" % ((d.oos_total > 0).sum(), d.oos_total.median(), d.is_total.median()))
print("\n=== t-stat distribution (all with n>=50): max %.2f, >4: %d, >3: %d of %d" % (A[A.n >= 50].tstat.max(), (A[A.n >= 50].tstat > 4).sum(), (A[A.n >= 50].tstat > 3).sum(), (A.n >= 50).sum()))
print(A[A.n >= 50].sort_values("tstat", ascending=False).head(15)[cols].to_string(index=False))
AR.sort_values("cagr", ascending=False).to_csv(os.path.join(here, "data", "robust_ranked.csv"), index=False)
