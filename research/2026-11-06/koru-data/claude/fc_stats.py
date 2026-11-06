"""KORU 24h forecast (2026-11-06) 조건부 통계 (Claude Fable Max). 입력 hist/*.pkl. 출력 fc_stats.json + 표준출력.
 S1 코스피 장중 −7% 이하 급락일(일봉)   S2 코스피 10:00 상태별 종가(1시간봉)   S3 EWY 급락 다음 날   S4 EWY 깊은 할인 다음 날
 S5 필라델피아 반도체·S&P500 급락 다음 날   S6 KORU 급락 다음 날 / 24시간 분포
실행: python3 fc_stats.py"""
import numpy as np, pandas as pd
from fc_common import *

OUT = {}
ewy, koru, soxx, spy, sox, mu, vix = (dl(s, "America/New_York") for s in ["EWY", "KORU", "SOXX", "SPY", "^SOX", "MU", "^VIX"])
gspc = dl("^GSPC", "America/New_York")
ks, tr = dl("^KS11", "Asia/Seoul"), dl("278540.KS", "Asia/Seoul")
fxd = dl("KRW=X", "Europe/London")
TODAY = pd.Timestamp("2026-11-06")
ks_hist = ks.loc[:"2026-11-05"].copy()

# ---------------------------------------------------------------- S1 코스피 장중 급락일
k = ks_hist.copy()
pc = k["Close"].shift(1)
k["gap"] = k["Open"] / pc - 1; k["lowp"] = k["Low"] / pc - 1; k["r"] = k["Close"] / pc - 1; k["highp"] = k["High"] / pc - 1
k["rec"] = k["Close"] / k["Low"] - 1          # 저가 대비 종가 회복
k["oc"] = k["Close"] / k["Open"] - 1
k["nxt"] = k["r"].shift(-1); k["nxt_gap"] = k["gap"].shift(-1)
print("=== S1 코스피 장중 저가 −7% 이하 (전일 종가 대비, 1997~2026-11-05)")
c = k[k["lowp"] <= -0.07]
print((c[["gap", "lowp", "r", "rec", "nxt_gap", "nxt"]] * 100).round(2).to_string())
OUT["S1_low_le_7"] = {"n": int(len(c)), "close_r": summ(c["r"]), "rec_from_low": summ(c["rec"]), "next": summ(c["nxt"]),
                      "close_above_-6": round(float((c["r"] > -0.06).mean() * 100), 1), "close_above_-4": round(float((c["r"] > -0.04).mean() * 100), 1),
                      "rows": {str(i)[:10]: [round(float(x) * 100, 2) for x in r] for i, r in c[["gap", "lowp", "r", "rec", "nxt"]].iterrows()}}
print("N", len(c), "종가 분포", summ(c["r"]), "\n저가→종가 회복", summ(c["rec"]), "\n다음 날", summ(c["nxt"]))
c26 = c.loc["2026-01-01":]
print("2026년만 N", len(c26), "종가", summ(c26["r"]), "회복", summ(c26["rec"]), "다음날", summ(c26["nxt"]))
OUT["S1_low_le_7_2026"] = {"n": int(len(c26)), "close_r": summ(c26["r"]), "rec_from_low": summ(c26["rec"]), "next": summ(c26["nxt"])}
# 갭 −1.5~−3% 로 시작해 장중 −7% 이하
c2 = k[(k["lowp"] <= -0.05)]
print("저가 −5% 이하 N", len(c2), "종가", summ(c2["r"]), "회복", summ(c2["rec"]), "2026:", summ(c2.loc["2026-01-01":, "r"]), summ(c2.loc["2026-01-01":, "rec"]))
OUT["S1_low_le_5"] = {"n": int(len(c2)), "close_r": summ(c2["r"]), "rec_from_low": summ(c2["rec"]), "close_r_2026": summ(c2.loc["2026-01-01":, "r"]), "rec_2026": summ(c2.loc["2026-01-01":, "rec"])}

