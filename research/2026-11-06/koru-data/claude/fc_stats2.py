"""KORU 24h forecast (2026-11-06) 추가 통계 (Claude Fable Max).
 T1 미국 선물·시간외 현재 수준   T2 애프터마켓 마지막 체결 → 다음 날 애프터마켓 마지막 체결(24시간) 분포
 T3 KORU 급락일 사례표(1시간봉)   T4 금요일 애프터마켓 드리프트   T5 코스피 급락일 밤의 EWY
실행: python3 fc_stats2.py"""
import numpy as np, pandas as pd
from fc_common import *

OUT = {}
NY = "America/New_York"
# ---------------------------------------------------------------- T1 선물·시간외
es, nq = m1("ES=F"), m1("NQ=F")
def at(df, ts):
    x = df.loc[:pd.Timestamp(ts, tz="Asia/Seoul")]
    return float(x["Close"].iloc[-1]), x.index[-1].strftime("%m/%d %H:%M")
print("=== T1 선물 (KST)")
for nm, df in [("ES", es), ("NQ", nq)]:
    ref, rt = at(df, "2026-11-06 05:59")       # 미국 현물 마감 직전
    ref2, rt2 = at(df, "2026-11-05 05:59")      # 전일 같은 시각
    row = {"ref_0559": ref, "prev_0559": ref2, "chg_1105_session": round((ref / ref2 - 1) * 100, 2)}
    for t in ["2026-11-06 06:59", "2026-11-06 08:00", "2026-11-06 08:59", "2026-11-06 09:39", "2026-11-06 09:59", "2026-11-06 10:42", "2026-11-06 23:59"]:
        v, vt = at(df, t)
        row[vt] = [v, round((v / ref - 1) * 100, 2)]
    OUT[f"T1_{nm}"] = row
    print(nm, row)
for sym in ["SOXX", "MU", "SPY", "QQQ", "NVDA", "SKHY", "EWY", "KORU"]:
    df = m1(sym)
    c1559, _ = at(df, "2026-11-06 05:59")
    last, lt = at(df, "2026-11-06 10:00")
    lo = df.loc[pd.Timestamp("2026-11-06 06:00", tz="Asia/Seoul"):pd.Timestamp("2026-11-06 10:00", tz="Asia/Seoul")]
    OUT[f"T1_ah_{sym}"] = {"last_regular_1m": c1559, "ah_last": last, "ah_last_t": lt, "ah_vs_1559_pct": round((last / c1559 - 1) * 100, 2), "ah_low": float(lo["Low"].min()), "ah_high": float(lo["High"].max())}
    print(sym, OUT[f"T1_ah_{sym}"])

# ---------------------------------------------------------------- T2 24시간 분포 (1시간봉, 시간외 포함)
kh = hl("KORU", NY); eh = hl("EWY", NY)
koru, ewy, sox = dl("KORU", NY), dl("EWY", NY), dl("^SOX", NY)
ks = dl("^KS11", "Asia/Seoul").loc[:"2026-11-05"]
def last_ah(h):
    """날짜별 애프터마켓(16:00~19:59 ET) 마지막 1시간봉 종가와 그 봉의 시각."""
    out = {}
    for day, g in h.groupby(h.index.strftime("%Y-%m-%d")):
        a = g[(g.index.hour >= 16) & (g.index.hour <= 19)]
        if len(a):
            out[pd.Timestamp(day)] = (float(a["Close"].iloc[-1]), int(a.index[-1].hour))
    return pd.DataFrame(out, index=["px", "hr"]).T
la = last_ah(kh)
d = koru[["Open", "High", "Low", "Close"]].join(la, how="inner")
d = d.loc["2023-12-08":"2026-11-05"]
d["r"] = koru["Close"].pct_change(fill_method=None).reindex(d.index)
d["nxt_px"] = d["px"].shift(-1); d["nxt_hr"] = d["hr"].shift(-1)
d["nxt_day"] = d.index.to_series().shift(-1)
d["ok"] = (d["nxt_day"] - d.index.to_series()).dt.days <= 4
d["r24"] = d["nxt_px"] / d["px"] - 1
d["ah_prem"] = d["px"] / d["Close"] - 1
pcl = koru["Close"].shift(1)
trng = pd.concat([koru["High"] - koru["Low"], (koru["High"] - pcl).abs(), (koru["Low"] - pcl).abs()], axis=1).max(axis=1)
d["atrp"] = (trng.rolling(14).mean() / koru["Close"]).reindex(d.index)
d["sd10"] = koru["Close"].pct_change(fill_method=None).rolling(10).std().reindex(d.index)
v = d[d["ok"] & (d["ah_prem"].abs() < 0.15)].dropna(subset=["r24"]).loc[:"2026-11-04"]
print("\n=== T2 애프터마켓 마지막 체결 → 다음 거래일 애프터마켓 마지막 체결 (N", len(v), ", 마지막 봉 시각 분포", v["hr"].value_counts().to_dict(), ")")
def q(x):
    x = x.dropna()
    return {"n": int(len(x)), "up": round(float((x > 0).mean() * 100), 1), "mean": round(float(x.mean() * 100), 2),
            **{f"p{int(p*1000)/10:g}": round(float(x.quantile(p) * 100), 1) for p in (.025, .05, .10, .25, .5, .75, .90, .95, .975)}}
