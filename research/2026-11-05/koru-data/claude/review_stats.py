"""KORU 2026-11-04 회차 복기 — 교훈 검증용 통계 (Claude Fable Max).

A. 선반영을 '수준'(EWY ÷ 달러 환산 MSCI Korea TR 비율의 20일 중앙값 대비 괴리)으로 잰 구조식과
   11/4 노트의 수익률 회귀(코스피·전날 EWY)의 설명력 비교
B. 애프터마켓 프리미엄이 붙은 날: 24시간 뒤 가격이 기준가/정규장 종가보다 높은 비율 (2년 1시간봉)
C. EWY 미국장 수익률의 SOXX·SPY 민감도
D. 코스피 갭 상승일의 개장 1시간 규칙 (2년 1시간봉)과 그날 밤 EWY
E. 코스피 갭 +2% 이상 & 전날 EWY +1.5% 이상: 시가 위/아래 마감별 그날 밤 EWY (장기 일봉, 11/4 포함 재계산)

실행: python3 review_stats.py  → review_stats.json, review_stats_*.csv
"""
import json
import os

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT: dict = {}


def p(path: str) -> str:
    return os.path.join(HERE, path)


def d1(sym: str, tz: str) -> pd.DataFrame:
    d = pd.read_csv(p(f"h_d1_{sym}.csv"), index_col=0)
    idx = pd.to_datetime(d.index, utc=True).tz_convert(tz)
    d.index = pd.to_datetime(idx.strftime("%Y-%m-%d"))
    return d


