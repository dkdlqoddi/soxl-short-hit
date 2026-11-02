"""Build the Strategy Tester confirmation job list from the screening CSVs.

Usage: python3 make_jobs.py <analysis_dir> <jobs.json> [tfs=15,30,60,120] [topn=12]
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os, json
import pandas as pd

MIN_TRADES = 30


def main():
    adir, out = sys.argv[1], sys.argv[2]
    tfs = (sys.argv[3] if len(sys.argv) > 3 else "15,30,60,120").split(",")
    topn = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    jobs, seen = [], set()
    jid = [0]

    def add(tf, r, label, params=None, start=None):
        key = (tf, int(r.buy_a), int(r.buy_b), int(r.sell_a), int(r.sell_b), json.dumps(params or {}, sort_keys=True))
        if key in seen:
            return
        seen.add(key)
        jid[0] += 1
        j = dict(id=jid[0], tf=tf, buyA=int(r.buy_a), buyB=int(r.buy_b), sellA=int(r.sell_a), sellB=int(r.sell_b), label=label,
                 screen_net_pct=round(float(r.net_pct), 1), screen_trades=int(r.trades))
        if params:
            j["params"] = params
        if start:
            j["start"] = start
        jobs.append(j)

    for tf in tfs:
        fp = os.path.join(adir, f"screen_{tf}.csv")
        if not os.path.exists(fp):
            continue
        df = pd.read_csv(fp)
        ok = df[df.trades >= MIN_TRADES].sort_values("net_mult", ascending=False)
        start = "2025-11-01T00:00:00-0400" if tf == "5" else None
        for i, r in enumerate(ok.head(topn).itertuples()):
            add(tf, r, f"top{i + 1}", start=start)
        # best exit of the most robust buy variants, best entry of the most robust sell variants
        rb = pd.read_csv(os.path.join(adir, f"robust_buy_{tf}.csv")).head(6)
        for i, bv in enumerate(rb.bv):
            sub = ok[ok.bv == bv].head(1)
            for r in sub.itertuples():
                add(tf, r, f"robustbuy{i + 1}", start=start)
        rs = pd.read_csv(os.path.join(adir, f"robust_sell_{tf}.csv")).head(5)
        for i, sv in enumerate(rs.sv):
            sub = ok[ok.sv == sv].head(1)
            for r in sub.itertuples():
                add(tf, r, f"robustsell{i + 1}", start=start)
        # best risk-adjusted (Calmar) with >= 50 trades
        cal = ok[(ok.net_pct > 0) & (ok.trades >= 50)].sort_values("calmar", ascending=False).head(5)
        for i, r in enumerate(cal.itertuples()):
            add(tf, r, f"calmar{i + 1}", start=start)
        for nb in (1, 2):
            for ns in (1, 2):
                sub = ok[(ok.n_buy == nb) & (ok.n_sell == ns)].head(2)
                for i, r in enumerate(sub.itertuples()):
                    add(tf, r, f"best_{nb}buy_{ns}sell_{i + 1}", start=start)
        # baselines: first-hour entry with EOD exit (open->close day trade) and with the 24h cap only via a never-triggering-ish exit
        for (ba, bb, sa, sb, lab) in [(17, -1, 19, -1, "baseline_firsthour_EOD"), (17, -1, 18, -1, "baseline_firsthour_4h"), (16, -1, 14, -1, "baseline_CLV_TP3"), (19, -1, 19, -1, "baseline_drop2_EOD")]:
            r = df[(df.buy_a == ba) & (df.buy_b == bb) & (df.sell_a == sa) & (df.sell_b == sb)]
            if len(r):
                add(tf, r.iloc[0], lab, start=start)
        # parameter neighbours for the top 3 by net and the top 2 by Calmar
        neigh = pd.concat([ok.head(3), cal.head(2)]).drop_duplicates(subset=["k"]) if "k" in ok.columns else ok.head(3)
        for i, r in enumerate(neigh.itertuples()):
            sells = {int(r.sell_a), int(r.sell_b)}
            variants = [dict(maxHrs=8.0), dict(maxHrs=48.0)]
            if 14 in sells:
                variants += [dict(tpPct=2.0), dict(tpPct=4.0), dict(tpPct=5.0)]
            if 15 in sells:
                variants += [dict(slPct=1.5), dict(slPct=3.0)]
            if 16 in sells:
                variants += [dict(trPct=1.0), dict(trPct=3.0)]
            if 17 in sells:
                variants += [dict(chMult=1.5), dict(chMult=3.0)]
            if 18 in sells:
                variants += [dict(holdHrs=2.0), dict(holdHrs=6.0)]
            for v in variants:
                add(tf, r, f"top{i + 1}_var_" + "_".join(f"{k}{val}" for k, val in v.items()), params=v, start=start)
    json.dump(jobs, open(out, "w"), indent=1)
    print(f"{len(jobs)} jobs -> {out}")
    print(pd.DataFrame(jobs).groupby("tf").size())


if __name__ == "__main__":
    main()
