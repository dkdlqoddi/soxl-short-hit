"""SOXL 2026-11-05 회차(기준 11/4 23:30 KST 정규장 시가) 24시간 예측 채점.
입력: fetch.py가 저장한 1분봉 CSV. 출력: review_score.json, review_path_30min.csv, 표준 출력."""
import json
import pandas as pd, numpy as np
from load import load

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 800)
NY = "America/New_York"
T = lambda x: pd.Timestamp(x, tz=NY)
kst = lambda ts: ts.tz_convert("Asia/Seoul").strftime("%m/%d %H:%M")
s = load("SOXL")
d1 = pd.read_csv("SOXL_1d.csv", index_col=0)
d1.index = pd.to_datetime(d1.index, utc=True).tz_convert(NY).strftime("%Y-%m-%d")
out = {}

def bar(ts):
    r = s.loc[T(ts)]
    return dict(kst=r["kst"], o=round(r["Open"], 4), h=round(r["High"], 4), l=round(r["Low"], 4), c=round(r["Close"], 4), v=int(r["Volume"]))

def seg(a, b):
    return s[(s.index >= T(a)) & (s.index <= T(b))]

def hl(a, b):
    x = seg(a, b)
    ih, il = x["High"].idxmax(), x["Low"].idxmin()
    return dict(first=round(x["Open"].iloc[0], 3), last=round(x["Close"].iloc[-1], 3),
                high=round(x["High"].max(), 3), high_kst=kst(ih), high_et=ih.strftime("%m/%d %H:%M"),
                low=round(x["Low"].min(), 3), low_kst=kst(il), low_et=il.strftime("%m/%d %H:%M"), n=len(x))

# ── 기준가·만기가
out["base_bar"] = bar("2026-11-04 09:30")
out["expiry_open_bar"] = bar("2026-11-05 09:30")
out["codex_expiry_bar_1004"] = bar("2026-11-05 10:04")
out["codex_expiry_bar_1005"] = bar("2026-11-05 10:05")
out["daily"] = {k: {c: round(float(d1.loc[k, c]), 4) for c in ("Open", "High", "Low", "Close")} | {"Volume": int(d1.loc[k, "Volume"])}
                for k in ("2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05")}
PC, C4, C5 = 73.12, d1.loc["2026-11-04", "Close"], d1.loc["2026-11-05", "Close"]
O5 = out["expiry_open_bar"]["o"]; X1004 = out["codex_expiry_bar_1004"]["c"]
models = {
    "claude": dict(base=70.03, p_up=0.42, p_up_vs_close=0.20, p_up_vs_now=0.50, now=69.8, expiry=O5, center=(67, 70), full=(60, 80)),
    "argon": dict(base=70.03, p_up=0.59, p_up_vs_close=0.435, p_up_vs_now=0.515, now=72.37, expiry=O5, center=(71.5, 74.0), full=(61, 79)),
    "codex_main": dict(base=70.00, p_up=0.55, now=71.75, expiry=X1004, center=(71, 73), full=(61, 81)),
    "codex_open": dict(base=70.00, p_up=0.55, now=71.75, expiry=O5, center=(71, 73), full=(61, 81)),
}
for k, m in models.items():
    m["chg_vs_base"] = round((m["expiry"] / m["base"] - 1) * 100, 2)
    m["chg_vs_prev_close"] = round((m["expiry"] / PC - 1) * 100, 2)
    m["chg_vs_now"] = round((m["expiry"] / m["now"] - 1) * 100, 2)
    m["center_low_gap_pct"] = round((m["expiry"] / m["center"][0] - 1) * 100, 2)
    m["full_low_gap_pct"] = round((m["expiry"] / m["full"][0] - 1) * 100, 2)
    m["brier_base"] = round(m["p_up"] ** 2, 4)
    if "p_up_vs_close" in m:
        m["brier_close"] = round(m["p_up_vs_close"] ** 2, 4)
        m["brier_now"] = round(m["p_up_vs_now"] ** 2, 4)
out["models"] = models
out["alt_expiry"] = {"open_bar_close": out["expiry_open_bar"]["c"],
                     "chg_openbar_close_vs_7003": round((out["expiry_open_bar"]["c"] / 70.03 - 1) * 100, 2),
                     "chg_open_vs_70025": round((O5 / 70.025 - 1) * 100, 2),
                     "regular_close_1105_vs_7003": round((C5 / 70.03 - 1) * 100, 2),
                     "regular_close_1104_vs_7003": round((C4 / 70.03 - 1) * 100, 2)}