for lab, cond in [("전체", v["r"] < 9), ("ATR/종가 ≥ 12%", v["atrp"] >= 0.12), ("ATR/종가 ≥ 15%", v["atrp"] >= 0.15), ("10일 표준편차 ≥ 10%", v["sd10"] >= 0.10),
                  ("당일 −10% 이하", v["r"] <= -0.10), ("당일 −15% 이하", v["r"] <= -0.15), ("당일 −15% 이하 & 2026", (v["r"] <= -0.15) & (v.index >= "2026-01-01")),
                  ("당일 −10% 이하 & 애프터가 종가 아래", (v["r"] <= -0.10) & (v["ah_prem"] < 0)), ("당일 −10% 이하 & 애프터가 종가 위", (v["r"] <= -0.10) & (v["ah_prem"] >= 0)),
                  ("2026-10-08 이후", v.index >= "2026-10-08"), ("금요일 애프터 만기(목→금)", v.index.dayofweek == 3), ("목→금 & ATR ≥ 12%", (v.index.dayofweek == 3) & (v["atrp"] >= 0.12))]:
    s = v[cond]
    OUT[f"T2_{lab}"] = q(s["r24"])
    print(lab, OUT[f"T2_{lab}"])
s = v[v["r"] <= -0.15]
tab = s[["Close", "px", "hr", "nxt_px", "nxt_hr", "r", "ah_prem", "r24"]].copy()
tab[["r", "ah_prem", "r24"]] = (tab[["r", "ah_prem", "r24"]] * 100).round(2)
print(tab.to_string())
OUT["T2_rows_le_15"] = {str(i)[:10]: [float(a) for a in r] for i, r in tab.iterrows()}
print("11/5 행:", d.loc["2026-11-05", ["Close", "px", "hr", "r", "ah_prem", "atrp", "sd10"]].to_dict())

# ---------------------------------------------------------------- T3 급락일 사례: 다음 한국장·다음 미국장
print("\n=== T3 KORU −15% 이하(2026) 다음 날 분해")
e = ewy.copy(); e["r"] = e["Close"].pct_change(fill_method=None)
ksr = ks["Close"].pct_change(fill_method=None); ksgap = ks["Open"] / ks["Close"].shift(1) - 1; kslow = ks["Low"] / ks["Close"].shift(1) - 1
sr = sox["Close"].pct_change(fill_method=None)
rows = []
for dt in s.index[s.index >= "2026-01-01"]:
    i = koru.index.get_loc(dt); nd = koru.index[i + 1]
    kx = ksr.loc[ksr.index > dt]
    kd = kx.index[0]
    rows.append({"D": str(dt)[:10], "KORU_D": round(float(s.loc[dt, "r"]), 2) if False else round(float(koru["Close"].pct_change(fill_method=None).loc[dt]) * 100, 1),
                 "EWY_D": round(float(e.loc[dt, "r"]) * 100, 1), "AH_prem": round(float(d.loc[dt, "ah_prem"]) * 100, 1),
                 "KR_day": str(kd)[5:10], "KOSPI_gap": round(float(ksgap.loc[kd]) * 100, 1), "KOSPI_low": round(float(kslow.loc[kd]) * 100, 1), "KOSPI_close": round(float(ksr.loc[kd]) * 100, 1),
                 "EWY_gap": round(float(ewy.loc[nd, "Open"] / ewy.loc[dt, "Close"] - 1) * 100, 1), "EWY_oc": round(float(ewy.loc[nd, "Close"] / ewy.loc[nd, "Open"] - 1) * 100, 1),
                 "EWY_n": round(float(e.loc[nd, "r"]) * 100, 1), "SOX_n": round(float(sr.loc[nd]) * 100, 1),
                 "KORU_n": round(float(koru.loc[nd, "Close"] / koru.loc[dt, "Close"] - 1) * 100, 1), "KORU_24h_AH": round(float(d.loc[dt, "r24"]) * 100, 1) if pd.notna(d.loc[dt, "r24"]) else None})
