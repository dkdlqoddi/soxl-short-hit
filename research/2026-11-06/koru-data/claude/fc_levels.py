"""A. 수준 계산: KORU NAV 근사, EWY의 한국 종가 환산 공정가치(20일·60일 중앙값 비율), 기준가가 요구하는 한국장 종가.
B. 11/6 장중 경로(1분봉). 실행: python3 fc_levels.py"""
import json, urllib.request
import numpy as np, pandas as pd
from fc_common import *

OUT = {}
ewy, koru, soxx, spy = (dl(s, "America/New_York") for s in ["EWY", "KORU", "SOXX", "SPY"])
ks, tr = dl("^KS11", "Asia/Seoul"), dl("278540.KS", "Asia/Seoul")
fxd = dl("KRW=X", "Europe/London")
print("EWY tail\n", ewy.tail(4)); print("KORU tail\n", koru.tail(4)); print("KS tail\n", ks.tail(3)); print("TR tail\n", tr.tail(3))

# Nasdaq API로 11/5 공식 종가 교차 확인
def nasdaq(sym):
    url = f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass=etf&fromdate=2026-10-25&todate=2026-11-06&limit=20"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            rows = json.load(r)["data"]["tradesTable"]["rows"]
        return rows[:4]
    except Exception as e:
        return f"ERR {e}"
for s in ["KORU", "EWY"]:
    print("NASDAQ", s, nasdaq(s))

# --- KORU 일간 수익률 vs 3×EWY (종가 기준 괴리 = NAV 대비 할증 변화)
j = pd.DataFrame({"koru": koru["Close"], "ewy": ewy["Close"]}).dropna()
j["kr"] = j["koru"].pct_change(); j["er"] = j["ewy"].pct_change()
j["gap"] = (1 + j["kr"]) / (1 + 3 * j["er"]) - 1
print("\nKORU vs 3xEWY 일간 괴리 (최근 15일)\n", (j[["koru", "ewy", "kr", "er", "gap"]].tail(15) * [1, 1, 100, 100, 100]).round(3))
g26 = j.loc["2026-01-01":"2026-11-04", "gap"]
print("2026 괴리 분포(%):", summ(g26))
OUT["koru_vs_3x_gap_2026"] = summ(g26)
EWY_C, EWY_P, KORU_P, KORU_C = float(ewy.loc["2026-11-05", "Close"]), float(ewy.loc["2026-11-04", "Close"]), float(koru.loc["2026-11-04", "Close"]), float(koru.loc["2026-11-05", "Close"])
nav = KORU_P * (1 + 3 * (EWY_C / EWY_P - 1))
print(f"\nEWY 11/4 {EWY_P} → 11/5 {EWY_C} ({(EWY_C/EWY_P-1)*100:+.2f}%), KORU 11/4 {KORU_P} → 11/5 {KORU_C} ({(KORU_C/KORU_P-1)*100:+.2f}%)")
print(f"KORU NAV 근사(11/4 종가=NAV 가정) = {nav:.4f}, 종가 할증 {(KORU_C/nav-1)*100:+.2f}%")
OUT["nav_est"] = round(nav, 4); OUT["close_premium_to_nav_pct"] = round((KORU_C / nav - 1) * 100, 2)

# --- 1분봉: 11/5 정규장 마지막 연속 체결과 애프터마켓 경로
k1, e1, s1, mu1, sp1 = m1("KORU"), m1("EWY"), m1("SOXX"), m1("MU"), m1("SPY")
def at(df, ts):
    ts = pd.Timestamp(ts, tz="Asia/Seoul")
    x = df.loc[:ts]
    return float(x["Close"].iloc[-1]), x.index[-1].strftime("%m/%d %H:%M")
