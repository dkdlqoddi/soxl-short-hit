"""KORU 2026-11-04 회차 복기 — 보조 통계 (Claude Fable Max). review_stats.py 실행 뒤에 돌린다.

1. 갭 상승일에 기준가가 요구한 코스피 수준(+3.4% = 시가 +0.98%) 이상으로 마감한 비율
2. 11/3형(전일 +4% 이상 & 애프터 프리미엄 +2.5% 이상)의 24시간 통계 — 11/3 자신을 뺀 값 포함
3. 겨울 시간(EST)에 미국 반도체 등락이 다음 날 아침(08:59 KST) 애프터마켓가에 한 번 더 반영되는지
4. 확률 예측의 Brier 점수
5. 2요인식(수준 괴리 + SOXX)으로 본 11/4 EWY

실행: python3 review_stats_extra.py → review_stats_extra.json
"""
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def p(name: str) -> str:
    return os.path.join(HERE, name)


def summ(s: pd.Series) -> dict:
    s = s.dropna()
    if not len(s):
        return {"n": 0}
    return {"n": int(len(s)), "up": round(float((s > 0).mean() * 100), 1), "mean": round(float(s.mean() * 100), 2),
            "median": round(float(s.median() * 100), 2), "q25": round(float(s.quantile(0.25) * 100), 2), "q75": round(float(s.quantile(0.75) * 100), 2)}


out: dict = {}

# 1. 갭 상승일 분포 (2010~, 코스피·EWY 모두 거래한 날)
x = pd.read_csv(p("review_stats_gapup_long.csv"), index_col=0, parse_dates=True)
need_oc = 5843 / 5786.13 - 1  # 기준가 $11.39가 가정한 코스피 5,843 ÷ 시가 5,786.13
g1 = {}
for nm, g in [("gap>=+2% (2010~)", x[x["gap"] >= 0.02]), ("gap +2~3% (2010~)", x[(x["gap"] >= 0.02) & (x["gap"] < 0.03)]),
              ("gap>=+2% (2026)", x[(x["gap"] >= 0.02)].loc["2026-01-01":]),
              ("gap>=+2% (2010~, 11/4 제외)", x[(x["gap"] >= 0.02)].drop(pd.Timestamp("2026-11-04"), errors="ignore"))]:
    g1[nm] = {"n": int(len(g)), "need_oc_pct": round(need_oc * 100, 2),
              "p_close_ge_needed_level": round(float((g["oc"] >= need_oc).mean() * 100), 1),
              "p_close_above_open": round(float((g["oc"] >= 0).mean() * 100), 1),
              "p_day_ge_+3.4%": round(float((g["k_r"] >= 0.034).mean() * 100), 1),
              "p_day_lt_+1.0%": round(float((g["k_r"] < 0.01).mean() * 100), 1),
              "oc_mean": round(float(g["oc"].mean() * 100), 2), "oc_median": round(float(g["oc"].median() * 100), 2)}
out["1_gapup_needed_level"] = g1

# 2. 11/3형 24시간 통계
b = pd.read_csv(p("review_stats_ah_premium.csv"), index_col=0, parse_dates=True)
ex = b.drop(pd.Timestamp("2026-11-03"), errors="ignore")
g2 = {}
for nm, f in [("dayret>=+4% & prem>=+2.5%", lambda d: d[(d["dayret"] >= 0.04) & (d["prem"] >= 0.025)]),
              ("dayret>=+4% & prem>=+1.5%", lambda d: d[(d["dayret"] >= 0.04) & (d["prem"] >= 0.015)]),
              ("prem>=+2.5%", lambda d: d[d["prem"] >= 0.025])]:
    g2[nm] = {"incl_1103": {"vs_base": summ(f(b)["r_base"]), "vs_close": summ(f(b)["r_vs_close"]), "c2c": summ(f(b)["r_c2c"])},
              "excl_1103": {"vs_base": summ(f(ex)["r_base"]), "vs_close": summ(f(ex)["r_vs_close"]), "c2c": summ(f(ex)["r_c2c"])},
              "2026_excl_1103": {"vs_base": summ(f(ex.loc["2026-01-01":])["r_base"]), "vs_close": summ(f(ex.loc["2026-01-01":])["r_vs_close"]),
                                 "c2c": summ(f(ex.loc["2026-01-01":])["r_c2c"])}}
out["2_1103_type_24h"] = g2