t3 = pd.DataFrame(rows)
print(t3.to_string(index=False))
OUT["T3_rows"] = rows
sub = t3[t3["KOSPI_close"] <= -5]
print("다음 한국장 −5% 이하였던 경우: N", len(sub), "KORU 24h 상승", int((sub["KORU_24h_AH"] > 0).sum()), "중앙값", sub["KORU_24h_AH"].median(), "| EWY_n 평균", round(sub["EWY_n"].mean(), 2), "SOX_n 평균", round(sub["SOX_n"].mean(), 2))
OUT["T3_kospi_le_5"] = {"n": int(len(sub)), "up": int((sub["KORU_24h_AH"] > 0).sum()), "median": float(sub["KORU_24h_AH"].median())}

# ---------------------------------------------------------------- T4 금요일 애프터마켓 드리프트 (16:00 종가 → 마지막 애프터 체결)
dd = d.loc[:"2026-11-04"].copy()
dd["ah_drift"] = dd["px"] / dd["Close"] - 1
dd = dd[dd["ah_drift"].abs() < 0.15]
print("\n=== T4 애프터마켓 드리프트(정규장 종가 → 마지막 애프터 체결)")
for lab, cond in [("전체", dd["r"] < 9), ("금요일", dd.index.dayofweek == 4), ("금요일 & ATR ≥ 12%", (dd.index.dayofweek == 4) & (dd["atrp"] >= 0.12)), ("월~목 & ATR ≥ 12%", (dd.index.dayofweek < 4) & (dd["atrp"] >= 0.12))]:
    x = dd.loc[cond, "ah_drift"]
    OUT[f"T4_{lab}"] = {**q(x), "sd": round(float(x.std() * 100), 2), "abs_median": round(float(x.abs().median() * 100), 2)}
    print(lab, OUT[f"T4_{lab}"])

# ---------------------------------------------------------------- T5 코스피 급락일 밤 EWY (갭·시가→종가·종가)
print("\n=== T5 코스피 −5% 이하 마감일의 그날 밤 미국장 EWY")
soxx = dl("SOXX", NY)
rows = []
for kd in ksr.index[(ksr <= -0.05) & (ksr.index >= "2010-01-01")]:
    if kd not in ewy.index: continue
    i = ewy.index.get_loc(kd)
    if i == 0: continue
    p = ewy["Close"].iloc[i - 1]
    rows.append({"d": kd, "kospi": ksr.loc[kd], "ewy_prev": e["r"].iloc[i - 1], "gap": ewy["Open"].iloc[i] / p - 1, "oc": ewy["Close"].iloc[i] / ewy["Open"].iloc[i] - 1, "cc": ewy["Close"].iloc[i] / p - 1,
                 "sox": sr.loc[kd] if kd in sr.index else np.nan})
t5 = pd.DataFrame(rows).set_index("d")
print((t5 * 100).round(2).to_string())
for lab, sub in [("전체(2010~)", t5), ("2026", t5.loc["2026-01-01":]), ("전날 EWY −5% 이하(선반영)", t5[t5["ewy_prev"] <= -0.05]), ("전날 EWY −5% 초과", t5[t5["ewy_prev"] > -0.05])]:
    OUT[f"T5_{lab}"] = {"n": int(len(sub)), "gap": summ(sub["gap"]), "oc": summ(sub["oc"]), "cc": summ(sub["cc"]), "p_cc_gt_1.28": round(float((sub["cc"] > 0.0128).mean() * 100), 1) if len(sub) else None, "sox": summ(sub["sox"])}
    print(lab, "N", len(sub), "| 갭", OUT[f"T5_{lab}"]["gap"].get("median"), "| O→C 상승", OUT[f"T5_{lab}"]["oc"].get("up"), OUT[f"T5_{lab}"]["oc"].get("median"), "| 종가 상승", OUT[f"T5_{lab}"]["cc"].get("up"), OUT[f"T5_{lab}"]["cc"].get("mean"), OUT[f"T5_{lab}"]["cc"].get("median"), "| >+1.28%", OUT[f"T5_{lab}"]["p_cc_gt_1.28"], "| SOX 상승", OUT[f"T5_{lab}"]["sox"].get("up"), OUT[f"T5_{lab}"]["sox"].get("median"))
dump(OUT, "fc_stats2.json")
