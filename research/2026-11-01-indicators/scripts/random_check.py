"""How good can a RANDOM signal look? Reference distribution for the data-mining problem.
For each template/instrument, draw random signal sets with the same frequency p and compute the 10-year total after fees."""
import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Backtester, trades_for, net
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bt = Backtester(os.path.join(here, "data")); rng = np.random.default_rng(1)
n = len(bt.idx); rows = []
for inst in ("SOXL", "SOXS"):
    O, C = bt.px[inst]
    for tpl in ("OC", "OO", "CC", "CO", "O3C", "O5C"):
        if tpl in ("O3C", "O5C"):
            base = None
        else:
            ei, ep, xi, xp = trades_for(np.ones(n, dtype=bool), tpl, O, C)
            base = np.full(n, np.nan); base[ei - (0 if tpl in ("CC", "CO") else 1)] = np.log1p(net(ep, xp))  # per signal-day log return
            base = np.nan_to_num(base)
        for p in (0.05, 0.10, 0.20, 0.40):
            if base is None and p > 0.2: continue
            tot = []
            for _ in range(4000 if base is not None else 1500):
                s = rng.random(n) < p
                if base is None:
                    ei, ep, xi, xp = trades_for(s, tpl, O, C); tot.append(np.exp(np.log1p(net(ep, xp)).sum()) - 1)
                else:
                    tot.append(np.exp((base * s).sum()) - 1)
            tot = 100 * np.array(tot)
            rows.append(dict(inst=inst, tpl=tpl, p=p, n_trades=int(p * n), median=round(np.median(tot), 1), p95=round(np.percentile(tot, 95), 1),
                             p99=round(np.percentile(tot, 99), 1), p999=round(np.percentile(tot, 99.9), 1), best=round(tot.max(), 1)))
df = pd.DataFrame(rows); pd.set_option("display.width", 200)
print(df.to_string(index=False)); df.to_csv(os.path.join(here, "data", "random_reference.csv"), index=False)