# ---------------------------------------------------------------- S2 코스피 1시간봉: 10:00/11:00 상태 → 종가
kh = hl("^KS11", "Asia/Seoul")
kh = kh[kh.index < pd.Timestamp("2026-11-06", tz="Asia/Seoul")]
rows = []
dclose = ks_hist["Close"]
for day, g in kh.groupby(kh.index.strftime("%Y-%m-%d")):
    d = pd.Timestamp(day)
    if d not in dclose.index: continue
    i = dclose.index.get_loc(d)
    if i == 0: continue
    p = float(dclose.iloc[i - 1]); cl = float(dclose.iloc[i])
    g = g.sort_index()
    b9 = g[g.index.hour == 9]; b10 = g[g.index.hour == 10]
    if len(b9) == 0 or len(b10) == 0: continue
    rows.append({"d": d, "open": b9["Open"].iloc[0] / p - 1, "h10": b9["Close"].iloc[0] / p - 1, "h11": b10["Close"].iloc[0] / p - 1,
                 "low_am": min(b9["Low"].iloc[0], b10["Low"].iloc[0]) / p - 1, "close": cl / p - 1,
                 "low_day": float(ks_hist.loc[d, "Low"]) / p - 1})
hh = pd.DataFrame(rows).set_index("d")
hh["h11_to_close"] = (1 + hh["close"]) / (1 + hh["h11"]) - 1
hh["h10_to_close"] = (1 + hh["close"]) / (1 + hh["h10"]) - 1
hh["new_low_pm"] = hh["low_day"] < hh["low_am"] - 1e-6
print("\n=== S2 코스피 1시간봉 (", str(hh.index[0])[:10], "~", str(hh.index[-1])[:10], "N", len(hh), ")")
for lab, cond in [("11:00에 −4% 이하", hh["h11"] <= -0.04), ("11:00에 −3% 이하", hh["h11"] <= -0.03), ("11:00에 −5% 이하", hh["h11"] <= -0.05),
                  ("10:00에 −4% 이하", hh["h10"] <= -0.04), ("11:00에 −3% 이하 & 2026", (hh["h11"] <= -0.03) & (hh.index >= "2026-01-01")),
                  ("11:00에 −3% 이하 & 11:00>10:00(반등 중)", (hh["h11"] <= -0.03) & (hh["h11"] > hh["h10"])),
                  ("11:00에 −3% 이하 & 11:00<=10:00(하락 중)", (hh["h11"] <= -0.03) & (hh["h11"] <= hh["h10"])),
                  ("전체", hh["h11"] < 9)]:
    s = hh[cond]
    res = {"n": int(len(s)), "h11_to_close": summ(s["h11_to_close"]), "close_r": summ(s["close"]),
           "pm_new_low": round(float(s["new_low_pm"].mean() * 100), 1) if len(s) else None,
           "close_ge_+1pp_vs_11": round(float((s["h11_to_close"] >= 0.01).mean() * 100), 1) if len(s) else None,
           "close_le_-1pp_vs_11": round(float((s["h11_to_close"] <= -0.01).mean() * 100), 1) if len(s) else None}
    OUT[f"S2_{lab}"] = res
    print(lab, "N", len(s), "| 11:00→종가", res["h11_to_close"], "| 오후 신저가", res["pm_new_low"], "% | +1%p 이상 회복", res["close_ge_+1pp_vs_11"], "% | −1%p 이상 추가 하락", res["close_le_-1pp_vs_11"], "%")
s = hh[hh["h11"] <= -0.04]
print((s[["open", "h10", "h11", "low_am", "low_day", "close", "h11_to_close"]] * 100).round(2).to_string())
OUT["S2_rows_h11_le_4"] = {str(i)[:10]: [round(float(x) * 100, 2) for x in r] for i, r in s[["open", "h10", "h11", "low_day", "close", "h11_to_close"]].iterrows()}

