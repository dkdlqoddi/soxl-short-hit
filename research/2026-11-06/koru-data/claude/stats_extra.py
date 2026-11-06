"""KORU 2026-11-05 회차 복기 — 보조 통계 (Claude Fable Max).
 E1 외국인 순매도와 다음 날 코스피   E2 2026년 코스피 급락 기저율(갭 조건부)   E3 미국장 2요인식 강건성
 E4 고변동 구간의 24시간 분포   E5 한국장·미국장 동반 급락 빈도   E6 EWY −10% 이하 폭락일 다음 날
실행: python3 stats_extra.py → stats_extra.json
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
H = D / "hist"
OUT = {}
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)

def dl(sym, tz):
    df = pd.read_pickle(H / f"d_{sym}.pkl")
    idx = df.index.tz_convert(tz) if df.index.tz is not None else df.index
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(idx.strftime("%Y-%m-%d"))
    return df[~df.index.duplicated(keep="last")]

def summ(x):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return {"n": 0}
    return {"n": int(len(x)), "up": round(float((x > 0).mean() * 100), 1), "mean": round(float(x.mean() * 100), 2), "median": round(float(x.median() * 100), 2),
            "p10": round(float(x.quantile(.1) * 100), 2), "q25": round(float(x.quantile(.25) * 100), 2), "q75": round(float(x.quantile(.75) * 100), 2), "min": round(float(x.min() * 100), 2)}

def ols(y, X, names):
    y = np.asarray(y, float); X = np.asarray(X, float)
    if X.ndim == 1: X = X.reshape(-1, 1)
    X1 = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ b
    return {"n": int(len(y)), "r2": round(float(1 - (res @ res) / ((y - y.mean()) ** 2).sum()), 3), "coef": {k: round(float(v), 3) for k, v in zip(["const"] + names, b)}, "resid_sd": round(float(res.std(ddof=X1.shape[1])), 3)}

ewy, koru, spy, soxx, sox, mu = (dl(s, "America/New_York") for s in ["EWY", "KORU", "SPY", "SOXX", "SOX", "MU"])
for _df, _c in [(ewy, 131.65), (koru, 6.53), (spy, 733.00), (soxx, 131.90), (mu, 656.39)]:
    if pd.isna(_df.loc["2026-11-05", "Close"]):
        _df.loc["2026-11-05", "Close"] = _c
ks = dl("KS11", "Asia/Seoul")
ks.loc[pd.Timestamp("2026-11-05")] = [5580.09, 5586.46, 5336.88, 5383.80, 0]
ks = ks.sort_index().loc[:"2026-11-05"]
ks["r"] = ks["Close"].pct_change(fill_method=None)
ks["gap"] = ks["Open"] / ks["Close"].shift(1) - 1
ks["oc"] = ks["Close"] / ks["Open"] - 1
ks["next_r"] = ks["r"].shift(-1)
ks["next_gap"] = ks["gap"].shift(-1)

# ---------------------------------------------------------------- E1 외국인 순매도
fl = pd.read_csv(D / "kospi_investor_flows.csv", dtype={"date": str})
fl.index = pd.to_datetime(fl["date"]); fl = fl.drop(columns="date")
f = fl.join(ks[["r", "gap", "oc", "next_r", "next_gap"]], how="left")
f["foreign_next"] = f["foreign"].shift(-1)
f["sell_streak"] = 0
st = 0
for i, v in enumerate(f["foreign"].values):
    st = st + 1 if v < 0 else 0
    f.iloc[i, f.columns.get_loc("sell_streak")] = st
E1 = {"period": f"{f.index[0].date()}~{f.index[-1].date()}", "n_days": int(len(f)),
      "recent": {str(i.date()): {"foreign": int(v["foreign"]), "individual": int(v["individual"]), "institution": int(v["institution"]), "kospi_r": round(float(v["r"] * 100), 2), "streak": int(v["sell_streak"])} for i, v in f.tail(6).iterrows()},
      "rank_1105_foreign_sell": int((f["foreign"] <= f.loc["2026-11-05", "foreign"]).sum()),
      "top_sell_days": {str(i.date()): [int(v["foreign"]), round(float(v["r"] * 100), 2), round(float(v["next_r"] * 100), 2) if pd.notna(v["next_r"]) else None] for i, v in f.nsmallest(12, "foreign").iterrows()}}
print("E1 최근:", json.dumps(E1["recent"], ensure_ascii=False))
print("   11/5 순매도 순위:", E1["rank_1105_foreign_sell"], "/", len(f))
print("   순매도 상위 12일 [외국인(억원), 당일 코스피%, 다음 날 코스피%]:", json.dumps(E1["top_sell_days"], ensure_ascii=False))
f0 = f.loc[:"2026-11-04"]
conds = {"외국인 순매도 2조 이상": f0["foreign"] <= -20000, "외국인 순매도 1.5조 이상": f0["foreign"] <= -15000, "외국인 순매도 1조 이상": f0["foreign"] <= -10000,
         "순매도 1.5조 이상 & 코스피 상승 마감 (11/4형)": (f0["foreign"] <= -15000) & (f0["r"] > 0),
         "순매도 1조 이상 & 코스피 상승 마감": (f0["foreign"] <= -10000) & (f0["r"] > 0),
         "순매도 1조 이상이 2일 연속이고 둘째 날이 더 큼 (11/3→11/4형)": (f0["foreign"] <= -10000) & (f0["foreign"].shift(1) <= -10000) & (f0["foreign"] < f0["foreign"].shift(1)),
         "순매도 연속 3일 이상째 & 당일 1조 이상": (f0["sell_streak"] >= 3) & (f0["foreign"] <= -10000),
         "전체": f0["foreign"].notna()}
for label, m in conds.items():
    s = f0[m]
    E1[label] = {"다음 날 코스피": summ(s["next_r"]), "다음 날 시가 갭": summ(s["next_gap"]), "다음 날도 외국인 순매도 %": round(float((s["foreign_next"] < 0).mean() * 100), 1) if len(s) else None,
                 "다음 날 코스피 −3% 이하 %": round(float((s["next_r"] <= -0.03).mean() * 100), 1) if len(s) else None}
    print("  ", label, json.dumps(E1[label], ensure_ascii=False))
OUT["E1"] = E1

# ---------------------------------------------------------------- E2 2026년 코스피 급락 기저율
E2 = {}
for label, sub in [("2026년 (~11/4)", ks.loc["2026-01-01":"2026-11-04"]), ("2025년", ks.loc["2025-01-01":"2025-12-31"]), ("2010~2025년", ks.loc["2010-01-01":"2025-12-31"])]:
    s = sub.dropna(subset=["r"])
    g = s[s["gap"] <= -0.015]
    E2[label] = {"n": int(len(s)), "종가 −3.5% 이하 %": round(float((s["r"] <= -0.035).mean() * 100), 1), "종가 −5% 이하 %": round(float((s["r"] <= -0.05).mean() * 100), 1),
                 "종가 −3.5% 이하 일수": int((s["r"] <= -0.035).sum()), "종가 −5% 이하 일수": int((s["r"] <= -0.05).sum()),
                 "갭 −1.5% 이하": {"n": int(len(g)), "종가 −2% 이하 %": round(float((g["r"] <= -0.02).mean() * 100), 1) if len(g) else None, "종가 −3.5% 이하 %": round(float((g["r"] <= -0.035).mean() * 100), 1) if len(g) else None,
                                 "종가 −5% 이하 %": round(float((g["r"] <= -0.05).mean() * 100), 1) if len(g) else None, "종가 −1.1% 초과 %": round(float((g["r"] > -0.011).mean() * 100), 1) if len(g) else None,
                                 "종가": summ(g["r"]), "시가→종가": summ(g["oc"])}}
    g2 = s[(s["gap"] <= -0.015) & (s["gap"] > -0.025)]
    E2[label]["갭 −1.5~−2.5% (11/5형 −1.82%)"] = {"n": int(len(g2)), "종가 −1.1% 초과 %": round(float((g2["r"] > -0.011).mean() * 100), 1) if len(g2) else None, "종가 −2% 이하 %": round(float((g2["r"] <= -0.02).mean() * 100), 1) if len(g2) else None,
                                                "종가 −3.5% 이하 %": round(float((g2["r"] <= -0.035).mean() * 100), 1) if len(g2) else None, "종가 −5% 이하 %": round(float((g2["r"] <= -0.05).mean() * 100), 1) if len(g2) else None, "종가": summ(g2["r"])}
    print("E2", label, json.dumps(E2[label], ensure_ascii=False))
OUT["E2"] = E2

# ---------------------------------------------------------------- E3 미국장 2요인식 강건성 (2026년)
u = pd.DataFrame({"ewy_oc": ewy["Close"] / ewy["Open"] - 1, "soxx_oc": soxx["Close"] / soxx["Open"] - 1, "spy_oc": spy["Close"] / spy["Open"] - 1}).dropna()
r5 = u.loc["2026-11-05"]
E3 = {}
for label, sub in [("2026 전체(~11/4)", u.loc["2026-01-01":"2026-11-04"]), ("2026, SOXX 시가→종가 −5% 이하 제외", u.loc["2026-01-01":"2026-11-04"][lambda d: d["soxx_oc"] > -0.05]),
                   ("2026 하반기(7/1~11/4)", u.loc["2026-07-01":"2026-11-04"]), ("2026 상반기", u.loc["2026-01-01":"2026-06-30"]), ("2025", u.loc["2025-01-01":"2025-12-31"])]:
    two = ols(sub["ewy_oc"] * 100, np.column_stack([sub["soxx_oc"] * 100, sub["spy_oc"] * 100]), ["soxx", "spy"])
    one = ols(sub["ewy_oc"] * 100, sub["soxx_oc"] * 100, ["soxx"])
    E3[label] = {"two": two, "one": one, "pred_1105_two": round(float(two["coef"]["const"] + two["coef"]["soxx"] * r5["soxx_oc"] * 100 + two["coef"]["spy"] * r5["spy_oc"] * 100), 2),
                 "pred_1105_one": round(float(one["coef"]["const"] + one["coef"]["soxx"] * r5["soxx_oc"] * 100), 2), "corr_soxx_spy": round(float(sub["soxx_oc"].corr(sub["spy_oc"])), 2)}
    print("E3", label, json.dumps(E3[label], ensure_ascii=False))
big = u.loc["2010-01-01":"2026-11-05"][lambda d: (d["soxx_oc"] <= -0.05)]
big = big.assign(ratio=big["ewy_oc"] / big["soxx_oc"])
print("   SOXX 시가→종가 −5% 이하인 날 (2010~):"); print(big.mul(100).assign(ratio=big["ratio"]).round(2).to_string())
E3["soxx_oc<=-5%_days"] = {str(i.date()): {c: round(float(v[c] * (1 if c == "ratio" else 100)), 2) for c in big.columns} for i, v in big.iterrows()}
OUT["E3"] = E3

# ---------------------------------------------------------------- E4 고변동 구간의 24시간 분포
kh = pd.read_pickle(H / "h_KORU.pkl"); kh.index = kh.index.tz_convert("America/New_York")
ah = kh[kh.index.hour == 17]["Close"]; ah.index = pd.to_datetime(ah.index.strftime("%Y-%m-%d")); ah = ah[~ah.index.duplicated(keep="last")]
k = koru.copy(); pc = k["Close"].shift(1)
trng = pd.concat([k["High"] - k["Low"], (k["High"] - pc).abs(), (k["Low"] - pc).abs()], axis=1).max(axis=1)
k["atrp"] = trng.rolling(14).mean() / k["Close"]
k["r"] = k["Close"].pct_change(fill_method=None)
a = pd.DataFrame({"ah": ah}).join(k[["Close", "atrp", "r"]], how="inner")
a["ret24"] = a["ah"].shift(-1) / a["ah"] - 1
a["z"] = a["ret24"] / a["atrp"]
a["prem"] = a["ah"] / a["Close"] - 1
_nxt = pd.Series(k.index, index=k.index).shift(-1)
a["next_ok"] = (a.index.to_series().shift(-1) == _nxt.reindex(a.index)) & (a["prem"].abs() <= 0.15) & (a["prem"].shift(-1).abs() <= 0.15)
a.loc[~a["next_ok"], ["ret24", "z"]] = np.nan                  # 연속 거래일만, 오체결 봉(2026-06-24) 제외
a0 = a.dropna(subset=["ret24", "atrp"]).loc[:"2026-11-03"]      # 11/4→11/5 제외
hv = a0[a0["atrp"] >= 0.12]
E4 = {"all(~11/3)": {"n": int(len(a0)), "q": {str(q): round(float(a0["ret24"].quantile(q) * 100), 1) for q in (.01, .025, .05, .10, .90, .95, .975, .99)}},
      "atr>=12%": {"n": int(len(hv)), "q": {str(q): round(float(hv["ret24"].quantile(q) * 100), 1) for q in (.025, .05, .10, .25, .5, .75, .90, .95, .975)}, "summ": summ(hv["ret24"]),
                   "period": f"{hv.index[0].date()}~{hv.index[-1].date()}"},
      "z_q(~11/3)": {str(q): round(float(a0["z"].quantile(q)), 2) for q in (.01, .025, .05, .10, .90, .95, .975, .99)},
      "z<=-2.88 count": int((a0["z"] <= -2.88).sum()), "ret24<=-30% days": {str(i.date()): round(float(v * 100), 1) for i, v in a0["ret24"][a0["ret24"] <= -0.30].items()},
      "ret24<=-20% count": int((a0["ret24"] <= -0.20).sum())}
y26 = k.loc["2026-01-01":"2026-11-04", "r"].dropna()
E4["KORU 일간 2026 (~11/4)"] = {"n": int(len(y26)), "<=-15%": int((y26 <= -0.15).sum()), "<=-20%": int((y26 <= -0.20).sum()), "<=-30%": int((y26 <= -0.30).sum()), ">=+15%": int((y26 >= 0.15).sum()), ">=+20%": int((y26 >= 0.20).sum()),
                                "q": {str(q): round(float(y26.quantile(q) * 100), 1) for q in (.01, .025, .05, .10, .90, .95, .975, .99)}, "sd": round(float(y26.std() * 100), 1)}
yall = k.loc["2013-04-11":"2025-12-31", "r"].dropna()
E4["KORU 일간 2013~2025"] = {"n": int(len(yall)), "<=-15%": int((yall <= -0.15).sum()), "<=-20%": int((yall <= -0.20).sum()), "<=-30%": int((yall <= -0.30).sum()), "sd": round(float(yall.std() * 100), 1)}
print("E4", json.dumps(E4, ensure_ascii=False))
OUT["E4"] = E4

# ---------------------------------------------------------------- E5 동반 급락 빈도 (같은 날짜의 한국장 → 미국장)
x = ks[["r"]].join(pd.DataFrame({"soxx_oc": soxx["Close"] / soxx["Open"] - 1, "sox_r": sox["Close"].pct_change(fill_method=None), "ewy_r": ewy["Close"].pct_change(fill_method=None)}), how="inner")
E5 = {}
for label, sub in [("2026 (~11/4)", x.loc["2026-01-01":"2026-11-04"]), ("2010~2025", x.loc["2010-01-01":"2025-12-31"])]:
    s = sub.dropna()
    kd = s[s["r"] <= -0.03]
    E5[label] = {"n": int(len(s)), "코스피 −3% 이하": int(len(kd)), "그중 같은 밤 SOX −3% 이하": int((kd["sox_r"] <= -0.03).sum()), "그중 같은 밤 SOX −5% 이하": int((kd["sox_r"] <= -0.05).sum()),
                 "SOX −3% 이하 전체": int((s["sox_r"] <= -0.03).sum()), "SOX −5% 이하 전체": int((s["sox_r"] <= -0.05).sum()),
                 "코스피 −3% 이하인 날 밤 SOX": summ(kd["sox_r"]), "그 밖의 날 밤 SOX": summ(s.loc[s["r"] > -0.03, "sox_r"])}
    print("E5", label, json.dumps(E5[label], ensure_ascii=False))
OUT["E5"] = E5

# ---------------------------------------------------------------- E6 EWY −10% 이하 폭락일 다음 날
e = ewy.copy(); e["r"] = e["Close"].pct_change(fill_method=None); e["gap"] = e["Open"] / e["Close"].shift(1) - 1; e["oc"] = e["Close"] / e["Open"] - 1
e["next_r"] = e["r"].shift(-1); e["next_gap"] = e["gap"].shift(-1); e["next_oc"] = e["oc"].shift(-1); e["next_date"] = e.index.to_series().shift(-1)
kr = k["r"]; e["koru_r"] = kr.reindex(e.index); e["koru_next"] = kr.shift(-1).reindex(e.index)
rows = {}
for i, v in e[e["r"] <= -0.09].iterrows():
    nd = v["next_date"]
    kday = ks.index[ks.index > i]           # 폭락한 미국장 뒤에 처음 열리는 한국장
    kn = kday[0] if len(kday) else None
    rows[str(i.date())] = {"ewy": round(float(v["r"] * 100), 1), "koru": round(float(v["koru_r"] * 100), 1) if pd.notna(v["koru_r"]) else None,
                           "다음 한국장": str(kn.date()) if kn is not None else None, "다음 한국장 코스피": round(float(ks.loc[kn, "r"] * 100), 1) if kn is not None and pd.notna(ks.loc[kn, "r"]) else None,
                           "다음 한국장 시가 갭": round(float(ks.loc[kn, "gap"] * 100), 1) if kn is not None and pd.notna(ks.loc[kn, "gap"]) else None,
                           "다음 한국장 시가→종가": round(float(ks.loc[kn, "oc"] * 100), 1) if kn is not None and pd.notna(ks.loc[kn, "oc"]) else None,
                           "다음 미국장 EWY": round(float(v["next_r"] * 100), 1) if pd.notna(v["next_r"]) else None, "EWY 갭": round(float(v["next_gap"] * 100), 1) if pd.notna(v["next_gap"]) else None,
                           "EWY 시가→종가": round(float(v["next_oc"] * 100), 1) if pd.notna(v["next_oc"]) else None, "다음 미국장 KORU": round(float(v["koru_next"] * 100), 1) if pd.notna(v["koru_next"]) else None}
print("E6 EWY −9% 이하인 날과 그다음:")
print(pd.DataFrame(rows).T.to_string())
OUT["E6"] = rows
nx = e[(e["r"] <= -0.09)].loc[:"2026-11-04"]
OUT["E6_summary"] = {"다음 미국장 EWY": summ(nx["next_r"]), "다음 미국장 KORU": summ(nx["koru_next"])}
print("   요약:", json.dumps(OUT["E6_summary"], ensure_ascii=False))
json.dump(OUT, open(D / "stats_extra.json", "w"), ensure_ascii=False, indent=1, default=str)
print("saved stats_extra.json")