# 3. 겨울 시간(EST) 아침 애프터마켓의 미국 반도체 메아리
sx = pd.read_csv(p("h_d1_SOXX.csv"), index_col=0)
sx.index = pd.to_datetime(pd.to_datetime(sx.index, utc=True).tz_convert("America/New_York").strftime("%Y-%m-%d"))
b["soxx_r"] = sx["Close"].pct_change().reindex(b.index)
kh = pd.read_csv(p("h_h1_KORU.csv"), index_col=0)
idx = pd.to_datetime(kh.index, utc=True).tz_convert("America/New_York")
off = pd.Series([t.utcoffset().total_seconds() / 3600 for t in idx], index=pd.to_datetime(idx.strftime("%Y-%m-%d"))).groupby(level=0).first()
b["est"] = off.reindex(b.index) == -5
nxt = b.index >= pd.Timestamp("2025-03-04")  # 넥스트레이드 출범
g3 = {
    "EST·NXT 이후 전체": summ(b.loc[b["est"] & nxt, "prem"]),
    "EST·NXT 이후 & SOXX<=-2%": summ(b.loc[b["est"] & nxt & (b["soxx_r"] <= -0.02), "prem"]),
    "EST·NXT 이후 & SOXX>=+2%": summ(b.loc[b["est"] & nxt & (b["soxx_r"] >= 0.02), "prem"]),
    "EDT & SOXX<=-2%": summ(b.loc[(~b["est"]) & (b["soxx_r"] <= -0.02), "prem"]),
    "EDT & SOXX>=+2%": summ(b.loc[(~b["est"]) & (b["soxx_r"] >= 0.02), "prem"]),
    "note": "prem = 18시 ET 1시간봉 종가(≈18:59 ET = 겨울 08:59 KST, 여름 07:59 KST) ÷ 정규장 종가 − 1",
}
out["3_morning_echo"] = g3

# 4. Brier 점수 (상승=1, 하락=0; 실제 결과는 두 기준 모두 하락)
def brier(prob_up: float, up: int) -> float:
    return round((prob_up - up) ** 2, 4)


out["4_brier"] = {
    "vs_base": {"Antigravity Argon High (상승 35~40% → 0.375)": brier(0.375, 0), "Claude Fable Max (상승 45%)": brier(0.45, 0),
                "동전 던지기 (50%)": brier(0.5, 0), "Codex Astra Max": "확률 미제시"},
    "vs_prev_close": {"Antigravity Argon High (상승 45%)": brier(0.45, 0), "Claude Fable Max (상승 55%)": brier(0.55, 0),
                      "동전 던지기 (50%)": brier(0.5, 0), "Codex Astra Max": "미제시"},
}

# 5. 2요인식으로 본 11/4 EWY
st = json.load(open(p("review_stats.json"), encoding="utf-8"))
row = st["A_level_vs_return_regression"]["recent_rows"]["2026-11-04T00:00:00.000"]
struct = row["struct"] * 100
soxx, spy = -3.1376, 1.6504
g5 = {"struct_pct(한국 달러 수익률 − 11/3 종가 괴리)": round(struct, 2), "soxx_pct": soxx, "spy_pct": spy, "actual_ewy_pct": round(row["ewy_r"] * 100, 2)}
for nm in ["close→close 2025-01~2026-11 (struct + soxx + spy)", "close→close 2026 (struct + soxx + spy)"]:
    c = st["C_ewy_soxx_spy"][nm]["coef"]
    g5[nm] = {"coef": c, "r2": st["C_ewy_soxx_spy"][nm]["r2"], "n": st["C_ewy_soxx_spy"][nm]["n"],
              "pred_pct": round(c["const"] + c["struct"] * struct + c["soxx"] * soxx + c["spy"] * spy, 2),
              "parts": {"struct": round(c["struct"] * struct, 2), "soxx": round(c["soxx"] * soxx, 2), "spy": round(c["spy"] * spy, 2)}}
old = st["A_level_vs_return_regression"]["2026"]["reg_old(kospi, ewy_prev)"]["coef"]
g5["old_regression_2026(kospi, ewy_prev)"] = {"coef": old, "pred_pct": round(old["const"] + old["kospi"] * 0.6198 + old["ewy_prev"] * 2.2688, 2)}
lvl = st["A_level_vs_return_regression"]["2026"]["reg_level(krusd, prem_prev)"]["coef"]
g5["level_regression_2026(krusd, prem_prev)"] = {"coef": lvl, "pred_pct": round(lvl["const"] + lvl["krusd"] * row["krusd_r"] * 100 + lvl["prem_prev"] * 1.757, 2)}
out["5_two_factor_1104"] = g5

with open(p("review_stats_extra.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
