"""KORU 2026-11-04 회차 24시간 예측 채점 (Claude Fable Max).

1분봉(yfinance, 프리·애프터 포함)으로 기준가·만기가·국면·재검토선 작동 여부를 계산해
review_score.json 과 review_path_30min.csv 로 저장한다. 노트의 가격 수치는 모두 이 파일에서 나온다.

만기가 규칙: 만기 시각이 속한 1분봉의 종가. 그 분에 체결이 없으면 직전 마지막 1분봉 종가.
실행: python3 review_score.py
"""
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KST = "Asia/Seoul"
PREV_CLOSE = 11.01  # 2026-11-03 미국 정규장 종가

NOTES = [
    {"model": "Codex Astra Max", "slug": "astra", "base_kst": "2026-11-04 08:43", "base_price": 11.41, "expiry_kst": "2026-11-05 08:43"},
    {"model": "Antigravity Argon High", "slug": "argon", "base_kst": "2026-11-04 08:55", "base_price": 11.30, "expiry_kst": "2026-11-05 08:55"},
    {"model": "Claude Fable Max", "slug": "claude", "base_kst": "2026-11-04 09:10", "base_price": 11.39, "expiry_kst": "2026-11-05 09:10"},
]


def m1(sym: str) -> pd.DataFrame:
    d = pd.read_csv(os.path.join(HERE, f"m1_{sym}.csv"), index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(KST)
    return d


def bar(d: pd.DataFrame, t: str) -> dict:
    """t(KST 분)가 속한 1분봉. 없으면 직전 마지막 봉."""
    ts = pd.Timestamp(t, tz=KST)
    s = d.loc[:ts]
    row = s.iloc[-1]
    return {"bar_time_kst": s.index[-1].strftime("%Y-%m-%d %H:%M"), "exact": bool(s.index[-1] == ts),
            "open": round(float(row["Open"]), 4), "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4), "close": round(float(row["Close"]), 4)}


def seg(d: pd.DataFrame, a: str, b: str) -> dict | None:
    s = d.loc[pd.Timestamp(a, tz=KST):pd.Timestamp(b, tz=KST)]
    if s.empty:
        return None
    f = lambda t: t.strftime("%m-%d %H:%M")  # noqa: E731
    return {"bars": int(len(s)), "first": f(s.index[0]), "last": f(s.index[-1]),
            "open": round(float(s["Open"].iloc[0]), 4), "close": round(float(s["Close"].iloc[-1]), 4),
            "high": round(float(s["High"].max()), 4), "high_t": f(s["High"].idxmax()),
            "low": round(float(s["Low"].min()), 4), "low_t": f(s["Low"].idxmin()),
            "chg_pct": round((float(s["Close"].iloc[-1]) / float(s["Open"].iloc[0]) - 1) * 100, 2)}


def at(d: pd.DataFrame, t: str) -> float:
    return round(float(d.loc[:pd.Timestamp(t, tz=KST)]["Close"].iloc[-1]), 4)


def pct(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 2)


k = m1("KORU")
e = m1("EWY")
out: dict = {"generated_at_kst": pd.Timestamp.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S"), "prev_regular_close": PREV_CLOSE,
             "expiry_rule": "만기 분 1분봉 종가 (체결 없으면 직전 마지막 1분봉 종가)"}

# ---------------------------------------------------------------- 1. 채점
scores = []
for n in NOTES:
    b = bar(k, n["base_kst"])
    x = bar(k, n["expiry_kst"])
    w = k.loc[pd.Timestamp(n["base_kst"], tz=KST):pd.Timestamp(n["expiry_kst"], tz=KST)]
    scores.append({**n, "base_bar": b, "expiry_bar": x, "expiry_price": x["close"],
                   "chg_vs_base_pct": pct(x["close"], n["base_price"]),
                   "chg_vs_prev_close_pct": pct(x["close"], PREV_CLOSE),
                   "window_high": round(float(w["High"].max()), 4), "window_high_t": w["High"].idxmax().strftime("%m-%d %H:%M"),
                   "window_low": round(float(w["Low"].min()), 4), "window_low_t": w["Low"].idxmin().strftime("%m-%d %H:%M"),
                   "minutes_above_base": int((w["Close"] > n["base_price"]).sum()), "minutes_total": int(len(w))})
out["scores"] = scores

# ---------------------------------------------------------------- 2. 국면
PH = {
    "1_ah_after_base (11/4 08:43~09:59)": ("2026-11-04 08:43", "2026-11-04 09:59"),
    "3_premarket (11/4 18:00~23:29)": ("2026-11-04 18:00", "2026-11-04 23:29"),
    "3a_premarket_stable (18:10~20:13)": ("2026-11-04 18:10", "2026-11-04 20:13"),
    "3b_premarket_fade (20:14~23:29)": ("2026-11-04 20:14", "2026-11-04 23:29"),
    "4_regular (11/4 23:30~11/5 05:59)": ("2026-11-04 23:30", "2026-11-05 05:59"),
    "4a_open_spike (23:30~23:47)": ("2026-11-04 23:30", "2026-11-04 23:47"),
    "4b_selloff (23:48~01:06)": ("2026-11-04 23:48", "2026-11-05 01:06"),
    "4c_bounce_fade (01:07~05:59)": ("2026-11-05 01:07", "2026-11-05 05:59"),
    "5_ah_to_expiry (11/5 06:00~09:10)": ("2026-11-05 06:00", "2026-11-05 09:10"),
    "5a_ah_before_nxt (06:00~07:59)": ("2026-11-05 06:00", "2026-11-05 07:59"),
    "5b_ah_after_nxt (08:00~09:10)": ("2026-11-05 08:00", "2026-11-05 09:10"),
    "6_post_expiry (11/5 09:11~09:59)": ("2026-11-05 09:11", "2026-11-05 09:59"),
}
out["phases"] = {name: {"KORU": seg(k, a, b), "EWY": seg(e, a, b)} for name, (a, b) in PH.items()}
out["koru_regular_1104"] = {"open": 10.85, "high": 11.55, "low": 10.225, "close": 10.43, "chg_pct": pct(10.43, PREV_CLOSE),
                             "note": "일봉 종가 10.43(공식), 1분봉 마지막 체결 10.42"}

# 30분 표
def r30(d: pd.DataFrame) -> pd.DataFrame:
    x = d.loc[pd.Timestamp("2026-11-04 08:30", tz=KST):pd.Timestamp("2026-11-05 10:00", tz=KST)]
    return x.resample("30min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()


t30 = r30(k).add_prefix("KORU_")
for sym in ["EWY", "SOXX", "MU", "SPY", "SKHY", "QCOM"]:
    t30 = t30.join(r30(m1(sym))[["Close"]].rename(columns={"Close": sym}))
t30.round(4).to_csv(os.path.join(HERE, "review_path_30min.csv"))

# ---------------------------------------------------------------- 3. 재검토선·매매 규칙
w = k.loc[pd.Timestamp("2026-11-04 08:43", tz=KST):pd.Timestamp("2026-11-05 09:10", tz=KST)]
stable = w.loc[pd.Timestamp("2026-11-04 18:10", tz=KST):]  # 프리마켓 첫 10분의 튀는 체결($10.03~11.10) 제외
lv = {}
for level in (10.83, 10.37):
    c = stable[stable["Close"] < level]
    lv[f"first_close_below_{level}_after_18:10"] = c.index[0].strftime("%m-%d %H:%M") if len(c) else None
    lv[f"minutes_close_below_{level}"] = int(len(c))
for level in (11.56, 11.59):
    h = w[w["High"] >= level]
    lv[f"bars_high_ge_{level}"] = int(len(h))
    lv[f"bars_high_ge_{level}_times"] = [h.index[0].strftime("%m-%d %H:%M"), h.index[-1].strftime("%m-%d %H:%M")] if len(h) else None
    lv[f"bars_close_ge_{level}"] = int((w["Close"] >= level).sum())
# 정규장 개장 직후 휩소: 23:30~23:36 저가와 23:47 고가
lv["open_dip"] = seg(k, "2026-11-04 23:30", "2026-11-04 23:36")
lv["first_close_below_10.83_regular"] = None
reg = k.loc[pd.Timestamp("2026-11-04 23:48", tz=KST):pd.Timestamp("2026-11-05 05:59", tz=KST)]
c = reg[reg["Close"] < 10.83]
if len(c):
    lv["first_close_below_10.83_after_spike"] = c.index[0].strftime("%m-%d %H:%M")
    lv["last_close_above_10.83_regular"] = reg[reg["Close"] >= 10.83].index[-1].strftime("%m-%d %H:%M")
out["levels"] = lv

# 코스피 종가 5,780 아래 → 미국 개장 전(프리마켓) 정리 규칙의 가상 청산가
ex = {}
for name, (a, b) in {"18:10~19:00": ("2026-11-04 18:10", "2026-11-04 19:00"), "18:10~20:30": ("2026-11-04 18:10", "2026-11-04 20:30"),
                     "18:10~23:29": ("2026-11-04 18:10", "2026-11-04 23:29"), "22:30~23:29": ("2026-11-04 22:30", "2026-11-04 23:29")}.items():
    s = k.loc[pd.Timestamp(a, tz=KST):pd.Timestamp(b, tz=KST)]["Close"]
    ex[name] = {"bars": int(len(s)), "median": round(float(s.median()), 3), "min": round(float(s.min()), 3), "max": round(float(s.max()), 3),
                "median_vs_11.39_pct": pct(float(s.median()), 11.39), "median_vs_expiry_10.30_pct": pct(float(s.median()), 10.30)}
out["premarket_exit_rule"] = ex

# ---------------------------------------------------------------- 4. 연동 자산
ctx = {}
ks = m1("KS11")
d = ks.loc[pd.Timestamp("2026-11-04 09:00", tz=KST):pd.Timestamp("2026-11-04 15:35", tz=KST)]
ctx["KOSPI_1104_intraday"] = {"prev_close": 5648.79, "open": round(float(d["Open"].iloc[0]), 2), "high": round(float(d["High"].max()), 2),
                              "high_t": d["High"].idxmax().strftime("%H:%M"), "low": round(float(d["Low"].min()), 2),
                              "low_t": d["Low"].idxmin().strftime("%H:%M"), "last_1m": round(float(d["Close"].iloc[-1]), 2),
                              "last_1m_t": d.index[-1].strftime("%H:%M"), "official_close": 5683.80,
                              "at": {t: [at(ks, f"2026-11-04 {t}"), pct(at(ks, f"2026-11-04 {t}"), 5648.79)]
                                     for t in ["09:10", "09:42", "10:00", "10:38", "11:00", "12:00", "12:45", "13:10", "14:00", "14:59"]}}
for nm, sym, pv, close in [("Samsung", "005930_KS", 219500, 218000), ("SKhynix", "000660_KS", 1398000, 1396000), ("KODEX_MSCI_Korea_TR", "278540_KS", 31750, 31760)]:
    x = m1(sym).loc[pd.Timestamp("2026-11-04 09:00", tz=KST):pd.Timestamp("2026-11-04 15:35", tz=KST)]
    ctx[f"{nm}_1104"] = {"prev_close": pv, "open": float(x["Open"].iloc[0]), "open_pct": pct(float(x["Open"].iloc[0]), pv),
                         "high": float(x["High"].max()), "high_t": x["High"].idxmax().strftime("%H:%M"),
                         "low": float(x["Low"].min()), "low_pct": pct(float(x["Low"].min()), pv), "low_t": x["Low"].idxmin().strftime("%H:%M"),
                         "official_close": close, "close_pct": pct(close, pv)}
us = {}
for sym in ["EWY", "SOXX", "MU", "NVDA", "AMD", "QCOM", "ARM", "SKHY", "SPY", "SOXL"]:
    x = m1(sym)
    path = os.path.join(HERE, f"d1_{sym}.csv")
    if not os.path.exists(path):  # SPY는 3년 일봉 파일만 있음
        path = os.path.join(HERE, f"h_d1_{sym}.csv")
    dd = pd.read_csv(path, index_col=0)
    assert str(dd.index[-1]).startswith("2026-11-04") and str(dd.index[-2]).startswith("2026-11-03"), (sym, dd.index[-2:])
    c0, o1, c1 = float(dd["Close"].iloc[-2]), float(dd["Open"].iloc[-1]), float(dd["Close"].iloc[-1])
    us[sym] = {"close_1103": round(c0, 2), "open_1104": round(o1, 2), "close_1104": round(c1, 2), "c2c_pct": pct(c1, c0), "o2c_pct": pct(c1, o1),
               "pm_2013kst": at(x, "2026-11-04 20:13"), "pm_2013_vs_close_pct": pct(at(x, "2026-11-04 20:13"), c0),
               "pm_last_2329kst": at(x, "2026-11-04 23:29"), "ah_0910kst": at(x, "2026-11-05 09:10"), "ah_0910_vs_close_pct": pct(at(x, "2026-11-05 09:10"), c1),
               "ah_0959kst": at(x, "2026-11-05 09:59")}
ctx["US_1104"] = us
fut = {}
for sym in ["ES_F", "NQ_F", "KRW_X"]:
    x = m1(sym)
    fut[sym] = {t: at(x, t) for t in ["2026-11-04 09:10", "2026-11-04 10:00", "2026-11-04 12:00", "2026-11-04 12:45", "2026-11-04 15:30",
                                      "2026-11-04 18:00", "2026-11-04 20:13", "2026-11-04 23:30", "2026-11-05 06:00", "2026-11-05 09:10"]}
ctx["futures_fx"] = fut
out["context"] = ctx

# ---------------------------------------------------------------- 5. 구간 기여 (Claude 기준가 $11.39 → 만기 $10.30)
legs = [("09:10 기준가 → 09:59 애프터 종료", 11.39, at(k, "2026-11-04 09:59")),
        ("09:59 → 18:10 프리마켓(안정 체결)", at(k, "2026-11-04 09:59"), at(k, "2026-11-04 18:10")),
        ("18:10 → 20:13 프리마켓 고점", at(k, "2026-11-04 18:10"), at(k, "2026-11-04 20:13")),
        ("20:13 → 23:29 프리마켓 마지막", at(k, "2026-11-04 20:13"), at(k, "2026-11-04 23:29")),
        ("23:29 → 06:00 정규장 종가", at(k, "2026-11-04 23:29"), 10.43),
        ("06:00 → 07:59 애프터(NXT 개시 전)", 10.43, at(k, "2026-11-05 07:59")),
        ("07:59 → 09:10 만기", at(k, "2026-11-05 07:59"), at(k, "2026-11-05 09:10"))]
out["legs_claude"] = [{"leg": nm, "from": a, "to": b, "pct": pct(b, a)} for nm, a, b in legs]

with open(os.path.join(HERE, "review_score.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
