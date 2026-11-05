import json
import os
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-05/koru-data/argon"

# 1. Exact scoring arithmetic for the 3 models
models_check = [
    {
        "model": "Codex Astra Max",
        "base_time": "2026-11-04 08:43",
        "base_price": 11.41,
        "prev_close": 11.01,
        "expiry_time": "2026-11-05 08:43",
        "expiry_price": 10.3800, # 08:43 1m close = $10.3800 (O=10.38, H=10.38, L=10.37, C=10.38)
    },
    {
        "model": "Antigravity Argon High",
        "base_time": "2026-11-04 08:55",
        "base_price": 11.30,
        "prev_close": 11.01,
        "expiry_time": "2026-11-05 08:55",
        "expiry_price": 10.3297, # 08:55 1m close = $10.3297 (O=10.35, H=10.35, L=10.3297, C=10.3297)
    },
    {
        "model": "Claude Fable Max",
        "base_time": "2026-11-04 09:10",
        "base_price": 11.39,
        "prev_close": 11.01,
        "expiry_time": "2026-11-05 09:10",
        "expiry_price": 10.3000, # 09:10 1m close = $10.3000 (O=10.31, H=10.3354, L=10.29, C=10.30)
    },
]

print("=== EXACT SCORING ARITHMETIC ===")
for m in models_check:
    chg_base = (m["expiry_price"] / m["base_price"] - 1) * 100
    chg_prev_at_exp = (m["expiry_price"] / m["prev_close"] - 1) * 100
    chg_prev_reg_close = (10.43 / m["prev_close"] - 1) * 100
    m["chg_base_pct"] = round(chg_base, 2)
    m["chg_prev_at_exp_pct"] = round(chg_prev_at_exp, 2)
    m["chg_prev_reg_close_pct"] = round(chg_prev_reg_close, 2)
    print(f"{m['model']}: base=${m['base_price']:.2f} -> exp=${m['expiry_price']:.4f} ({chg_base:+.2f}%) | vs 11/3 reg close $11.01: 11/4 reg close $10.43 ({chg_prev_reg_close:+.2f}%), 11/5 exp ({chg_prev_at_exp:+.2f}%)")

# 2. Check iNAV convergence math on 11/3 -> 11/4 -> 11/5
# On 11/3 KR close: 278540.KS = 31,750 KRW, USDKRW ~ 1,343.9 -> EWY fair value estimated by Argon = $151.75
# On 11/4 KR close (15:30 KST): 278540.KS = 31,760 KRW (+0.031%), USDKRW ~ 1,340.7 (-0.24%) -> USD return of 278540.KS = +0.27% -> EWY fair value = $151.75 * (31760/31750) * (1343.9/1340.7) = $152.16!
ewy_fv_1104 = 151.75 * (31760 / 31750) * (1343.9 / 1340.7)
print(f"\n=== iNAV CONVERGENCE CHECK ===")
print(f"11/4 15:30 KST implied EWY fair value: ${ewy_fv_1104:.2f} vs actual 11/4 US regular close EWY = $152.12 (diff = {(152.12/ewy_fv_1104 - 1)*100:+.2f}%!)")
print(f"Wait: EWY fell from $155.06 (11/3 reg close) and $156.23~$156.96 (11/4 morning AH) right down to $152.12 — literally $0.04 away from 11/4 Korean close fair value (${ewy_fv_1104:.2f})!")

# On 11/5 13:22 KST (current Naver check): 278540.KS = 30,160 (-5.04% vs 31,760), USDKRW = 1,343.08 (+0.18% vs 1,340.7)
ewy_fv_1105_mid = ewy_fv_1104 * (30160 / 31760) * (1340.7 / 1343.08)
koru_implied_1105 = 10.43 * (1 + 3 * (ewy_fv_1105_mid / 152.12 - 1))
print(f"11/5 13:22 KST implied EWY fair value: ${ewy_fv_1105_mid:.2f} ({(ewy_fv_1105_mid/152.12 - 1)*100:+.2f}% vs 11/4 EWY close $152.12) -> implied KORU ~ ${koru_implied_1105:.2f} (note: 09:59 KST AH closed at $9.89 when KOSPI was ~5,496 / -3.3%)")

# 3. Historical decoupling backtest (2016-11 ~ 2026-11, 10 years daily):
# When Nasdaq (^IXIC) or S&P500 (^GSPC) rises (>0%), BUT Semiconductors (SOXX < -1.5%) or Micron (MU < -3.0%) drop, how do EWY and KORU behave on the same US day?
syms = ["KORU", "EWY", "^IXIC", "^GSPC", "SOXX", "MU"]
hist = {}
for s in syms:
    d = yf.Ticker(s).history(period="10y", interval="1d")["Close"]
    d.index = d.index.tz_localize(None).normalize()
    hist[s] = d.pct_change() * 100

df_ret = pd.DataFrame(hist).dropna()
df_ret = df_ret[df_ret.index <= "2026-11-04"]

print(f"\n=== 10Y DECOUPLING BACKTEST (N_total={len(df_ret)}, {df_ret.index[0].strftime('%Y-%m-%d')}~{df_ret.index[-1].strftime('%Y-%m-%d')}) ===")
conds = [
    ("Nasdaq > +0.5% (unconditional)", df_ret["^IXIC"] > 0.5),
    ("Nasdaq > 0% & SOXX <= -1.5% (11/4 type: IXIC +1.44%, SOXX -3.14%)", (df_ret["^IXIC"] > 0) & (df_ret["SOXX"] <= -1.5)),
    ("S&P500 > +0.5% & SOXX <= -1.5% (11/4 type: GSPC +1.58%, SOXX -3.14%)", (df_ret["^GSPC"] > 0.5) & (df_ret["SOXX"] <= -1.5)),
    ("Nasdaq > 0% & MU <= -3.0% (11/4 type: MU -7.00%)", (df_ret["^IXIC"] > 0) & (df_ret["MU"] <= -3.0)),
    ("2025~2026 AI regime: Nasdaq > 0% & SOXX <= -1.0%", (df_ret.index >= "2025-01-01") & (df_ret["^IXIC"] > 0) & (df_ret["SOXX"] <= -1.0)),
]

backtest_rows = []
for name, mask in conds:
    sub = df_ret[mask]
    n = len(sub)
    if n > 0:
        koru_up = (sub["KORU"] > 0).mean() * 100
        koru_mean = sub["KORU"].mean()
        koru_med = sub["KORU"].median()
        ewy_up = (sub["EWY"] > 0).mean() * 100
        ewy_med = sub["EWY"].median()
        print(f"{name}: N={n} | KORU up={koru_up:.1f}%, mean={koru_mean:+.2f}%, median={koru_med:+.2f}% | EWY up={ewy_up:.1f}%, median={ewy_med:+.2f}%")
        backtest_rows.append({
            "condition": name, "N": int(n),
            "koru_up_pct": round(float(koru_up), 1),
            "koru_mean_pct": round(float(koru_mean), 2),
            "koru_median_pct": round(float(koru_med), 2),
            "ewy_up_pct": round(float(ewy_up), 1),
            "ewy_median_pct": round(float(ewy_med), 2),
        })

with open(os.path.join(OUT_DIR, "review_metrics.json"), "w", encoding="utf-8") as f:
    json.dump({"scores_calc": models_check, "ewy_fv_1104": round(ewy_fv_1104, 2), "decoupling_backtest": backtest_rows}, f, ensure_ascii=False, indent=2)