print("\n애프터마켓 경로 (KST) KORU / EWY / KORU 이론가(NAV×(1+3×(EWY/131.65−1))) / 괴리 / SOXX / MU / SPY")
rows = []
for t in ["2026-11-06 05:59", "2026-11-06 06:10", "2026-11-06 06:30", "2026-11-06 07:00", "2026-11-06 07:30", "2026-11-06 08:00", "2026-11-06 08:20", "2026-11-06 08:40", "2026-11-06 08:59", "2026-11-06 09:03", "2026-11-06 09:10", "2026-11-06 09:20", "2026-11-06 09:30", "2026-11-06 09:39", "2026-11-06 09:45", "2026-11-06 09:50", "2026-11-06 09:55", "2026-11-06 09:59"]:
    kp, kt = at(k1, t); ep, et = at(e1, t); sp_, _ = at(s1, t); mp, _ = at(mu1, t); spp, _ = at(sp1, t)
    theo = nav * (1 + 3 * (ep / EWY_C - 1))
    rows.append((t[5:], kp, kt, ep, et, round(theo, 3), round((kp / theo - 1) * 100, 2), sp_, mp, spp))
    print(t[5:], f"KORU {kp:.3f}({kt[-5:]}) EWY {ep:.2f}({et[-5:]}) theo {theo:.3f} gap {(kp/theo-1)*100:+.2f}% SOXX {sp_:.2f} MU {mp:.2f} SPY {spp:.2f}")
OUT["afterhours_path"] = rows
# 마지막 30분 애프터마켓 체결 통계
for nm, df in [("KORU", k1), ("EWY", e1), ("SOXX", s1)]:
    seg = df.loc["2026-11-06 09:30":"2026-11-06 09:59"]
    print(nm, "09:30~09:59 KST: n", len(seg), "low", seg["Low"].min(), "high", seg["High"].max(), "last", seg["Close"].iloc[-1], "vol", int(seg["Volume"].sum()), "median close", round(float(seg["Close"].median()), 3))
seg = k1.loc["2026-11-06 06:00":"2026-11-06 09:59"]
print("KORU 애프터 전체: low", seg["Low"].min(), seg["Low"].idxmin(), "high", seg["High"].max(), seg["High"].idxmax(), "vol", int(seg["Volume"].sum()))
seg = k1.loc["2026-11-05 23:30":"2026-11-06 05:59"]
print("KORU 정규장 11/5: open", seg["Open"].iloc[0], "low", seg["Low"].min(), seg["Low"].idxmin(), "high", seg["High"].max(), seg["High"].idxmax(), "last1m", seg["Close"].iloc[-1])
seg = e1.loc["2026-11-05 23:30":"2026-11-06 05:59"]
print("EWY 정규장 11/5: open", seg["Open"].iloc[0], "low", seg["Low"].min(), "high", seg["High"].max(), "last1m", seg["Close"].iloc[-1])

# --- 공정가치: EWY ÷ (278540 ÷ 원/달러 15:30)
fxh = hl("KRW=X", "Asia/Seoul")
fx15 = {}
for day, g in fxh.groupby(fxh.index.strftime("%Y-%m-%d")):
    g2 = g[g.index.hour <= 15]
    if len(g2):
        fx15[pd.Timestamp(day)] = float(g2["Close"].iloc[-1])
fx15 = pd.Series(fx15)
kr = pd.DataFrame({"tr": tr["Close"], "kospi": ks["Close"]}).dropna()
kr["fx"] = fx15.reindex(kr.index).fillna(fxd["Close"].reindex(kr.index))
kr = kr.loc[:"2026-11-05"].dropna()
kr["usd"] = kr["tr"] / kr["fx"]
us = pd.DataFrame({"ewy": ewy["Close"]}).dropna()
jj = kr.join(us, how="inner")
jj["ratio"] = jj["ewy"] / jj["usd"]
for w in (20, 60):
    jj[f"med{w}"] = jj["ratio"].rolling(w).median().shift(1)       # 전일까지의 중앙값
    jj[f"prem{w}"] = jj["ratio"] / jj[f"med{w}"] - 1