def h1(sym: str, tz: str) -> pd.DataFrame:
    d = pd.read_csv(p(f"h_h1_{sym}.csv"), index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(tz)
    return d


def ols(y: np.ndarray, X: np.ndarray, names: list[str]) -> dict:
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    sse = float(resid @ resid)
    sst = float(((y - y.mean()) ** 2).sum())
    n, k = X1.shape
    cov = sse / (n - k) * np.linalg.inv(X1.T @ X1)
    se = np.sqrt(np.diag(cov))
    return {
        "n": int(n),
        "r2": round(1 - sse / sst, 3),
        "coef": {nm: round(float(b), 3) for nm, b in zip(["const"] + names, beta)},
        "t": {nm: round(float(b / s), 2) for nm, b, s in zip(["const"] + names, beta, se)},
    }


def summ(x: pd.Series) -> dict:
    x = x.dropna()
    if len(x) == 0:
        return {"n": 0}
    return {"n": int(len(x)), "up": round(float((x > 0).mean() * 100), 1), "mean": round(float(x.mean() * 100), 2),
            "median": round(float(x.median() * 100), 2), "q25": round(float(x.quantile(0.25) * 100), 2),
            "q75": round(float(x.quantile(0.75) * 100), 2)}


# ---------------------------------------------------------------- A. 수준(iNAV 괴리) 구조식
ewy = d1("EWY", "America/New_York")
koru = d1("KORU", "America/New_York")
soxx = d1("SOXX", "America/New_York")
spy = d1("SPY", "America/New_York")
mu = d1("MU", "America/New_York")
tr = d1("278540_KS", "Asia/Seoul")
ks = d1("KS11", "Asia/Seoul")
fxd = d1("KRW_X", "Europe/London")
fxh = h1("KRW_X", "Asia/Seoul")

# 서울 15:30 부근 환율: 15시 봉 종가(≈15:59 KST), 없으면 16시 이전 마지막 봉, 그것도 없으면 일봉 종가
fx15 = {}
for day, g in fxh.groupby(fxh.index.strftime("%Y-%m-%d")):
    g2 = g[g.index.hour <= 15]
    if len(g2):
        fx15[pd.Timestamp(day)] = float(g2["Close"].iloc[-1])
fx15 = pd.Series(fx15)

kr = pd.DataFrame({"tr": tr["Close"], "kospi": ks["Close"], "kospi_open": ks["Open"]}).dropna()
kr["fx"] = fx15.reindex(kr.index)
kr["fx"] = kr["fx"].fillna(fxd["Close"].reindex(kr.index))
kr = kr.dropna()
kr["usd"] = kr["tr"] / kr["fx"]
kr["kr_prev"] = kr.index.to_series().shift(1)
us = pd.DataFrame({"ewy": ewy["Close"], "ewy_open": ewy["Open"], "koru": koru["Close"], "soxx": soxx["Close"],
                   "soxx_open": soxx["Open"], "spy": spy["Close"], "spy_open": spy["Open"], "mu": mu["Close"]}).dropna()
us["us_prev"] = us.index.to_series().shift(1)

j = kr.join(us, how="inner")
j["ratio"] = j["ewy"] / j["usd"]
j["fair"] = j["ratio"].rolling(20).median().shift(1)
j["fair60"] = j["ratio"].rolling(60).median().shift(1)
j["prem"] = j["ratio"] / j["fair"] - 1
j["prem60"] = j["ratio"] / j["fair60"] - 1
j["jprev"] = j.index.to_series().shift(1)
ok = (j["jprev"] == j["kr_prev"]) & (j["jprev"] == j["us_prev"])  # 양쪽 모두 연속 거래일
j["ewy_r"] = j["ewy"].pct_change()
j["koru_r"] = j["koru"].pct_change()
j["kospi_r"] = j["kospi"].pct_change()
j["krusd_r"] = j["usd"].pct_change()
j["soxx_r"] = j["soxx"].pct_change()
j["spy_r"] = j["spy"].pct_change()
j["mu_r"] = j["mu"].pct_change()
j["ewy_prev_r"] = j["ewy_r"].shift(1)
j["prem_prev"] = j["prem"].shift(1)
j["prem60_prev"] = j["prem60"].shift(1)
j["struct"] = j["krusd_r"] - j["prem_prev"]
j.loc[~ok, ["ewy_r", "koru_r", "kospi_r", "krusd_r", "soxx_r", "spy_r", "mu_r", "struct"]] = np.nan
j["ewy_prev_r"] = j["ewy_r"].shift(1)
j.to_csv(p("review_stats_inav.csv"))

A = {}
for label, sub in [("2024-03~2026-11", j.loc["2024-03-01":]), ("2026", j.loc["2026-01-01":])]:
    s = sub.dropna(subset=["ewy_r", "krusd_r", "prem_prev", "kospi_r", "ewy_prev_r"])
    y = s["ewy_r"].values * 100
    res = {
        "n": int(len(s)),
        "reg_old(kospi, ewy_prev)": ols(y, np.column_stack([s["kospi_r"] * 100, s["ewy_prev_r"] * 100]), ["kospi", "ewy_prev"]),
        "reg_level(krusd, prem_prev)": ols(y, np.column_stack([s["krusd_r"] * 100, s["prem_prev"] * 100]), ["krusd", "prem_prev"]),
        "reg_struct(krusd - prem_prev)": ols(y, (s["struct"] * 100).values.reshape(-1, 1), ["struct"]),
        # 계수 없이 구조식 그대로 썼을 때의 설명력
        "struct_r2_no_fit": round(float(1 - ((s["ewy_r"] - s["struct"]) ** 2).sum() / ((s["ewy_r"] - s["ewy_r"].mean()) ** 2).sum()), 3),
        # 한국장이 프리미엄을 얼마나 '추인'하는가: krusd(D+1) = a + b*prem(D)
        "kr_validates(krusd ~ prem_prev)": ols((s["krusd_r"] * 100).values, (s["prem_prev"] * 100).values.reshape(-1, 1), ["prem_prev"]),
        "ewy_next ~ prem_prev": ols(y, (s["prem_prev"] * 100).values.reshape(-1, 1), ["prem_prev"]),
    }
    # 프리미엄 구간별
    buckets = {}
    for nm, m in [("prem>=+2.0%", s["prem_prev"] >= 0.02), ("prem +1.0~+2.0%", (s["prem_prev"] >= 0.01) & (s["prem_prev"] < 0.02)),
                  ("prem -1.0~+1.0%", s["prem_prev"].abs() < 0.01), ("prem<=-1.0%", s["prem_prev"] <= -0.01),
                  ("prem<=-2.0%", s["prem_prev"] <= -0.02)]:
        buckets[nm] = {"kr_usd_next": summ(s.loc[m, "krusd_r"]), "kospi_next": summ(s.loc[m, "kospi_r"]),
                       "ewy_next": summ(s.loc[m, "ewy_r"]), "koru_next": summ(s.loc[m, "koru_r"])}
    res["buckets"] = buckets
    A[label] = res
row = j.loc["2026-10-27":"2026-11-04", ["tr", "fx", "usd", "ewy", "ratio", "fair", "prem", "prem60", "krusd_r", "kospi_r", "ewy_r", "struct"]]
A["recent_rows"] = json.loads(row.round(5).to_json(orient="index", date_format="iso"))
OUT["A_level_vs_return_regression"] = A

# ---------------------------------------------------------------- B. 애프터마켓 프리미엄 → 24시간 뒤
kh = h1("KORU", "America/New_York")
kd = d1("KORU", "America/New_York")
rows = []
for day, g in kh.groupby(kh.index.strftime("%Y-%m-%d")):
    b18 = g[(g.index.hour == 18)]
    b17 = g[(g.index.hour == 17)]
    b19 = g[(g.index.hour == 19)]
    rows.append({"date": pd.Timestamp(day), "ah18": float(b18["Close"].iloc[-1]) if len(b18) else np.nan,
                 "ah17": float(b17["Close"].iloc[-1]) if len(b17) else np.nan,
                 "ah19": float(b19["Close"].iloc[-1]) if len(b19) else np.nan})
b = pd.DataFrame(rows).set_index("date").join(kd[["Open", "High", "Low", "Close"]], how="inner")
b["dayret"] = b["Close"].pct_change()
b["prem"] = b["ah18"] / b["Close"] - 1
b["next_ah18"] = b["ah18"].shift(-1)
b["next_close"] = b["Close"].shift(-1)
b["r_base"] = b["next_ah18"] / b["ah18"] - 1          # 기준가(애프터) → 24시간 뒤 애프터
b["r_vs_close"] = b["next_ah18"] / b["Close"] - 1      # 정규장 종가 → 24시간 뒤 애프터
b["r_c2c"] = b["next_close"] / b["Close"] - 1          # 정규장 종가 → 다음 정규장 종가
b["ah_drift19"] = b["ah19"] / b["Close"] - 1
b = b[(b["prem"].abs() < 0.3) & (b["dayret"].abs() < 0.6)]
b.to_csv(p("review_stats_ah_premium.csv"))
B = {}
conds = {
    "all": b["prem"].notna(),
    "prem>=+1.0%": b["prem"] >= 0.01,
    "prem>=+2.5%": b["prem"] >= 0.025,
    "dayret>=+4% & prem>=+1.5%": (b["dayret"] >= 0.04) & (b["prem"] >= 0.015),
    "dayret>=+4% & prem>=+2.5% (11/3형)": (b["dayret"] >= 0.04) & (b["prem"] >= 0.025),
    "dayret>=+5% & prem>=+2.0%": (b["dayret"] >= 0.05) & (b["prem"] >= 0.02),
}
for nm, m in conds.items():
    s = b[m]
    B[nm] = {"vs_base(AH→AH)": summ(s["r_base"]), "vs_close(C→AH')": summ(s["r_vs_close"]), "c2c(C→C')": summ(s["r_c2c"])}
B["2026-11-03_row"] = json.loads(b.loc["2026-11-03":"2026-11-03"].round(4).to_json(orient="index", date_format="iso"))
B["sample_range"] = [str(b.index[0].date()), str(b.index[-1].date())]
OUT["B_ah_premium_24h"] = B

# ---------------------------------------------------------------- C. EWY 미국장 수익률의 SOXX·SPY 민감도
C = {}
u = us.copy()
u["ewy_oc"] = u["ewy"] / u["ewy_open"] - 1
u["soxx_oc"] = u["soxx"] / u["soxx_open"] - 1
u["spy_oc"] = u["spy"] / u["spy_open"] - 1
for label, sub in [("2025-01~2026-11", u.loc["2025-01-01":]), ("2026", u.loc["2026-01-01":])]:
    s = sub.dropna(subset=["ewy_oc", "soxx_oc", "spy_oc"])
    C[f"open→close {label}"] = ols((s["ewy_oc"] * 100).values, np.column_stack([s["soxx_oc"] * 100, s["spy_oc"] * 100]), ["soxx", "spy"])
    C[f"open→close {label} corr"] = {"ewy~soxx": round(float(s["ewy_oc"].corr(s["soxx_oc"])), 3), "ewy~spy": round(float(s["ewy_oc"].corr(s["spy_oc"])), 3)}
for label, sub in [("2025-01~2026-11", j.loc["2025-01-01":]), ("2026", j.loc["2026-01-01":])]:
    s = sub.dropna(subset=["ewy_r", "struct", "soxx_r", "spy_r"])
    C[f"close→close {label} (struct + soxx + spy)"] = ols((s["ewy_r"] * 100).values, np.column_stack([s["struct"] * 100, s["soxx_r"] * 100, s["spy_r"] * 100]), ["struct", "soxx", "spy"])
# 지수와 반도체가 갈린 날: SPY >= +0.5% & SOXX <= -2%
dv = u.copy()
dv["ewy_r"] = dv["ewy"].pct_change(); dv["soxx_r"] = dv["soxx"].pct_change(); dv["spy_r"] = dv["spy"].pct_change(); dv["koru_r"] = dv["koru"].pct_change()
m = (dv["spy_r"] >= 0.005) & (dv["soxx_r"] <= -0.02)
C["SPY>=+0.5% & SOXX<=-2% days (3y)"] = {"ewy": summ(dv.loc[m, "ewy_r"]), "koru": summ(dv.loc[m, "koru_r"]),
                                           "dates": [str(x.date()) for x in dv.index[m]]}
m2 = (dv["spy_r"] <= -0.005) & (dv["soxx_r"] >= 0.02)
C["SPY<=-0.5% & SOXX>=+2% days (3y)"] = {"ewy": summ(dv.loc[m2, "ewy_r"]), "koru": summ(dv.loc[m2, "koru_r"]),
                                           "dates": [str(x.date()) for x in dv.index[m2]]}
OUT["C_ewy_soxx_spy"] = C

# ---------------------------------------------------------------- D. 코스피 갭 상승일 개장 1시간 규칙 (2년 1시간봉)
kh1 = h1("KS11", "Asia/Seoul")
ksd = d1("KS11", "Asia/Seoul")
rows = []
for day, g in kh1.groupby(kh1.index.strftime("%Y-%m-%d")):
    g9 = g[g.index.hour == 9]
    if not len(g9):
        continue
    rows.append({"date": pd.Timestamp(day), "h1_open": float(g9["Open"].iloc[0]), "h1_close": float(g9["Close"].iloc[-1])})
dd = pd.DataFrame(rows).set_index("date").join(ksd[["Open", "Close"]], how="inner")
dd["prev_close"] = ksd["Close"].shift(1).reindex(dd.index)
dd["gap"] = dd["Open"] / dd["prev_close"] - 1
dd["h1_vs_open"] = dd["h1_close"] / dd["Open"] - 1
dd["close_vs_open"] = dd["Close"] / dd["Open"] - 1
dd["day_r"] = dd["Close"] / dd["prev_close"] - 1
dd = dd.join(j[["ewy_r", "koru_r", "ewy_prev_r", "prem_prev"]], how="left")
dd.to_csv(p("review_stats_kospi_first_hour.csv"))
D = {}
for gap_min in (0.015, 0.02):
    g = dd[dd["gap"] >= gap_min]
    below = g[g["h1_vs_open"] < 0]
    above = g[g["h1_vs_open"] >= 0]
    D[f"gap>={gap_min*100:.1f}%"] = {
        "n": int(len(g)),
        "h1_below_open": {"n": int(len(below)), "close_below_open_pct": round(float((below["close_vs_open"] < 0).mean() * 100), 1),
                          "open→close": summ(below["close_vs_open"]), "ewy_that_night": summ(below["ewy_r"]), "koru_that_night": summ(below["koru_r"])},
        "h1_above_open": {"n": int(len(above)), "close_below_open_pct": round(float((above["close_vs_open"] < 0).mean() * 100), 1),
                          "open→close": summ(above["close_vs_open"]), "ewy_that_night": summ(above["ewy_r"]), "koru_that_night": summ(above["koru_r"])},
        "close_below_open": {"ewy_that_night": summ(g.loc[g["close_vs_open"] < 0, "ewy_r"]), "koru_that_night": summ(g.loc[g["close_vs_open"] < 0, "koru_r"])},
        "close_above_open": {"ewy_that_night": summ(g.loc[g["close_vs_open"] >= 0, "ewy_r"]), "koru_that_night": summ(g.loc[g["close_vs_open"] >= 0, "koru_r"])},
    }
D["2026-11-04_row"] = json.loads(dd.loc["2026-11-04":"2026-11-04"].round(5).to_json(orient="index", date_format="iso"))
D["sample_range"] = [str(dd.index[0].date()), str(dd.index[-1].date())]
OUT["D_kospi_first_hour"] = D

# ---------------------------------------------------------------- E. 장기 일봉: 갭 +2% & 전날 EWY +1.5% (11/4 노트 2.4 재계산)
def long_daily(sym: str, tz: str) -> pd.DataFrame:
    path = p(f"h_dmax_{sym.replace('^', '').replace('=', '_')}.csv")
    if not os.path.exists(path):
        df = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False)
        df.to_csv(path)
    d = pd.read_csv(path, index_col=0)
    idx = pd.to_datetime(d.index, utc=True).tz_convert(tz)
    d.index = pd.to_datetime(idx.strftime("%Y-%m-%d"))
    return d


