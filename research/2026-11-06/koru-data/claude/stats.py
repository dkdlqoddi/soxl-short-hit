"""KORU 2026-11-05 회차 복기 — 교훈 검증용 통계 (Claude Fable Max).
입력: hist/*.pkl (fetch_hist.py). 출력: 표준출력 + stats.json
 S1 꼬리·범위 보정   S2 한국 종가 환산 공정가치(수준)와 EWY 시가   S3 미국장 구간 민감도
 S4 애프터마켓의 정규장 저가 이탈   S5 코스피 갭 하락일   S6 코스피 급락일 밤의 EWY   S7 평균회귀 통계와 다음 날 코스피 갭
실행: python3 stats.py
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

def hl(sym, tz):
    df = pd.read_pickle(H / f"h_{sym}.pkl")
    df.index = df.index.tz_convert(tz)
    return df[["Open", "High", "Low", "Close", "Volume"]]

def summ(x, pct=True):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return {"n": 0}
    m = 100 if pct else 1
    return {"n": int(len(x)), "up": round(float((x > 0).mean() * 100), 1), "mean": round(float(x.mean() * m), 2),
            "median": round(float(x.median() * m), 2), "p10": round(float(x.quantile(.10) * m), 2),
            "q25": round(float(x.quantile(.25) * m), 2), "q75": round(float(x.quantile(.75) * m), 2),
            "min": round(float(x.min() * m), 2)}

def ols(y, X, names):
    y = np.asarray(y, float); X = np.asarray(X, float)
    if X.ndim == 1: X = X.reshape(-1, 1)
    X1 = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ b
    r2 = 1 - (res @ res) / ((y - y.mean()) ** 2).sum()
    return {"n": int(len(y)), "r2": round(float(r2), 3), "coef": {k: round(float(v), 3) for k, v in zip(["const"] + names, b)},
            "resid_sd": round(float(res.std(ddof=X1.shape[1])), 3)}

ewy, koru, spy, sox, soxx, mu, skhy, vix = (dl(s, "America/New_York") for s in ["EWY", "KORU", "SPY", "SOX", "SOXX", "MU", "SKHY", "VIX"])
# period="max" 일봉은 장 마감 직후 11/5 종가가 NaN으로 내려와, 같은 시각 10일 일봉(d1_recent_all.csv)에서 확인한 공식 종가로 보충
for _df, _c in [(ewy, 131.65), (koru, 6.53), (spy, 733.00), (soxx, 131.90), (mu, 656.39), (skhy, 123.90)]:
    if pd.isna(_df.loc["2026-11-05", "Close"]):
        _df.loc["2026-11-05", "Close"] = _c
ks, tr = dl("KS11", "Asia/Seoul"), dl("278540_KS", "Asia/Seoul")
fxd = dl("KRW_X", "Europe/London")
# yfinance 일봉에 11/5 코스피 행이 빠져 있어 1분봉·마감 기사 값으로 보충 (시가 5,580.09 / 고가 5,586.46 / 저가 5,336.88 / 종가 5,383.80)
ks.loc[pd.Timestamp("2026-11-05")] = [5580.09, 5586.46, 5336.88, 5383.80, 0]
ks = ks.sort_index()
ks = ks.loc[:"2026-11-05"]; tr = tr.loc[:"2026-11-05"]

# ------------------------------------------------------------------ S1 꼬리·범위
S1 = {}
for nm, df in [("EWY", ewy), ("KORU", koru), ("SOX", sox), ("SPY", spy), ("MU", mu.loc["2000-01-01":])]:
    r = df["Close"].pct_change(fill_method=None).dropna()
    last = r.iloc[-1]
    worst = r.nsmallest(8)
    S1[f"{nm}_worst"] = {"since": str(r.index[0])[:10], "n": int(len(r)), "last": round(float(last * 100), 2),
                         "rank_from_worst": int((r <= last).sum()),
                         "worst8": {str(k)[:10]: round(float(v * 100), 2) for k, v in worst.items()}}
    print(f"{nm}: since {str(r.index[0])[:10]} N={len(r)} 11/5 {last*100:+.2f}% → 최악 순위 {int((r <= last).sum())}위")
    print("   worst8:", {str(k)[:10]: round(float(v * 100), 2) for k, v in worst.items()})
print("KORU 거래량 11/5:", int(koru["Volume"].iloc[-1]), "순위", int((koru["Volume"] >= koru["Volume"].iloc[-1]).sum()), "최대", str(koru["Volume"].idxmax())[:10], int(koru["Volume"].max()))
S1["KORU_volume_1105"] = {"vol": int(koru["Volume"].iloc[-1]), "rank": int((koru["Volume"] >= koru["Volume"].iloc[-1]).sum())}

# ATR(14)/종가 (단순평균)와 다음 날 수익률의 ATR 배수
k = koru.copy()
pc = k["Close"].shift(1)
trng = pd.concat([k["High"] - k["Low"], (k["High"] - pc).abs(), (k["Low"] - pc).abs()], axis=1).max(axis=1)
k["atrp"] = trng.rolling(14).mean() / k["Close"]
k["r1"] = k["Close"].pct_change(fill_method=None).shift(-1)
k["z"] = k["r1"] / k["atrp"]
print("ATR%% 11/4: %.2f%%  (11/5 일간 %.2f%% = %.2f ATR)" % (k.loc["2026-11-04", "atrp"] * 100, k.loc["2026-11-04", "r1"] * 100, k.loc["2026-11-04", "z"]))
zz = k["z"].dropna()
cov = {f"|z|<={c}": round(float((zz.abs() <= c).mean() * 100), 1) for c in (1, 1.5, 2, 2.5, 3)}
low = {f"z<=-{c}": [int((zz <= -c).sum()), round(float((zz <= -c).mean() * 100), 2)] for c in (1, 1.5, 2, 2.5, 3)}
print("종가→다음 종가 ATR 배수 분포 (2013~, N=%d): 포함률 %s / 하방 꼬리 %s" % (len(zz), cov, low))
print("   z 분위수:", {q: round(float(zz.quantile(q)), 2) for q in (.01, .025, .05, .10, .5, .90, .95, .975, .99)})
S1["cc_atr"] = {"n": int(len(zz)), "atrp_1104": round(float(k.loc["2026-11-04", "atrp"] * 100), 2), "z_1105": round(float(k.loc["2026-11-04", "z"]), 2),
                "coverage": cov, "lower_tail": low, "z_q": {str(q): round(float(zz.quantile(q)), 2) for q in (.01, .025, .05, .10, .90, .95, .975, .99)}}
worstz = zz.nsmallest(8)
print("   z 최악 8:", {str(i)[:10]: [round(float(v), 2), round(float(k.loc[i, 'r1'] * 100), 1)] for i, v in worstz.items()})
S1["cc_atr"]["worst_z"] = {str(i)[:10]: [round(float(v), 2), round(float(k.loc[i, "r1"] * 100), 1)] for i, v in worstz.items()}

# 2년 1시간봉: 애프터마켓(17시 EST 봉 종가) → 다음 거래일 애프터마켓
kh = hl("KORU", "America/New_York")
ah = kh[kh.index.hour == 17]["Close"]
ah.index = pd.to_datetime(ah.index.strftime("%Y-%m-%d"))
ah = ah[~ah.index.duplicated(keep="last")]
a = pd.DataFrame({"ah": ah}).join(k[["Close", "atrp", "Low", "High", "Open"]], how="inner")
a["ret24"] = a["ah"].shift(-1) / a["ah"] - 1
a["gapdays"] = (a.index.to_series().shift(-1) - a.index.to_series()).dt.days
a["z24"] = a["ret24"] / a["atrp"]
a["dayret"] = k["Close"].pct_change(fill_method=None).reindex(a.index)
a["prem"] = a["ah"] / a["Close"] - 1
# 다음 행이 실제 다음 거래일일 때만 사용(17시 봉이 빠진 날을 건너뛰어 며칠치가 합쳐지는 것 방지), 애프터 가격이 종가와 15% 넘게 다른 봉(2026-06-24 한 건)은 오체결로 보고 제외
_nxt = pd.Series(k.index, index=k.index).shift(-1)
a["next_ok"] = (a.index.to_series().shift(-1) == _nxt.reindex(a.index)) & (a["prem"].abs() <= 0.15) & (a["prem"].shift(-1).abs() <= 0.15)
a.loc[~a["next_ok"], ["ret24", "z24"]] = np.nan
a1 = a.dropna(subset=["ret24", "atrp"])
print("애프터→애프터 24h (2년 1시간봉) N=%d: %s" % (len(a1), summ(a1["ret24"])))
print("   분위수:", {q: round(float(a1["ret24"].quantile(q) * 100), 1) for q in (.01, .025, .05, .10, .25, .75, .90, .95, .975, .99)})
z24 = a1["z24"]
cov24 = {f"|z|<={c}": round(float((z24.abs() <= c).mean() * 100), 1) for c in (1, 1.5, 2, 2.5, 3)}
print("   ATR 배수 포함률:", cov24, " z 분위수:", {q: round(float(z24.quantile(q)), 2) for q in (.01, .025, .05, .10, .90, .95, .975, .99)})
row = a.loc["2026-11-04"]
print("   11/4 행: ah=%.3f close=%.2f atrp=%.2f%% ret24=%s z24=%s" % (row["ah"], row["Close"], row["atrp"] * 100, row["ret24"], row["z24"]))
# 노트의 전체 범위 밖으로 나간 비율: Claude −17.1%~+8.3%, Argon −14.0%~+12.5%, Codex 대표 −13.2%~+11.3%
rng = {"Claude 전체 범위 −17.1~+8.3%": (-0.171, 0.083), "Argon 범위 −14.0~+12.5%": (-0.140, 0.125), "Codex 대표 −13.2~+11.3%": (-0.132, 0.113)}
reg = a1.loc["2026-10-08":"2026-11-04"]
S1["ah24"] = {"all": summ(a1["ret24"]), "q": {str(q): round(float(a1["ret24"].quantile(q) * 100), 1) for q in (.01, .025, .05, .10, .90, .95, .975, .99)},
              "coverage_atr": cov24, "z_q": {str(q): round(float(z24.quantile(q)), 2) for q in (.01, .025, .05, .95, .975, .99)}, "range_outside": {}}
for nm, (lo, hi) in rng.items():
    o_all = [float((a1["ret24"] < lo).mean() * 100), float((a1["ret24"] > hi).mean() * 100)]
    hv = a1[a1["atrp"] >= 0.12]
    o_hv = [float((hv["ret24"] < lo).mean() * 100), float((hv["ret24"] > hi).mean() * 100)]
    o_rg = [int((reg["ret24"] < lo).sum()), int((reg["ret24"] > hi).sum()), int(len(reg))]
    S1["ah24"]["range_outside"][nm] = {"all_below_above_pct": [round(v, 1) for v in o_all], "atr>=12%_below_above_pct": [round(v, 1) for v in o_hv], "n_atr>=12%": int(len(hv)), "since_1008_below_above_n": o_rg}
    print(f"   {nm}: 전체 하단 밖 {o_all[0]:.1f}% / 상단 밖 {o_all[1]:.1f}% | ATR≥12% (N={len(hv)}) 하단 밖 {o_hv[0]:.1f}% / 상단 밖 {o_hv[1]:.1f}% | 10/8~11/4 (N={len(reg)}) 하단 밖 {o_rg[0]}건 / 상단 밖 {o_rg[1]}건")
print("   10/8~11/4 24h 수익률:", {str(i)[5:10]: round(float(v * 100), 1) for i, v in reg["ret24"].items()})
print("   10/8~11/4 표준편차 %.1f%%, 평균 %.1f%%, 상승 %d/%d" % (reg["ret24"].std() * 100, reg["ret24"].mean() * 100, (reg["ret24"] > 0).sum(), len(reg)))
S1["ah24"]["since_1008"] = {"rets": {str(i)[5:10]: round(float(v * 100), 1) for i, v in reg["ret24"].items()}, "sd": round(float(reg["ret24"].std() * 100), 1), "up": int((reg["ret24"] > 0).sum()), "n": int(len(reg))}
dn = reg[reg["dayret"] <= -0.04]
print("   10/8 이후 당일 −4%% 이하 (N=%d): 상승 %d, 수익률 %s" % (len(dn), (dn["ret24"] > 0).sum(), {str(i)[5:10]: round(float(v * 100), 1) for i, v in dn["ret24"].items()}))
S1["ah24"]["since_1008_down4"] = {"n": int(len(dn)), "up": int((dn["ret24"] > 0).sum()), "rets": {str(i)[5:10]: round(float(v * 100), 1) for i, v in dn["ret24"].items()}}
OUT["S1"] = S1

# ------------------------------------------------------------------ S2 수준 접근: 한국 종가 환산 공정가치 → EWY 시가
fxh = hl("KRW_X", "Asia/Seoul")
fx15 = {}
for day, g in fxh.groupby(fxh.index.strftime("%Y-%m-%d")):
    g2 = g[g.index.hour <= 15]
    if len(g2):
        fx15[pd.Timestamp(day)] = float(g2["Close"].iloc[-1])
fx15 = pd.Series(fx15)
kr = pd.DataFrame({"tr": tr["Close"], "kospi": ks["Close"], "kospi_open": ks["Open"], "kospi_low": ks["Low"], "kospi_high": ks["High"]}).dropna()
kr["fx"] = fx15.reindex(kr.index).fillna(fxd["Close"].reindex(kr.index))
kr = kr.dropna()
kr["usd"] = kr["tr"] / kr["fx"]
kr["kr_prev"] = kr.index.to_series().shift(1)
us = pd.DataFrame({"ewy": ewy["Close"], "ewy_open": ewy["Open"], "ewy_low": ewy["Low"], "koru": koru["Close"], "koru_open": koru["Open"],
                   "soxx": soxx["Close"], "soxx_open": soxx["Open"], "spy": spy["Close"], "spy_open": spy["Open"], "sox": sox["Close"]}).dropna()
us["us_prev"] = us.index.to_series().shift(1)
j = kr.join(us, how="inner")
j["ratio"] = j["ewy"] / j["usd"]
for w in (20, 60):
    j[f"fair{w}"] = j["ratio"].rolling(w).median().shift(1)
    j[f"prem{w}"] = j["ratio"] / j[f"fair{w}"] - 1
j["jprev"] = j.index.to_series().shift(1)
ok = (j["jprev"] == j["kr_prev"]) & (j["jprev"] == j["us_prev"])
j["krusd_r"] = j["usd"].pct_change(fill_method=None)
j["kospi_r"] = j["kospi"].pct_change(fill_method=None)
j["tr_r"] = j["tr"].pct_change(fill_method=None)
j["ewy_r"] = j["ewy"].pct_change(fill_method=None)
j["koru_r"] = j["koru"].pct_change(fill_method=None)
j["ewy_gap"] = j["ewy_open"] / j["ewy"].shift(1) - 1
j["ewy_oc"] = j["ewy"] / j["ewy_open"] - 1
j["soxx_oc"] = j["soxx"] / j["soxx_open"] - 1
j["spy_oc"] = j["spy"] / j["spy_open"] - 1
j["sox_r"] = j["sox"].pct_change(fill_method=None)
j["ewy_prev_r"] = j["ewy_r"].shift(1)
for w in (20, 60):
    j[f"prem{w}_prev"] = j[f"prem{w}"].shift(1)
    # 시가 환산 공정가치: 직전 미국 종가 시점의 공정 비율(fair) × 오늘 한국 달러 환산 종가 → 직전 EWY 종가 대비
    j[f"fairgap{w}"] = (j[f"fair{w}"].shift(1) * j["usd"]) / j["ewy"].shift(1) - 1   # 직전일까지의 중앙값 비율 사용
    j[f"struct{w}"] = j["krusd_r"] - j[f"prem{w}_prev"]
cols = ["krusd_r", "kospi_r", "tr_r", "ewy_r", "koru_r", "ewy_gap", "ewy_oc", "fairgap20", "fairgap60", "struct20", "struct60"]
j.loc[~ok, cols] = np.nan
S2 = {}
r = j.loc["2026-11-05"]
print("\nS2 11/5 행: 278540 %.0f (%.2f%%), fx15 %.1f, krusd %.2f%%, prem20_prev %.2f%%, prem60_prev %.2f%%, fairgap20 %.2f%%, fairgap60 %.2f%%, EWY 시가 갭 %.2f%%, EWY O→C %.2f%%, SOXX O→C %.2f%%, SPY O→C %.2f%%" % (
    r["tr"], r["tr_r"] * 100, r["fx"], r["krusd_r"] * 100, r["prem20_prev"] * 100, r["prem60_prev"] * 100, r["fairgap20"] * 100, r["fairgap60"] * 100, r["ewy_gap"] * 100, r["ewy_oc"] * 100, r["soxx_oc"] * 100, r["spy_oc"] * 100))
S2["row_1105"] = {c: round(float(r[c] * 100), 2) for c in ["tr_r", "kospi_r", "krusd_r", "prem20_prev", "prem60_prev", "fairgap20", "fairgap60", "ewy_gap", "ewy_oc", "soxx_oc", "spy_oc", "ewy_r", "koru_r"]}
S2["row_1105"]["fx15"] = round(float(r["fx"]), 2)
for label, sub in [("2024-03~2026-11-04", j.loc["2024-03-01":"2026-11-04"]), ("2026 (~11/4)", j.loc["2026-01-01":"2026-11-04"])]:
    s = sub.dropna(subset=["ewy_gap", "fairgap20", "fairgap60", "kospi_r", "ewy_prev_r", "ewy_r"])
    res = {"gap~fairgap20": ols(s["ewy_gap"] * 100, s["fairgap20"] * 100, ["fairgap20"]),
           "gap~fairgap60": ols(s["ewy_gap"] * 100, s["fairgap60"] * 100, ["fairgap60"]),
           "gap~kospi": ols(s["ewy_gap"] * 100, s["kospi_r"] * 100, ["kospi"]),
           "gap~kospi+ewy_prev": ols(s["ewy_gap"] * 100, np.column_stack([s["kospi_r"] * 100, s["ewy_prev_r"] * 100]), ["kospi", "ewy_prev"]),
           "ewy_cc~kospi+ewy_prev (노트 회귀)": ols(s["ewy_r"] * 100, np.column_stack([s["kospi_r"] * 100, s["ewy_prev_r"] * 100]), ["kospi", "ewy_prev"]),
           "mae_gap_vs_fairgap20_pp": round(float((s["ewy_gap"] - s["fairgap20"]).abs().mean() * 100), 2),
           "mae_gap_vs_fairgap60_pp": round(float((s["ewy_gap"] - s["fairgap60"]).abs().mean() * 100), 2),
           "mae_gap_vs_zero_pp": round(float(s["ewy_gap"].abs().mean() * 100), 2)}
    big = s[s["krusd_r"].abs() >= 0.03]
    res["big_korea_days(|krusd|>=3%)"] = {"n": int(len(big)), "gap~fairgap20": ols(big["ewy_gap"] * 100, big["fairgap20"] * 100, ["fairgap20"]) if len(big) > 5 else None,
                                         "mae20_pp": round(float((big["ewy_gap"] - big["fairgap20"]).abs().mean() * 100), 2) if len(big) else None}
    S2[label] = res
    print(label, json.dumps(res, ensure_ascii=False))
# 11/5에 노트 회귀를 그대로 적용했다면
b = S2["2026 (~11/4)"]["ewy_cc~kospi+ewy_prev (노트 회귀)"]["coef"]
pred_old = b["const"] + b["kospi"] * r["kospi_r"] * 100 + b["ewy_prev"] * r["ewy_prev_r"] * 100
print("노트식(2026 재적합) 11/5 EWY 예측 %.2f%% vs 실제 %.2f%% (시가 갭 %.2f%%)" % (pred_old, r["ewy_r"] * 100, r["ewy_gap"] * 100))
S2["old_reg_pred_1105"] = round(float(pred_old), 2)
OUT["S2"] = S2

# ------------------------------------------------------------------ S3 미국장 구간 민감도
S3 = {}
u = pd.DataFrame({"ewy_oc": ewy["Close"] / ewy["Open"] - 1, "soxx_oc": soxx["Close"] / soxx["Open"] - 1, "spy_oc": spy["Close"] / spy["Open"] - 1,
                  "mu_oc": mu["Close"] / mu["Open"] - 1, "koru_oc": koru["Close"] / koru["Open"] - 1}).dropna()
r5 = u.loc["2026-11-05"]
print("\nS3 11/5 O→C: EWY %.2f%% SOXX %.2f%% SPY %.2f%% MU %.2f%% KORU %.2f%%" % tuple(r5[c] * 100 for c in ["ewy_oc", "soxx_oc", "spy_oc", "mu_oc", "koru_oc"]))
S3["oc_1105"] = {c: round(float(r5[c] * 100), 2) for c in u.columns}
for label, sub in [("2024-11~2026-11-04", u.loc["2024-11-01":"2026-11-04"]), ("2026 (~11/4)", u.loc["2026-01-01":"2026-11-04"]), ("2010~2026-11-04", u.loc["2010-01-01":"2026-11-04"])]:
    one = ols(sub["ewy_oc"] * 100, sub["soxx_oc"] * 100, ["soxx"])
    two = ols(sub["ewy_oc"] * 100, np.column_stack([sub["soxx_oc"] * 100, sub["spy_oc"] * 100]), ["soxx", "spy"])
    p1 = one["coef"]["const"] + one["coef"]["soxx"] * r5["soxx_oc"] * 100
    p2 = two["coef"]["const"] + two["coef"]["soxx"] * r5["soxx_oc"] * 100 + two["coef"]["spy"] * r5["spy_oc"] * 100
    tail = sub[sub["soxx_oc"] <= -0.04]
    ratio = (tail["ewy_oc"] / tail["soxx_oc"])
    tl = {"n": int(len(tail)), "ratio_median": round(float(ratio.median()), 2), "ratio_q25": round(float(ratio.quantile(.25)), 2), "ratio_q75": round(float(ratio.quantile(.75)), 2),
          "ewy_oc": summ(tail["ewy_oc"])}
    both = sub[(sub["soxx_oc"] <= -0.04) & (sub["spy_oc"] <= -0.015)]
    rb = both["ewy_oc"] / both["soxx_oc"]
    tb = {"n": int(len(both)), "ratio_median": round(float(rb.median()), 2) if len(both) else None, "ewy_oc": summ(both["ewy_oc"])}
    S3[label] = {"one": one, "two": two, "pred_1105_one": round(float(p1), 2), "pred_1105_two": round(float(p2), 2), "tail_soxx<=-4%": tl, "tail_soxx<=-4%&spy<=-1.5%": tb}
    print(label, json.dumps(S3[label], ensure_ascii=False))
sk = pd.DataFrame({"ewy_oc": ewy["Close"] / ewy["Open"] - 1, "skhy_oc": skhy["Close"] / skhy["Open"] - 1, "soxx_oc": soxx["Close"] / soxx["Open"] - 1,
                   "ewy_r": ewy["Close"].pct_change(fill_method=None), "skhy_r": skhy["Close"].pct_change(fill_method=None)}).dropna().loc[:"2026-11-04"]
S3["skhy"] = {"n": int(len(sk)), "ewy_oc~skhy_oc": ols(sk["ewy_oc"] * 100, sk["skhy_oc"] * 100, ["skhy"]), "ewy_oc~soxx_oc(same sample)": ols(sk["ewy_oc"] * 100, sk["soxx_oc"] * 100, ["soxx"]),
              "ewy_cc~skhy_cc": ols(sk["ewy_r"] * 100, sk["skhy_r"] * 100, ["skhy"]),
              "skhy_oc_1105": round(float((skhy["Close"].iloc[-1] / skhy["Open"].iloc[-1] - 1) * 100), 2), "skhy_cc_1105": round(float(skhy["Close"].pct_change(fill_method=None).iloc[-1] * 100), 2)}
c = S3["skhy"]["ewy_oc~skhy_oc"]["coef"]
S3["skhy"]["pred_1105"] = round(float(c["const"] + c["skhy"] * S3["skhy"]["skhy_oc_1105"]), 2)
print("SKHY", json.dumps(S3["skhy"], ensure_ascii=False))
OUT["S3"] = S3

# ------------------------------------------------------------------ S4 애프터마켓이 정규장 저가를 깬 날
S4 = {}
rows = []
for day, g in kh.groupby(kh.index.strftime("%Y-%m-%d")):
    hm = g.index.hour * 60 + g.index.minute
    regb = g[(hm >= 570) & (hm < 960)]
    ahb = g[(hm >= 960) & (hm < 1200)]
    if len(regb) < 5 or len(ahb) < 2:
        continue
    b19 = g[g.index.hour == 19]
    rows.append({"day": pd.Timestamp(day), "reg_low": regb["Low"].min(), "reg_close": regb["Close"].iloc[-1], "reg_open": regb["Open"].iloc[0],
                 "ah_low": ahb["Low"].min(), "ah_last": ahb["Close"].iloc[-1], "ah17": g[g.index.hour == 17]["Close"].iloc[-1] if (g.index.hour == 17).any() else np.nan,
                 "b19_close": b19["Close"].iloc[-1] if len(b19) else np.nan, "b19_low": b19["Low"].min() if len(b19) else np.nan,
                 "utc_off": g.index[0].utcoffset().total_seconds() / 3600})
q = pd.DataFrame(rows).set_index("day")
q["dayret"] = k["Close"].pct_change(fill_method=None).reindex(q.index)
_nx = pd.Series(k.index, index=k.index).shift(-1)
q["next_ah17"] = q["ah17"].shift(-1).where(q.index.to_series().shift(-1) == _nx.reindex(q.index))   # 다음 행이 실제 다음 거래일일 때만
q["fwd_from_last"] = q["next_ah17"] / q["ah_last"] - 1          # 애프터마켓 마지막 체결(20시 ET) → 다음 날 17시대
q["fwd_from_17"] = q["next_ah17"] / q["ah17"] - 1
q["brk"] = q["ah_low"] < q["reg_low"] * 0.995                   # 정규장 저가를 0.5% 넘게 하향 이탈
q["brk_close"] = q["ah_last"] < q["reg_low"]                    # 애프터마켓 마지막 체결이 정규장 저가 아래
q = q.loc[:"2026-11-04"]
r4 = q.loc["2026-11-04"]
print("\nS4 11/4 행:", {c: (round(float(r4[c]), 4) if isinstance(r4[c], (float, np.floating)) else r4[c]) for c in ["reg_low", "reg_close", "ah_low", "ah_last", "ah17", "b19_close", "dayret", "brk", "brk_close", "fwd_from_last", "fwd_from_17"]})
for label, m in [("전체", q["dayret"].notna()), ("당일 −3% 이하", q["dayret"] <= -0.03), ("당일 −3% 이하 & 겨울 시간(EST)", (q["dayret"] <= -0.03) & (q["utc_off"] == -5))]:
    s = q[m].dropna(subset=["fwd_from_last"])
    S4[label] = {"저가 이탈(저가 기준 0.5%)": summ(s.loc[s["brk"], "fwd_from_last"]), "이탈 없음": summ(s.loc[~s["brk"], "fwd_from_last"]),
                 "마지막 체결이 정규장 저가 아래": summ(s.loc[s["brk_close"], "fwd_from_last"]), "마지막 체결이 저가 위": summ(s.loc[~s["brk_close"], "fwd_from_last"])}
    print(label, json.dumps(S4[label], ensure_ascii=False))
OUT["S4"] = S4

# ------------------------------------------------------------------ S5 코스피 갭 하락일 (2년 1시간봉 + 장기 일봉)
S5 = {}
kh1 = hl("KS11", "Asia/Seoul")
rows = []
for day, g in kh1.groupby(kh1.index.strftime("%Y-%m-%d")):
    if len(g) < 5:
        continue
    rows.append({"day": pd.Timestamp(day), "open": g["Open"].iloc[0], "h09": g[g.index.hour == 9]["Close"].iloc[-1] if (g.index.hour == 9).any() else np.nan,
                 "close": g["Close"].iloc[-1], "low": g["Low"].min()})
kq = pd.DataFrame(rows).set_index("day")
kq["prev_close"] = ks["Close"].shift(1).reindex(kq.index)
kq["gap"] = kq["open"] / kq["prev_close"] - 1
kq["h1"] = kq["h09"] / kq["open"] - 1
kq["oc"] = kq["close"] / kq["open"] - 1
kq["h1_to_close"] = kq["close"] / kq["h09"] - 1
print("\nS5 11/5 행(1시간봉):", kq.loc["2026-11-05"].round(4).to_dict() if pd.Timestamp("2026-11-05") in kq.index else "없음")
kq0 = kq.loc[:"2026-11-04"]
for label, m in [("갭 −1.5% 이하", kq0["gap"] <= -0.015), ("갭 −1.0% 이하", kq0["gap"] <= -0.01)]:
    s = kq0[m].dropna()
    S5[label + " (2년 1시간봉)"] = {"n": int(len(s)), "시가→종가": summ(s["oc"]),
        "10시에 시가 아래": {"n": int((s["h1"] < 0).sum()), "종가<시가 %": round(float((s.loc[s["h1"] < 0, "oc"] < 0).mean() * 100), 1), "10시→종가": summ(s.loc[s["h1"] < 0, "h1_to_close"])},
        "10시에 시가보다 1% 넘게 아래": {"n": int((s["h1"] <= -0.01).sum()), "종가<시가 %": round(float((s.loc[s["h1"] <= -0.01, "oc"] < 0).mean() * 100), 1) if (s["h1"] <= -0.01).any() else None, "10시→종가": summ(s.loc[s["h1"] <= -0.01, "h1_to_close"])},
        "10시에 시가 위": {"n": int((s["h1"] >= 0).sum()), "종가<시가 %": round(float((s.loc[s["h1"] >= 0, "oc"] < 0).mean() * 100), 1), "10시→종가": summ(s.loc[s["h1"] >= 0, "h1_to_close"])}}
    print(label, json.dumps(S5[label + " (2년 1시간봉)"], ensure_ascii=False))
OUT["S5"] = S5

# ------------------------------------------------------------------ S6 코스피 급락일 밤의 EWY, 다음 날 코스피
S6 = {}
kk = ks.copy()
kk["r"] = kk["Close"].pct_change(fill_method=None)
kk["clv"] = (kk["Close"] - kk["Low"]) / (kk["High"] - kk["Low"])
kk["next_r"] = kk["r"].shift(-1)
kk["next_gap"] = kk["Open"].shift(-1) / kk["Close"] - 1
e = pd.DataFrame({"ewy_gap": ewy["Open"] / ewy["Close"].shift(1) - 1, "ewy_oc": ewy["Close"] / ewy["Open"] - 1, "ewy_r": ewy["Close"].pct_change(fill_method=None),
                  "soxx_oc": soxx["Close"] / soxx["Open"] - 1, "spy_r": spy["Close"].pct_change(fill_method=None)})
x = kk.join(e, how="inner")   # 같은 달력 날짜: 한국장(낮) → 미국장(밤)
print("\nS6 11/5 행: 코스피 %.2f%% CLV %.2f / 그날 밤 EWY 갭 %.2f%% O→C %.2f%%" % (x.loc["2026-11-05", "r"] * 100, x.loc["2026-11-05", "clv"], x.loc["2026-11-05", "ewy_gap"] * 100, x.loc["2026-11-05", "ewy_oc"] * 100))
x0 = x.loc["2010-01-01":"2026-11-04"]
for label, m in [("코스피 −3% 이하", x0["r"] <= -0.03), ("코스피 −4% 이하", x0["r"] <= -0.04), ("코스피 −3% 이하 & CLV ≤ 0.2 (저가 부근 마감)", (x0["r"] <= -0.03) & (x0["clv"] <= 0.2)),
                 ("코스피 −3% 이하 & CLV > 0.2", (x0["r"] <= -0.03) & (x0["clv"] > 0.2)), ("코스피 −3% 이하 (2026년)", (x0["r"] <= -0.03) & (x0.index >= "2026-01-01")),
                 ("코스피 −3% 이하 & CLV ≤ 0.2 (2026년)", (x0["r"] <= -0.03) & (x0["clv"] <= 0.2) & (x0.index >= "2026-01-01"))]:
    s = x0[m]
    S6[label] = {"그날 밤 EWY 시가→종가": summ(s["ewy_oc"]), "그날 밤 EWY 일간": summ(s["ewy_r"]), "다음 날 코스피": summ(s["next_r"]), "다음 날 코스피 시가 갭": summ(s["next_gap"])}
    print(label, json.dumps(S6[label], ensure_ascii=False))
s26 = x0[(x0["r"] <= -0.03) & (x0.index >= "2026-01-01")]
print(s26[["r", "clv", "ewy_gap", "ewy_oc", "ewy_r", "soxx_oc", "next_r"]].mul(100).round(1).assign(clv=s26["clv"].round(2)).to_string())
S6["cases_2026"] = {str(i)[:10]: {c: round(float(v[c] * (1 if c == "clv" else 100)), 2) for c in ["r", "clv", "ewy_gap", "ewy_oc", "soxx_oc", "next_r"] if pd.notna(v[c])} for i, v in s26.iterrows()}
OUT["S6"] = S6

# ------------------------------------------------------------------ S7 평균회귀 통계 vs 다음 날 코스피 시가 갭
S7 = {}
kd = koru.copy()
kd["r"] = kd["Close"].pct_change(fill_method=None)
kd["clv"] = (kd["Close"] - kd["Low"]) / (kd["High"] - kd["Low"])
kd["ma20"] = kd["Close"].rolling(20).mean()
kd["dev20"] = kd["Close"] / kd["ma20"] - 1
kd["next_r"] = kd["r"].shift(-1)
kd["next_date"] = kd.index.to_series().shift(-1)
ksg = (ks["Open"] / ks["Close"].shift(1) - 1)
ksr = ks["Close"].pct_change(fill_method=None)
kd["kospi_gap_next"] = ksg.reindex(kd["next_date"].values).values   # 미국 D일 마감 뒤 열리는 한국장(= 다음 미국 거래일과 같은 날짜)의 시가 갭
kd["kospi_r_next"] = ksr.reindex(kd["next_date"].values).values
kd0 = kd.loc[:"2026-11-03"]
setups = {"당일 −4% 이하 & CLV ≤ 0.25": (kd0["r"] <= -0.04) & (kd0["clv"] <= 0.25),
          "당일 −4% 이하 & CLV ≤ 0.25 & 20일선 −15% 이하 (노트 3.1의 72.7% 조건)": (kd0["r"] <= -0.04) & (kd0["clv"] <= 0.25) & (kd0["dev20"] <= -0.15),
          "당일 −5% 이하": kd0["r"] <= -0.05}
for label, m in setups.items():
    s = kd0[m].dropna(subset=["next_r"])
    g1 = s[s["kospi_gap_next"] <= -0.015]; g2 = s[(s["kospi_gap_next"] > -0.015) & (s["kospi_gap_next"] <= -0.005)]; g3 = s[s["kospi_gap_next"] > -0.005]
    S7[label] = {"전체": summ(s["next_r"]), "다음 코스피 시가 갭 −1.5% 이하": summ(g1["next_r"]), "갭 −1.5~−0.5%": summ(g2["next_r"]), "갭 −0.5% 초과": summ(g3["next_r"]),
                 "다음 코스피 종가 −3% 이하": summ(s.loc[s["kospi_r_next"] <= -0.03, "next_r"]), "다음 코스피 종가 −1~−3%": summ(s.loc[(s["kospi_r_next"] > -0.03) & (s["kospi_r_next"] <= -0.01), "next_r"]),
                 "다음 코스피 종가 −1% 초과": summ(s.loc[s["kospi_r_next"] > -0.01, "next_r"])}
    print("\n" + label, json.dumps(S7[label], ensure_ascii=False))
print("11/4 행:", {c: round(float(kd.loc["2026-11-04", c]), 4) for c in ["r", "clv", "dev20", "next_r", "kospi_gap_next", "kospi_r_next"]})
OUT["S7"] = S7

json.dump(OUT, open(D / "stats.json", "w"), ensure_ascii=False, indent=1, default=str)
j.loc["2026-10-01":, ["tr", "fx", "usd", "ewy", "ewy_open", "ratio", "fair20", "fair60", "prem20", "prem60", "krusd_r", "fairgap20", "fairgap60", "ewy_gap", "ewy_oc", "soxx_oc", "spy_oc"]].round(5).to_csv(D / "stats_fairvalue_recent.csv")
print("\nsaved stats.json")
