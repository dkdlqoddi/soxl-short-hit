import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, itertools, time, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Backtester, TEMPLATES
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bt = Backtester(os.path.join(here, "data"))
print("bars", len(bt.idx), bt.idx[0].date(), bt.idx[-1].date(), "years", round(bt.years, 2), "conditions", len(bt.conds))
t0 = time.time(); rows = []
keys = list(bt.conds)
for k in keys:
    for tpl in TEMPLATES:
        for inst in ("SOXL", "SOXS"):
            r = bt.run([k], tpl, inst)
            if r: rows.append(dict(kind="single", a=k, b="", label=bt.conds[k]["label"], cat=bt.conds[k]["cat"], tpl=tpl, inst=inst, **{x: v for x, v in r.items() if x != "yearly"}))
singles = pd.DataFrame(rows); singles.to_csv(os.path.join(here, "data", "singles.csv"), index=False)
print("singles", len(singles), round(time.time() - t0, 1), "s")
t0 = time.time(); rows = []
pk = [k for k in keys if bt.conds[k]["pairs"]]
n_single = {(r.a, r.tpl, r.inst): r.n for r in singles.itertuples()}
for a, b in itertools.combinations(pk, 2):
    if bt.conds[a]["cat"] == bt.conds[b]["cat"] and bt.conds[a]["cat"] in ("추세",) and a.split("SMA")[0] == b.split("SMA")[0] and False: pass
    sig = bt.signal([a, b])
    if sig.sum() < 30: continue
    for tpl in TEMPLATES:
        for inst in ("SOXL", "SOXS"):
            r = bt.run([a, b], tpl, inst)
            if not r or r["n"] < 30: continue
            na, nb = n_single.get((a, tpl, inst), 0), n_single.get((b, tpl, inst), 0)
            red = r["n"] >= 0.97 * min(na, nb) if min(na, nb) > 0 else False
            rows.append(dict(kind="pair", a=a, b=b, label=bt.conds[a]["label"] + " & " + bt.conds[b]["label"], cat=bt.conds[a]["cat"] + "+" + bt.conds[b]["cat"],
                             tpl=tpl, inst=inst, redundant=red, **{x: v for x, v in r.items() if x != "yearly"}))
pairs = pd.DataFrame(rows); pairs.to_csv(os.path.join(here, "data", "pairs.csv"), index=False)
print("pairs", len(pairs), round(time.time() - t0, 1), "s")