# ---------------------------------------------------------------- S3 EWY 급락 다음 날
e = ewy.copy()
e["r"] = e["Close"].pct_change(fill_method=None); e["gap_n"] = (e["Open"].shift(-1) / e["Close"] - 1); e["oc_n"] = (e["Close"].shift(-1) / e["Open"].shift(-1) - 1)
e["r_n"] = e["r"].shift(-1); e["low_n"] = e["Low"].shift(-1) / e["Close"] - 1; e["high_n"] = e["High"].shift(-1) / e["Close"] - 1
e["clv"] = (e["Close"] - e["Low"]) / (e["High"] - e["Low"])
kr_ = koru["Close"].pct_change(fill_method=None)
e["koru_n"] = kr_.shift(-1).reindex(e.index)
ksr = ks_hist["Close"].pct_change(fill_method=None)
# 다음 한국 거래일(미국 D일 종가 뒤 첫 한국장 = 한국 날짜 > D 중 첫 날)
def next_kr(d):
    x = ksr.loc[ksr.index > d]
    return float(x.iloc[0]) if len(x) else np.nan
print("\n=== S3 EWY 하루 −9% 이하 (2000~, 11/5 제외) 다음 미국 거래일")
c = e[(e["r"] <= -0.09) & (e.index < "2026-11-05")].copy()
c["kospi_next"] = [next_kr(d) for d in c.index]
print((c[["r", "clv", "kospi_next", "gap_n", "oc_n", "r_n", "low_n", "high_n", "koru_n"]] * [100, 1, 100, 100, 100, 100, 100, 100, 100]).round(2).to_string())
for lab, thr in [("le9", -0.09), ("le7", -0.07), ("le6", -0.06)]:
    c = e[(e["r"] <= thr) & (e.index < "2026-11-05")]
    res = {"n": int(len(c)), "r_n": summ(c["r_n"]), "gap_n": summ(c["gap_n"]), "oc_n": summ(c["oc_n"]),
           "p_gt_1.28": round(float((c["r_n"] > 0.0128).mean() * 100), 1), "p_gt_1.66": round(float((c["r_n"] > 0.0166).mean() * 100), 1),
           "p_gt_0.3": round(float((c["r_n"] > 0.003).mean() * 100), 1), "koru_n": summ(c["koru_n"])}
    OUT[f"S3_ewy_{lab}"] = res
    print(lab, res)
    c26 = c.loc["2026-01-01":]
    res26 = {"n": int(len(c26)), "r_n": summ(c26["r_n"]), "p_gt_1.28": round(float((c26["r_n"] > 0.0128).mean() * 100), 1) if len(c26) else None, "oc_n": summ(c26["oc_n"]), "gap_n": summ(c26["gap_n"])}
    OUT[f"S3_ewy_{lab}_2026"] = res26
    print("   2026:", res26)
# 저가 마감(CLV<=0.1) 조건
c = e[(e["r"] <= -0.05) & (e["clv"] <= 0.1) & (e.index < "2026-11-05")]
OUT["S3_ewy_le5_clv01"] = {"n": int(len(c)), "r_n": summ(c["r_n"]), "p_gt_1.28": round(float((c["r_n"] > 0.0128).mean() * 100), 1), "gap_n": summ(c["gap_n"]), "oc_n": summ(c["oc_n"])}
print("EWY −5% 이하 & CLV≤0.1:", OUT["S3_ewy_le5_clv01"])
c26 = c.loc["2026-01-01":]
OUT["S3_ewy_le5_clv01_2026"] = {"n": int(len(c26)), "r_n": summ(c26["r_n"]), "p_gt_1.28": round(float((c26["r_n"] > 0.0128).mean() * 100), 1), "gap_n": summ(c26["gap_n"]), "oc_n": summ(c26["oc_n"])}
print("   2026:", OUT["S3_ewy_le5_clv01_2026"])

# ---------------------------------------------------------------- S4 EWY 깊은 할인(한국 종가 환산 공정가치 대비) 다음 날
fxh = hl("KRW=X", "Asia/Seoul")
fx15 = {}
for day, g in fxh.groupby(fxh.index.strftime("%Y-%m-%d")):
    g2 = g[g.index.hour <= 15]
    if len(g2): fx15[pd.Timestamp(day)] = float(g2["Close"].iloc[-1])
