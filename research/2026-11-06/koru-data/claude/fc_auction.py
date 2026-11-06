"""종가 단일가 왜곡 검증: EWY 공식 종가(일봉) vs 15:59 마지막 연속 체결(1시간봉 15시 봉 종가)의 차이가 다음 날 되돌려지는가.
실행: python3 fc_auction.py"""
import numpy as np, pandas as pd
from fc_common import *
NY = "America/New_York"
OUT = {}
for sym in ["EWY", "KORU"]:
    h = hl(sym, NY); d = dl(sym, NY)
    rows = {}
    for day, g in h.groupby(h.index.strftime("%Y-%m-%d")):
        b = g[g.index.hour == 15]
        a = g[(g.index.hour >= 16) & (g.index.hour <= 19)]
        if len(b):
            rows[pd.Timestamp(day)] = {"last_cont": float(b["Close"].iloc[-1]), "ah_last": float(a["Close"].iloc[-1]) if len(a) else np.nan,
                                       "ah_first": float(a["Close"].iloc[0]) if len(a) else np.nan}
    x = pd.DataFrame(rows).T.join(d[["Open", "Close"]], how="inner").loc[:"2026-11-05"]
    x["diff"] = x["Close"] / x["last_cont"] - 1                 # 공식 종가 − 마지막 연속 체결
    x["gap_n"] = x["Open"].shift(-1) / x["Close"] - 1
    x["r_n"] = x["Close"].shift(-1) / x["Close"] - 1
    x["ah1"] = x["ah_first"] / x["Close"] - 1                   # 첫 애프터 1시간봉 종가(16:59) vs 공식 종가
    x["ahl"] = x["ah_last"] / x["Close"] - 1
    v = x.dropna(subset=["diff", "r_n"]).loc[:"2026-11-04"]
    v = v[v["diff"].abs() < 0.05]
    print(f"=== {sym}: N {len(v)}, |diff| 분포(%):", {p: round(float(v['diff'].abs().quantile(p) * 100), 2) for p in (.5, .9, .95, .99)}, "diff ≤ −0.5%:", int((v["diff"] <= -0.005).sum()), "≥ +0.5%:", int((v["diff"] >= 0.005).sum()))
    print("11/5:", {k: (round(float(x.loc['2026-11-05', k]), 4) if pd.notna(x.loc['2026-11-05', k]) else None) for k in ["last_cont", "Close", "diff", "ah_first", "ah_last", "ah1", "ahl"]})
    res = {}
    for lab, y in [("첫 애프터 1시간(16:59) vs 공식 종가", "ah1"), ("마지막 애프터 vs 공식 종가", "ahl"), ("다음 날 시가 갭", "gap_n"), ("다음 날 종가", "r_n")]:
        w = v.dropna(subset=[y])
        o = ols(w[y] * 100, w["diff"] * 100, ["diff"])
        res[lab] = o
        print(f"  {lab} ~ diff: N {o['n']} 기울기 {o['coef']['diff']} 상수 {o['coef']['const']} R² {o['r2']}")
    big = v[v["diff"] <= -0.005]
    print("  diff ≤ −0.5% 인 날 N", len(big), "| 첫 애프터 평균 %.2f%% 중앙값 %.2f%% 상승 %.0f%% | 다음 날 갭 평균 %.2f%% 중앙값 %.2f%% | 다음 날 종가 평균 %.2f%% 상승 %.0f%%" % (
        big["ah1"].mean() * 100, big["ah1"].median() * 100, (big["ah1"] > 0).mean() * 100, big["gap_n"].mean() * 100, big["gap_n"].median() * 100, big["r_n"].mean() * 100, (big["r_n"] > 0).mean() * 100))
    print((big[["last_cont", "Close", "diff", "ah1", "ahl", "gap_n", "r_n"]] * [1, 1, 100, 100, 100, 100, 100]).round(2).tail(25).to_string())
    res["big_neg"] = {"n": int(len(big)), "ah1_mean": round(float(big["ah1"].mean() * 100), 2), "ah1_median": round(float(big["ah1"].median() * 100), 2), "ah1_up": round(float((big["ah1"] > 0).mean() * 100), 1),
                      "gap_mean": round(float(big["gap_n"].mean() * 100), 2), "gap_median": round(float(big["gap_n"].median() * 100), 2), "r_n_mean": round(float(big["r_n"].mean() * 100), 2), "r_n_up": round(float((big["r_n"] > 0).mean() * 100), 1),
                      "diff_mean": round(float(big["diff"].mean() * 100), 2)}
    OUT[sym] = res
dump(OUT, "fc_auction.json")