# ── 국면
phases = {
    "p1_first_hour": ("2026-11-04 09:30", "2026-11-04 10:29"),
    "p2_selloff": ("2026-11-04 10:30", "2026-11-04 11:29"),
    "p3_rest_regular": ("2026-11-04 11:30", "2026-11-04 15:59"),
    "p4_after_market": ("2026-11-04 16:00", "2026-11-04 19:59"),
    "p6_premarket": ("2026-11-05 04:00", "2026-11-05 09:29"),
    "p7_regular_1105": ("2026-11-05 09:30", "2026-11-05 15:59"),
    "p7a_first_hour_1105": ("2026-11-05 09:30", "2026-11-05 10:29"),
    "p8_after_market_1105": ("2026-11-05 16:00", "2026-11-05 19:59"),
    "regular_1104": ("2026-11-04 09:30", "2026-11-04 15:59"),
    "window_24h": ("2026-11-04 09:30", "2026-11-05 09:29"),
}
out["phases"] = {k: hl(*v) for k, v in phases.items()}
for k, v in out["phases"].items():
    print(k, v)

# 첫 1시간 종가 (10:29 봉 종가), 10:30 봉
out["first_hour_close_1029"] = bar("2026-11-04 10:29")
out["bar_1030"] = bar("2026-11-04 10:30")
# 분석 시각 가격
for nm, ts in {"codex_analysis_1005": "2026-11-04 10:05", "argon_analysis_1017": "2026-11-04 10:17", "claude_analysis_1030": "2026-11-04 10:30", "claude_recheck_1037": "2026-11-04 10:37"}.items():
    out[nm] = bar(ts)

# ── 구간 기여 (기준가 70.03 → 만기 56.95)
pts = [("11/4 09:30 시가", 70.03),
       ("11/4 10:29 (첫 1시간 종가)", out["first_hour_close_1029"]["c"]),
       ("11/4 16:00 정규장 종가", float(C4)),
       ("11/4 19:59 애프터마켓 마지막", seg("2026-11-04 19:00", "2026-11-04 19:59")["Close"].iloc[-1]),
       ("11/5 04:00 프리마켓 첫 체결", s.loc[T("2026-11-05 04:00"), "Open"]),
       ("11/5 09:29 프리마켓 마지막", seg("2026-11-05 09:00", "2026-11-05 09:29")["Close"].iloc[-1]),
       ("11/5 09:30 시가 (만기)", O5)]
contrib = []
for (n0, p0), (n1, p1) in zip(pts[:-1], pts[1:]):
    contrib.append(dict(frm=n0, to=n1, p0=round(float(p0), 3), p1=round(float(p1), 3), chg=round((p1 / p0 - 1) * 100, 2),
                        log_share=round(np.log(p1 / p0) / np.log(O5 / 70.03) * 100, 1)))
out["contrib"] = contrib
print(pd.DataFrame(contrib).to_string())

# ── 24시간 구간에서 기준가 위에 있던 1분봉 비율
w = seg("2026-11-04 09:30", "2026-11-05 09:29")
out["above_base"] = dict(n=len(w), above_7003=int((w["Close"] > 70.03).sum()), share=round(float((w["Close"] > 70.03).mean() * 100), 1),
                         last_above_kst=kst(w[w["Close"] > 70.03].index[-1]), last_above_et=str(w[w["Close"] > 70.03].index[-1]),
                         above_7312=int((w["Close"] > 73.12).sum()), last_above_7312_kst=kst(w[w["Close"] > 73.12].index[-1]) if (w["Close"] > 73.12).any() else None)
print("above_base", out["above_base"])