fx15 = pd.Series(fx15)
kr = pd.DataFrame({"tr": tr["Close"], "kospi": ks_hist["Close"]}).dropna()
kr["fx"] = fx15.reindex(kr.index).fillna(fxd["Close"].reindex(kr.index))
kr = kr.dropna(); kr["usd"] = kr["tr"] / kr["fx"]
us = pd.DataFrame({"ewy": ewy["Close"], "ewy_open": ewy["Open"], "koru": koru["Close"], "soxx_o": soxx["Open"], "soxx": soxx["Close"], "sox": sox["Close"], "spy": spy["Close"], "spy_o": spy["Open"]})
j = kr.join(us, how="inner").dropna(subset=["ewy"])
j["ratio"] = j["ewy"] / j["usd"]
for w in (20, 60):
    j[f"med{w}"] = j["ratio"].rolling(w).median().shift(1)
    j[f"prem{w}"] = j["ratio"] / j[f"med{w}"] - 1
j["krusd_n"] = j["usd"].pct_change(fill_method=None).shift(-1)
j["kospi_n"] = j["kospi"].pct_change(fill_method=None).shift(-1)
j["ewy_n"] = j["ewy"].pct_change(fill_method=None).shift(-1)
j["ewy_gap_n"] = j["ewy_open"].shift(-1) / j["ewy"] - 1
j["ewy_oc_n"] = j["ewy"].shift(-1) / j["ewy_open"].shift(-1) - 1
j["koru_n"] = j["koru"].pct_change(fill_method=None).shift(-1)
j["sox_n"] = j["sox"].pct_change(fill_method=None).shift(-1)
j["spy_oc_n"] = j["spy"].shift(-1) / j["spy_o"].shift(-1) - 1
j["struct20"] = j["krusd_n"] - j["prem20"]; j["struct60"] = j["krusd_n"] - j["prem60"]
j["ewy_r"] = j["ewy"].pct_change(fill_method=None)
jj = j.loc["2018-01-01":"2026-11-04"]
print("\n=== S4 EWY 종가가 한국 종가 환산 공정가치보다 깊이 할인된 날 (prem20) → 다음 날")
for lab, cond in [("prem20<=-5%", jj["prem20"] <= -0.05), ("prem20<=-4%", jj["prem20"] <= -0.04), ("prem20<=-3%", jj["prem20"] <= -0.03), ("prem20<=-2%", jj["prem20"] <= -0.02),
                  ("prem20<=-3% & 2026", (jj["prem20"] <= -0.03) & (jj.index >= "2026-01-01"))]:
    s = jj[cond].dropna(subset=["ewy_n"])
    res = {"n": int(len(s)), "kospi_n": summ(s["kospi_n"]), "krusd_n": summ(s["krusd_n"]), "ewy_n": summ(s["ewy_n"]), "ewy_gap_n": summ(s["ewy_gap_n"]), "ewy_oc_n": summ(s["ewy_oc_n"]), "koru_n": summ(s["koru_n"]),
           "struct20": summ(s["struct20"]), "p_ewy_gt_1.28": round(float((s["ewy_n"] > 0.0128).mean() * 100), 1)}
    OUT[f"S4_{lab}"] = res
    print(lab, "N", res["n"], "| 다음 코스피", res["kospi_n"]["up"], res["kospi_n"]["median"], "| 한국USD−할인", res["struct20"]["median"], "| EWY 다음날", res["ewy_n"]["up"], res["ewy_n"]["mean"], res["ewy_n"]["median"], "| >+1.28%", res["p_ewy_gt_1.28"], "| 갭", res["ewy_gap_n"]["median"], "| O→C", res["ewy_oc_n"]["up"], res["ewy_oc_n"]["median"], "| KORU", res["koru_n"]["up"], res["koru_n"]["median"])