ksm = long_daily("^KS11", "Asia/Seoul").loc["2010-01-01":]
ewm = long_daily("EWY", "America/New_York").loc["2010-01-01":]
kom = long_daily("KORU", "America/New_York")
x = pd.DataFrame({"k_open": ksm["Open"], "k_close": ksm["Close"]}).dropna()
x = x[(x["k_open"] > 0) & (x["k_close"] > 0)]
x["k_prev"] = x["k_close"].shift(1)
x["gap"] = x["k_open"] / x["k_prev"] - 1
x["oc"] = x["k_close"] / x["k_open"] - 1
x["k_r"] = x["k_close"] / x["k_prev"] - 1
e2 = pd.DataFrame({"ewy": ewm["Close"]}).dropna()
e2["ewy_r"] = e2["ewy"].pct_change()
e2["ewy_prev_r"] = e2["ewy_r"].shift(1)
e2["koru_r"] = kom["Close"].pct_change().reindex(e2.index)
x = x.join(e2[["ewy_r", "ewy_prev_r", "koru_r"]], how="inner")
x.to_csv(p("review_stats_gapup_long.csv"))
E = {}
g = x[(x["gap"] >= 0.02) & (x["ewy_prev_r"] >= 0.015)]
E["gap>=+2% & prev EWY>=+1.5% (2010~)"] = {
    "n": int(len(g)),
    "close_above_open": {"ewy_that_night": summ(g.loc[g["oc"] >= 0, "ewy_r"]), "koru_that_night": summ(g.loc[g["oc"] >= 0, "koru_r"])},
    "close_below_open": {"ewy_that_night": summ(g.loc[g["oc"] < 0, "ewy_r"]), "koru_that_night": summ(g.loc[g["oc"] < 0, "koru_r"]),
                         "dates": [f"{d.date()} gap {r.gap*100:+.1f}% oc {r.oc*100:+.1f}% ewy {r.ewy_r*100:+.1f}%" for d, r in g[g["oc"] < 0].iterrows()]},
}
g2 = x[(x["gap"] >= 0.02)]
E["gap>=+2% (2010~)"] = {"n": int(len(g2)), "close_above_open_pct": round(float((g2["oc"] >= 0).mean() * 100), 1),
                          "close_above_open": {"ewy_that_night": summ(g2.loc[g2["oc"] >= 0, "ewy_r"])},
                          "close_below_open": {"ewy_that_night": summ(g2.loc[g2["oc"] < 0, "ewy_r"])}}
OUT["E_gapup_close_vs_open_long"] = E

with open(p("review_stats.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print(json.dumps(OUT, ensure_ascii=False, indent=1))