# ── 재검토선
r4 = seg("2026-11-04 09:30", "2026-11-04 15:59")
after = lambda ts: r4[r4.index >= T(ts)]
# Argon: 10:17 이후 첫 1분봉 종가 < 70.03, 그리고 마지막으로 70.03 위였던 봉
a = after("2026-11-04 10:17"); below = a[a["Close"] < 70.03]
out["argon_7003_first_close_below"] = dict(et=str(below.index[0]), kst=kst(below.index[0]), close=round(below["Close"].iloc[0], 3))
ab = a[a["Close"] >= 70.03]
out["argon_7003_last_close_above"] = dict(et=str(ab.index[-1]), kst=kst(ab.index[-1]), close=round(ab["Close"].iloc[-1], 3))
# 15분봉
m15 = r4.resample("15min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
m15["kst"] = [kst(i) for i in m15.index]
m15["below6726"] = m15["Close"] < 67.26
m15["above7312"] = m15["Close"] > 73.12
print(m15[["kst", "Open", "High", "Low", "Close", "below6726", "above7312"]].round(2).to_string())
m15a = m15[m15.index >= T("2026-11-04 10:00")]
two = [i for i in range(1, len(m15a)) if m15a["below6726"].iloc[i] and m15a["below6726"].iloc[i - 1]]
i0 = two[0]
out["codex_two_15m_below_6726"] = dict(second_bar_start_et=str(m15a.index[i0]), confirm_kst=kst(m15a.index[i0] + pd.Timedelta(minutes=15)),
                                       confirm_close=round(m15a["Close"].iloc[i0], 3), first_bar_close=round(m15a["Close"].iloc[i0 - 1], 3))
out["codex_two_15m_above_7312"] = bool(any(m15a["above7312"].iloc[i] and m15a["above7312"].iloc[i - 1] for i in range(1, len(m15a))))
# 저가 67.26 첫 이탈(1분봉 저가 기준), 10:05 이후
b = after("2026-11-04 10:05"); brk = b[b["Low"] < 67.26]
out["first_break_6726"] = dict(et=str(brk.index[0]), kst=kst(brk.index[0]), low=round(brk["Low"].iloc[0], 3))
brk2 = b[b["Close"] < 67.26]
out["first_1m_close_below_6726"] = dict(et=str(brk2.index[0]), kst=kst(brk2.index[0]), close=round(brk2["Close"].iloc[0], 3))
# Claude 지정가: 67.26 아래(67.2 가정), 63~65(64 가정) 체결 시각
for lvl in (67.2, 65.0, 64.0, 63.0):
    x = b[b["Low"] <= lvl]
    out[f"limit_fill_{lvl}"] = dict(et=str(x.index[0]), kst=kst(x.index[0])) if len(x) else None
# SOXX 당일 저점(분할 전 452.46 = 분할 후 150.82) 하회 시각
sx = load("SOXX"); sx4 = sx[(sx.index >= T("2026-11-04 10:05")) & (sx.index <= T("2026-11-04 15:59"))]
x = sx4[sx4["Low"] < 452.46 / 3]
out["soxx_break_day_low"] = dict(et=str(x.index[0]), kst=kst(x.index[0]), low=round(x["Low"].iloc[0], 3)) if len(x) else None
sxr = sx[(sx.index >= T("2026-11-04 09:30")) & (sx.index <= T("2026-11-04 15:59"))]
out["soxx_1104"] = dict(open=round(sxr["Open"].iloc[0], 3), high=round(sxr["High"].max(), 3), low=round(sxr["Low"].min(), 3), low_kst=kst(sxr["Low"].idxmin()),
                        close=round(sxr["Close"].iloc[-1], 3))
for k in ("argon_7003_first_close_below", "argon_7003_last_close_above", "codex_two_15m_below_6726", "codex_two_15m_above_7312", "first_break_6726",
          "first_1m_close_below_6726", "limit_fill_67.2", "limit_fill_65.0", "limit_fill_64.0", "limit_fill_63.0", "soxx_break_day_low", "soxx_1104"):
    print(k, out[k])

# 30분 경로 저장
r = s[s.index >= T("2026-11-04 04:00")].resample("30min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
r.insert(0, "kst", [kst(i) for i in r.index]); r["vs_base_pct"] = (r["Close"] / 70.03 - 1) * 100
r.round(3).to_csv("review_path_30min.csv")
json.dump(out, open("review_score.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: out[k] for k in ("base_bar", "expiry_open_bar", "codex_expiry_bar_1004", "codex_expiry_bar_1005", "models", "alt_expiry", "first_hour_close_1029", "bar_1030",
                                      "codex_analysis_1005", "argon_analysis_1017", "claude_analysis_1030", "claude_recheck_1037")}, ensure_ascii=False, indent=1, default=str))