s = jj[jj["prem20"] <= -0.04]
print((s[["ewy_r", "prem20", "prem60", "kospi_n", "krusd_n", "struct20", "ewy_gap_n", "ewy_oc_n", "ewy_n", "sox_n", "koru_n"]] * 100).round(2).to_string())
OUT["S4_rows_prem20_le_4"] = {str(i)[:10]: [round(float(x) * 100, 2) if pd.notna(x) else None for x in r] for i, r in s[["ewy_r", "prem20", "prem60", "kospi_n", "krusd_n", "struct20", "ewy_gap_n", "ewy_oc_n", "ewy_n", "sox_n", "koru_n"]].iterrows()}
# EWY 다음 날 종가 수익률 ~ (한국 USD − 할인) + SOX  (2026)
for lab, sub in [("2026", j.loc["2026-01-01":"2026-11-04"]), ("2024-03~", j.loc["2024-03-01":"2026-11-04"])]:
    s = sub.dropna(subset=["ewy_n", "struct20", "struct60", "sox_n"])
    r1 = ols(s["ewy_n"] * 100, np.column_stack([s["struct20"] * 100, s["sox_n"] * 100]), ["struct20", "sox"])
    r2 = ols(s["ewy_n"] * 100, np.column_stack([s["struct60"] * 100, s["sox_n"] * 100]), ["struct60", "sox"])
    r3 = ols(s["ewy_gap_n"] * 100, s["struct20"] * 100, ["struct20"])
    r4 = ols(s["ewy_oc_n"] * 100, np.column_stack([(s["soxx"].shift(-1) / s["soxx_o"].shift(-1) - 1).fillna(0) * 100]), ["soxx_oc"])
    OUT[f"S4_reg_{lab}"] = {"ewy_n~struct20+sox": r1, "ewy_n~struct60+sox": r2, "gap~struct20": r3}
    print(lab, "EWY 다음날 ~ struct20 + SOX:", r1, "\n   struct60:", r2, "\n   갭~struct20:", r3)

# ---------------------------------------------------------------- S5 미국 급락 다음 날
print("\n=== S5 필라델피아 반도체 급락 다음 날 (1994~, 11/5 제외)")
x = sox.copy(); x["r"] = x["Close"].pct_change(fill_method=None); x["r_n"] = x["r"].shift(-1); x["r2_n"] = x["Close"].shift(-2) / x["Close"] - 1
for thr in (-0.08, -0.06, -0.05):
    c = x[(x["r"] <= thr) & (x.index < "2026-11-05")]
    res = {"n": int(len(c)), "next": summ(c["r_n"]), "p_le_-3": round(float((c["r_n"] <= -0.03).mean() * 100), 1), "p_ge_+3": round(float((c["r_n"] >= 0.03).mean() * 100), 1)}
    c26 = c.loc["2025-01-01":]
    res["since2025"] = {"n": int(len(c26)), "next": summ(c26["r_n"])}
    OUT[f"S5_sox_le_{int(-thr*100)}"] = res
    print("SOX ≤", thr, res)
c = x[(x["r"] <= -0.08) & (x.index < "2026-11-05")]
print((c[["r", "r_n"]] * 100).round(2).to_string())
OUT["S5_sox_rows_le_8"] = {str(i)[:10]: [round(float(a) * 100, 2), round(float(b) * 100, 2)] for i, (a, b) in c[["r", "r_n"]].iterrows()}
g = gspc.loc["1950-01-01":].copy(); g["r"] = g["Close"].pct_change(fill_method=None); g["r_n"] = g["r"].shift(-1)
for thr in (-0.04, -0.03):
    c = g[(g["r"] <= thr) & (g.index < "2026-11-05")]
    res = {"n": int(len(c)), "next": summ(c["r_n"]), "since2010": summ(c.loc["2010-01-01":, "r_n"]), "p_le_-2": round(float((c["r_n"] <= -0.02).mean() * 100), 1), "p_ge_+2": round(float((c["r_n"] >= 0.02).mean() * 100), 1)}
    OUT[f"S5_spx_le_{int(-thr*100)}"] = res
    print("S&P500 ≤", thr, res)
c = g[(g["r"] <= -0.04) & (g.index >= "2008-01-01") & (g.index < "2026-11-05")]
print((c[["r", "r_n"]] * 100).round(2).to_string())
# 두 조건 동시: SOX −6% 이하 & S&P −3% 이하
both = pd.DataFrame({"sox": x["r"], "spx": g["r"], "sox_n": x["r_n"], "spx_n": g["r_n"]}).dropna()
c = both[(both["sox"] <= -0.06) & (both["spx"] <= -0.03) & (both.index < "2026-11-05")]
OUT["S5_both"] = {"n": int(len(c)), "sox_n": summ(c["sox_n"]), "spx_n": summ(c["spx_n"]), "rows": {str(i)[:10]: [round(float(v) * 100, 2) for v in r] for i, r in c.iterrows()}}
print("SOX ≤ −6% & S&P ≤ −3%:", OUT["S5_both"]["n"], OUT["S5_both"]["sox_n"], OUT["S5_both"]["spx_n"])
print((c * 100).round(2).to_string())
# EWY 다음날 (SOX −6% 이하 & S&P −3% 이하인 날 다음)
ee = pd.DataFrame({"ewy_n": e["r_n"], "ewy_r": e["r"]}).reindex(c.index)
print("  그 다음 날 EWY:", summ(ee["ewy_n"]))
OUT["S5_both"]["ewy_n"] = summ(ee["ewy_n"])