print("\n공정가치 표 (최근 12행)\n", jj.tail(12).round(4))
last = jj.loc["2026-11-05"]
# 11/5 종가 시점의 공정 비율: 11/4까지의 중앙값(=복기 노트 방식). 11/5 값을 포함한 중앙값도 함께.
med20_incl = jj["ratio"].iloc[-20:].median(); med60_incl = jj["ratio"].iloc[-60:].median()
usd_1105 = float(last["usd"])
fair = {"20d": float(last["med20"]) * usd_1105, "60d": float(last["med60"]) * usd_1105, "20d_incl": med20_incl * usd_1105, "60d_incl": med60_incl * usd_1105}
print("11/5 한국 종가 환산 EWY 공정가치:", {k: round(v, 2) for k, v in fair.items()}, "TR", last["tr"], "fx15", last["fx"], "usd", round(usd_1105, 4))
OUT["fair_1105"] = {k: round(v, 2) for k, v in fair.items()}
OUT["prem_at_close"] = {k: round((EWY_C / v - 1) * 100, 2) for k, v in fair.items()}
print("EWY 공식 종가 131.65의 할증률(%):", OUT["prem_at_close"])
BASE = 6.4585
ewy_ah = 133.13
ewy_impl = EWY_C * (1 + (BASE / nav - 1) / 3)
print(f"기준가 {BASE} ↔ EWY 환산 {ewy_impl:.2f} (EWY 애프터 마지막 체결 {ewy_ah}); 종가 대비 {(ewy_impl/EWY_C-1)*100:+.2f}%")
OUT["ewy_implied_by_base"] = round(ewy_impl, 2)
for k in ("20d", "60d"):
    need = ewy_impl / fair[k] - 1
    print(f"  [{k}] 기준가가 요구하는 한국 달러 수익률 {need*100:+.2f}%  (EWY 애프터 133.13 기준 {(ewy_ah/fair[k]-1)*100:+.2f}%, 공식 종가 기준 {(EWY_C/fair[k]-1)*100:+.2f}%)")
    OUT[f"need_krusd_{k}"] = round(need * 100, 2)

# --- 오늘 한국장 1분봉 경로
kk, t1, ss, hx = m1("^KS11"), m1("278540.KS"), m1("005930.KS"), m1("000660.KS")
fx1 = m1("KRW=X")
KS_P, TR_P, SS_P, HX_P, FX_P = 5383.80, 30005.0, 201500.0, 1264000.0, float(last["fx"])
print("\n11/6 한국장 경로 (yfinance 1분봉, 지연 가능) — 코스피 / TR / 삼성 / 하이닉스 / 원달러 / 달러 환산 한국 수익률")
rows = []
T0 = pd.Timestamp("2026-11-06 09:00", tz="Asia/Seoul")
for t in ["09:01", "09:03", "09:05", "09:34", "09:40", "09:50", "09:59", "10:10", "10:20", "10:30", "10:40", "10:42", "10:45"]:
    ts = pd.Timestamp("2026-11-06 " + t, tz="Asia/Seoul")
    def v(df):
        x = df.loc[T0:ts]
        return (float(x["Close"].iloc[-1]), x.index[-1].strftime("%H:%M")) if len(x) else (np.nan, "")
    a, at_ = v(kk); b, bt = v(t1); c, _ = v(ss); d, _ = v(hx)
    f = float(fx1.loc[:ts]["Close"].iloc[-1])
    usd = (b / f) / (TR_P / FX_P) - 1 if not np.isnan(b) else np.nan
    rows.append((t, a, at_, round((a / KS_P - 1) * 100, 2), b, bt, round((b / TR_P - 1) * 100, 2), round((c / SS_P - 1) * 100, 2), round((d / HX_P - 1) * 100, 2), f, round(usd * 100, 2)))
    print(t, f"KOSPI {a:.2f}({at_}) {(a/KS_P-1)*100:+.2f}% | TR {b:.0f}({bt}) {(b/TR_P-1)*100:+.2f}% | 삼성 {(c/SS_P-1)*100:+.2f}% 하이닉스 {(d/HX_P-1)*100:+.2f}% | fx {f:.1f} | 한국USD {usd*100:+.2f}%")
OUT["korea_path"] = rows
seg = kk.loc[T0:]
print("코스피 1분봉 저가", seg["Low"].min(), seg["Low"].idxmin(), "고가", seg["High"].max(), seg["High"].idxmax(), "첫봉", seg.iloc[0].to_dict())
dump(OUT, "fc_levels.json")