# ---------------------------------------------------------------- S6 KORU 급락 다음 날
print("\n=== S6 KORU 하루 −15% 이하 다음 날 (종가→종가)")
kk = koru.copy(); kk["r"] = kk["Close"].pct_change(fill_method=None); kk["r_n"] = kk["r"].shift(-1); kk["gap_n"] = kk["Open"].shift(-1) / kk["Close"] - 1
kk["low_n"] = kk["Low"].shift(-1) / kk["Close"] - 1; kk["high_n"] = kk["High"].shift(-1) / kk["Close"] - 1
for thr in (-0.25, -0.15, -0.10):
    c = kk[(kk["r"] <= thr) & (kk.index < "2026-11-05")]
    res = {"n": int(len(c)), "next": summ(c["r_n"]), "gap": summ(c["gap_n"]), "low_n": summ(c["low_n"]), "high_n": summ(c["high_n"]), "y2026": summ(c.loc["2026-01-01":, "r_n"])}
    OUT[f"S6_koru_le_{int(-thr*100)}"] = res
    print("KORU ≤", thr, res)
c = kk[(kk["r"] <= -0.15) & (kk.index < "2026-11-05")]
print((c[["r", "gap_n", "low_n", "high_n", "r_n"]] * 100).round(2).to_string())
OUT["S6_rows_le_15"] = {str(i)[:10]: [round(float(v) * 100, 2) for v in r] for i, r in c[["r", "gap_n", "low_n", "high_n", "r_n"]].iterrows()}
# 변동성 눈금
pcl = kk["Close"].shift(1)
trng = pd.concat([kk["High"] - kk["Low"], (kk["High"] - pcl).abs(), (kk["Low"] - pcl).abs()], axis=1).max(axis=1)
atr = trng.rolling(14).mean()
print("ATR14", round(float(atr.iloc[-1]), 3), "ATR/종가", round(float(atr.iloc[-1] / kk['Close'].iloc[-1] * 100), 1), "%; 11/4 기준", round(float(atr.iloc[-2] / kk['Close'].iloc[-2] * 100), 1), "%")
r26 = kk.loc["2026-01-01":, "r"]
print("2026 일간 표준편차", round(float(r26.std() * 100), 2), "최근 20일", round(float(kk['r'].iloc[-20:].std() * 100), 2), "최근 10일(11/5 포함)", round(float(kk['r'].iloc[-10:].std() * 100), 2), "11/5 제외 최근 20일", round(float(kk['r'].iloc[-21:-1].std() * 100), 2))
OUT["vol"] = {"atr14": round(float(atr.iloc[-1]), 3), "atr_pct": round(float(atr.iloc[-1] / kk['Close'].iloc[-1] * 100), 1), "sd2026": round(float(r26.std() * 100), 2),
              "sd20": round(float(kk['r'].iloc[-20:].std() * 100), 2), "sd20_ex": round(float(kk['r'].iloc[-21:-1].std() * 100), 2)}
er = e["r"]
print("EWY 2026 일간 표준편차", round(float(er.loc['2026-01-01':].std() * 100), 2), "최근 20일(11/5 제외)", round(float(er.iloc[-21:-1].std() * 100), 2), "포함", round(float(er.iloc[-20:].std() * 100), 2))
OUT["vol"]["ewy_sd2026"] = round(float(er.loc['2026-01-01':].std() * 100), 2); OUT["vol"]["ewy_sd20_ex"] = round(float(er.iloc[-21:-1].std() * 100), 2); OUT["vol"]["ewy_sd20"] = round(float(er.iloc[-20:].std() * 100), 2)
dump(OUT, "fc_stats.json")
