#!/usr/bin/env python3
import json
import os
import pandas as pd
import numpy as np
import yfinance as yf
import pytz

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"
kst = pytz.timezone("Asia/Seoul")
est = pytz.timezone("America/New_York")

# 1. Check exact KRW=X and Korean 5m bars on 2026-11-05 and 2026-11-06
krwx_5m = pd.read_csv(os.path.join(OUT_DIR, "krwx_5m_window.csv"))
ks11_5m = pd.read_csv(os.path.join(OUT_DIR, "ks11_5m_window.csv"))
msci_5m = pd.read_csv(os.path.join(OUT_DIR, "278540_5m_window.csv"))
vix_5m = pd.read_csv(os.path.join(OUT_DIR, "vix_5m_window.csv"))
smsn_5m = pd.read_csv(os.path.join(OUT_DIR, "smsn_5m_window.csv"))

for df in [krwx_5m, ks11_5m, msci_5m, vix_5m, smsn_5m]:
    df["dt_kst"] = pd.to_datetime(df["ts_kst"])

print("=== KRW=X Key Timestamps ===")
for t_target in [
    "2026-11-05 07:35", "2026-11-05 09:00", "2026-11-05 10:15", "2026-11-05 15:30",
    "2026-11-05 18:00", "2026-11-05 21:00", "2026-11-05 22:30", "2026-11-05 23:30",
    "2026-11-06 01:00", "2026-11-06 06:00", "2026-11-06 07:35", "2026-11-06 09:05", "2026-11-06 09:40"
]:
    sub = krwx_5m[krwx_5m["dt_kst"] <= pd.Timestamp(t_target + ":00+09:00")]
    if not sub.empty:
        r = sub.iloc[-1]
        print(f"  <= {t_target} -> {r['ts_kst']} Close={r['Close']:.2f} (H={r['High']:.2f}, L={r['Low']:.2f})")

print("\n=== KS11 Intraday on 2026-11-05 ===")
ks_1105 = ks11_5m[(ks11_5m["dt_kst"] >= "2026-11-05 09:00:00+09:00") & (ks11_5m["dt_kst"] <= "2026-11-05 15:35:00+09:00")]
if not ks_1105.empty:
    print(f"  11/5 Open={ks_1105.iloc[0]['Open']:.2f}, High={ks_1105['High'].max():.2f} at {ks_1105.loc[ks_1105['High'].idxmax(),'ts_kst']}, Low={ks_1105['Low'].min():.2f} at {ks_1105.loc[ks_1105['Low'].idxmin(),'ts_kst']}, Last5m={ks_1105.iloc[-1]['Close']:.2f}")
    for t_check in ["09:00", "09:10", "09:30", "10:00", "10:15", "10:20", "11:00", "12:00", "13:20", "14:25", "14:30", "15:20"]:
        r = ks_1105[ks_1105["ts_kst"].str.contains(f"2026-11-05 {t_check}:")]
        if not r.empty:
            row = r.iloc[-1]
            print(f"    {row['ts_kst']} | O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f}")

print("\n=== KS11 Intraday on 2026-11-06 ===")
ks_1106 = ks11_5m[ks11_5m["dt_kst"] >= "2026-11-06 09:00:00+09:00"]
for _, row in ks_1106.iterrows():
    print(f"    {row['ts_kst']} | O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f}")

print("\n=== SMSN.IL (Samsung London GDR) on 2026-11-05 ~ 11-06 ===")
smsn_1105 = smsn_5m[smsn_5m["dt_kst"] >= "2026-11-05 17:00:00+09:00"]
if not smsn_1105.empty:
    print(f"  First={smsn_1105.iloc[0]['ts_kst']} O={smsn_1105.iloc[0]['Open']:.2f}, High={smsn_1105['High'].max():.2f}, Low={smsn_1105['Low'].min():.2f}, Last={smsn_1105.iloc[-1]['ts_kst']} C={smsn_1105.iloc[-1]['Close']:.2f}")

print("\n=== VIX Intraday on 2026-11-05 US session (KST) ===")
vix_sub = vix_5m[vix_5m["dt_kst"] >= "2026-11-05 17:00:00+09:00"]
for t_v in ["18:00", "21:00", "22:30", "23:30", "00:00", "01:00", "02:00", "04:00", "05:55", "06:00"]:
    r = vix_sub[vix_sub["ts_kst"].str.contains(f" {t_v}:")]
    if not r.empty:
        row = r.iloc[-1]
        print(f"  {row['ts_kst']} VIX={row['Close']:.2f}")

# 2. Compute 20-day iNAV calibration (278540.KS / KRW=X vs EWY) and exact gap on 11/4, 11/5, 11/6
print("\n=== iNAV FAIR VALUE CALIBRATION (278540.KS / KRW=X vs EWY) ===")
ewy_d = yf.Ticker("EWY").history(period="6mo", interval="1d")
msci_d = yf.Ticker("278540.KS").history(period="6mo", interval="1d")
krw_d = yf.Ticker("KRW=X").history(period="6mo", interval="1d")
koru_d = yf.Ticker("KORU").history(period="10y", interval="1d")
sox_d = yf.Ticker("^SOX").history(period="10y", interval="1d")
mu_d = yf.Ticker("MU").history(period="10y", interval="1d")
vix_d = yf.Ticker("^VIX").history(period="10y", interval="1d")
ks_d = yf.Ticker("^KS11").history(period="10y", interval="1d")

ewy_s = ewy_d["Close"].copy()
ewy_s.index = ewy_s.index.strftime("%Y-%m-%d")
msci_s = msci_d["Close"].copy()
msci_s.index = msci_s.index.strftime("%Y-%m-%d")
krw_s = krw_d["Close"].copy()
krw_s.index = krw_s.index.strftime("%Y-%m-%d")

# Also ensure 2026-11-05 278540.KS = 30005 and 11/5 15:30 KST KRW=X
krw_1105_1530 = float(krwx_5m[krwx_5m["dt_kst"] <= pd.Timestamp("2026-11-05 15:30:00+09:00")].iloc[-1]["Close"])
krw_1104_1530 = float(krwx_5m[krwx_5m["dt_kst"] <= pd.Timestamp("2026-11-04 15:30:00+09:00")].iloc[-1]["Close"])
krw_1106_0600 = float(krwx_5m[krwx_5m["dt_kst"] <= pd.Timestamp("2026-11-06 06:00:00+09:00")].iloc[-1]["Close"])
krw_1106_0905 = float(krwx_5m[krwx_5m["dt_kst"] <= pd.Timestamp("2026-11-06 09:05:00+09:00")].iloc[-1]["Close"])
krw_1106_0940 = float(krwx_5m[krwx_5m["dt_kst"] <= pd.Timestamp("2026-11-06 09:40:00+09:00")].iloc[-1]["Close"])

comb = pd.DataFrame({"ewy": ewy_s, "msci": msci_s, "krw": krw_s}).dropna()
comb["usd_idx"] = comb["msci"] / comb["krw"]
comb["ratio"] = comb["ewy"] / comb["usd_idx"]
med20_up_to_1104 = comb.loc[: "2026-11-04", "ratio"].tail(20).median()
med60_up_to_1104 = comb.loc[: "2026-11-04", "ratio"].tail(60).median()
print(f"20d median ratio (up to 11/4): {med20_up_to_1104:.4f}, 60d median: {med60_up_to_1104:.4f}")

fv_1104 = (31760.0 / krw_1104_1530) * med20_up_to_1104
fv_1105_1530 = (30005.0 / krw_1105_1530) * med20_up_to_1104
fv_1105_fx0600 = (30005.0 / krw_1106_0600) * med20_up_to_1104
fv_1106_cb_low = (26845.0 / krw_1106_0905) * med20_up_to_1104
fv_1106_0944 = (27750.0 / krw_1106_0940) * med20_up_to_1104

print(f"11/4 15:30 KST Fair Value EWY (31,760 / {krw_1104_1530:.2f}): ${fv_1104:.2f} | Actual 11/4 EWY Close=$152.12 ({(152.12/fv_1104-1)*100:+.2f}%) | 11/5 07:31 AH=$153.21 ({(153.21/fv_1104-1)*100:+.2f}%)")
print(f"11/5 15:30 KST Fair Value EWY (30,005 / {krw_1105_1530:.2f}): ${fv_1105_1530:.2f} (change vs 11/4 FV: {(fv_1105_1530/fv_1104-1)*100:+.2f}%)")
print(f"11/6 06:00 KST FX-adjusted 11/5 Fair Value EWY (30,005 / {krw_1106_0600:.2f}): ${fv_1105_fx0600:.2f} (change vs 11/4 EWY $152.12: {(fv_1105_fx0600/152.12-1)*100:+.2f}%)")
print(f"  -> US 11/5 Open EWY=$144.94 (gap vs 11/5 15:30 FV: {(144.935/fv_1105_1530-1)*100:+.2f}%)")
print(f"  -> US 11/5 Close EWY=$131.65 (discount vs FX-adj 11/5 FV ${fv_1105_fx0600:.2f}: {(131.65/fv_1105_fx0600-1)*100:+.2f}%)")
print(f"  -> Expiry EWY ~$132.20~$132.50 (discount vs FX-adj 11/5 FV: {(132.35/fv_1105_fx0600-1)*100:+.2f}%)")
print(f"11/6 09:03 CB Low Fair Value EWY (26,845 / {krw_1106_0905:.2f}): ${fv_1106_cb_low:.2f}")
print(f"11/6 09:44 KST Fair Value EWY (27,750 / {krw_1106_0940:.2f}): ${fv_1106_0944:.2f} (vs live EWY AH $135.23: {(135.23/fv_1106_0944-1)*100:+.2f}%)")

# 3. Historical Backtests for Section 4 Lessons (10-year daily, N~2512)
print("\n=== 10-YEAR BACKTESTS FOR LESSONS ===")
df_bt = pd.DataFrame({
    "koru_o": koru_d["Open"].tz_localize(None).resample("D").last(),
    "koru_h": koru_d["High"].tz_localize(None).resample("D").last(),
    "koru_l": koru_d["Low"].tz_localize(None).resample("D").last(),
    "koru_c": koru_d["Close"].tz_localize(None).resample("D").last(),
    "ewy_o": yf.Ticker("EWY").history(period="10y", interval="1d")["Open"].tz_localize(None).resample("D").last(),
    "ewy_c": yf.Ticker("EWY").history(period="10y", interval="1d")["Close"].tz_localize(None).resample("D").last(),
    "sox_c": sox_d["Close"].tz_localize(None).resample("D").last(),
    "mu_c": mu_d["Close"].tz_localize(None).resample("D").last(),
    "vix_c": vix_d["Close"].tz_localize(None).resample("D").last(),
}).dropna(subset=["koru_c", "ewy_c", "sox_c", "vix_c"])

df_bt["koru_ret"] = df_bt["koru_c"].pct_change() * 100
df_bt["koru_next"] = df_bt["koru_ret"].shift(-1)
df_bt["ewy_ret"] = df_bt["ewy_c"].pct_change() * 100
df_bt["ewy_intraday"] = (df_bt["ewy_c"] / df_bt["ewy_o"] - 1) * 100
df_bt["sox_ret"] = df_bt["sox_c"].pct_change() * 100
df_bt["sox_next"] = df_bt["sox_ret"].shift(-1)
df_bt["mu_ret"] = df_bt["mu_c"].pct_change() * 100
df_bt["vix_ret"] = df_bt["vix_c"].pct_change() * 100
df_bt["vix_next"] = df_bt["vix_ret"].shift(-1)
df_bt["clv"] = (df_bt["koru_c"] - df_bt["koru_l"]) / (df_bt["koru_h"] - df_bt["koru_l"]).replace(0, np.nan)
df_bt["ma20"] = df_bt["koru_c"].rolling(20).mean()
df_bt["dist_ma20"] = (df_bt["koru_c"] / df_bt["ma20"] - 1) * 100
tr = pd.concat([
    df_bt["koru_h"] - df_bt["koru_l"],
    (df_bt["koru_h"] - df_bt["koru_c"].shift(1)).abs(),
    (df_bt["koru_l"] - df_bt["koru_c"].shift(1)).abs()
], axis=1).max(axis=1)
df_bt["atr14_pct"] = tr.rolling(14).mean() / df_bt["koru_c"] * 100

print(f"Total 10y US trading days: {len(df_bt)}")
# Rank of 2026-11-05 KORU drop (-37.39%) and SOX drop (-12.25%) in 10 years!
worst_koru = df_bt.sort_values("koru_ret").head(10)[["koru_ret", "ewy_ret", "sox_ret", "vix_ret"]]
print("\nTop 10 worst KORU single-day drops in last 10 years:")
print(worst_koru.to_string())

# Lesson A: Low-CLV oversold bounce (koru_ret <= -4% & clv <= 0.20) split by volatility / SOX regime!
bt_valid = df_bt.dropna(subset=["koru_next"]).copy()
cond_low_clv = (bt_valid["koru_ret"] <= -4.0) & (bt_valid["clv"] <= 0.20)
print(f"\n[Backtest A] KORU <= -4% & CLV <= 0.20 (Total N={cond_low_clv.sum()}):")
s_all = bt_valid.loc[cond_low_clv, "koru_next"]
print(f"  All: N={len(s_all)}, Up={(s_all>0).mean()*100:.1f}%, Mean={s_all.mean():+.2f}%, Med={s_all.median():+.2f}%, P10={np.percentile(s_all,10):+.2f}%, Min={s_all.min():+.2f}%")

# Split by high ATR regime (atr14_pct >= 14%) vs normal ATR (< 14%)
s_hi_atr = bt_valid.loc[cond_low_clv & (bt_valid["atr14_pct"] >= 14.0), "koru_next"]
s_lo_atr = bt_valid.loc[cond_low_clv & (bt_valid["atr14_pct"] < 14.0), "koru_next"]
print(f"  ATR14/Close >= 14% (High-Vol Crash Regime): N={len(s_hi_atr)}, Up={(s_hi_atr>0).mean()*100:.1f}%, Mean={s_hi_atr.mean():+.2f}%, Med={s_hi_atr.median():+.2f}%, <=-10% ratio={(s_hi_atr<=-10).mean()*100:.1f}%, <=-15% ratio={(s_hi_atr<=-15).mean()*100:.1f}%")
print(f"  ATR14/Close <  14% (Normal Vol Regime):     N={len(s_lo_atr)}, Up={(s_lo_atr>0).mean()*100:.1f}%, Mean={s_lo_atr.mean():+.2f}%, Med={s_lo_atr.median():+.2f}%, <=-10% ratio={(s_lo_atr<=-10).mean()*100:.1f}%")

# Split by whether KORU opens down below prior day low (koru_o_{t+1} < koru_l_t) — i.e., Korea failed to hold & US gaps down!
bt_valid["next_open_vs_low"] = (bt_valid["koru_o"].shift(-1) / bt_valid["koru_l"] - 1) * 100
bt_valid["next_open_to_close"] = (bt_valid["koru_c"].shift(-1) / bt_valid["koru_o"].shift(-1) - 1) * 100
cond_gap_below_low = cond_low_clv & (bt_valid["next_open_vs_low"] < -1.0)
cond_hold_low = cond_low_clv & (bt_valid["next_open_vs_low"] >= -1.0)
s_gap_dn = bt_valid.loc[cond_gap_below_low, "koru_next"]
s_gap_dn_oc = bt_valid.loc[cond_gap_below_low, "next_open_to_close"]
s_hold = bt_valid.loc[cond_hold_low, "koru_next"]
print(f"  When next US Open gaps >1% BELOW prior day Low (Rule E support broken before open, like 11/5 $8.915 vs $10.23): N={len(s_gap_dn)}, CC Up={(s_gap_dn>0).mean()*100:.1f}%, CC Mean={s_gap_dn.mean():+.2f}%, CC Med={s_gap_dn.median():+.2f}%; Open->Close Up={(s_gap_dn_oc>0).mean()*100:.1f}%, OC Mean={s_gap_dn_oc.mean():+.2f}%, OC Med={s_gap_dn_oc.median():+.2f}%")
print(f"  When next US Open holds >= -1% of prior day Low: N={len(s_hold)}, CC Up={(s_hold>0).mean()*100:.1f}%, CC Mean={s_hold.mean():+.2f}%, CC Med={s_hold.median():+.2f}%")

# Lesson B: VIX crush (-12% or more) while SOX drops (<-1.5% or <0%) -> next day VIX & KORU!
cond_vix_crush = bt_valid["vix_ret"] <= -12.0
cond_vix_div = (bt_valid["vix_ret"] <= -10.0) & (bt_valid["sox_ret"] < 0.0)
print(f"\n[Backtest B] VIX <= -12% single-day crush (N={cond_vix_crush.sum()}):")
print(f"  Next day VIX up ratio={(bt_valid.loc[cond_vix_crush, 'vix_next']>0).mean()*100:.1f}%, KORU next up={(bt_valid.loc[cond_vix_crush, 'koru_next']>0).mean()*100:.1f}%, Med={bt_valid.loc[cond_vix_crush, 'koru_next'].median():+.2f}%")
print(f"  VIX <= -10% WHILE SOX < 0% (Divergence like 11/4 VIX -20.3% & SOX -3.1%): N={cond_vix_div.sum()}, Next day VIX up={(bt_valid.loc[cond_vix_div, 'vix_next']>0).mean()*100:.1f}% (Mean VIX chg {bt_valid.loc[cond_vix_div, 'vix_next'].mean():+.2f}%), Next day SOX up={(bt_valid.loc[cond_vix_div, 'sox_next']>0).mean()*100:.1f}%, KORU next up={(bt_valid.loc[cond_vix_div, 'koru_next']>0).mean()*100:.1f}% (Mean={bt_valid.loc[cond_vix_div, 'koru_next'].mean():+.2f}%, Med={bt_valid.loc[cond_vix_div, 'koru_next'].median():+.2f}%)")

# Lesson C: Intraday US session EWY (Open -> Close) regression / sensitivity on SOX (Open -> Close or daily) during major SOX selloffs (SOX <= -5%)
cond_sox_crash = df_bt["sox_ret"] <= -5.0
print(f"\n[Backtest C] Major US Semiconductor Selloff Days (SOX <= -5%, N={cond_sox_crash.sum()}):")
sub_sc = df_bt.loc[cond_sox_crash]
print(f"  KORU Up={(sub_sc['koru_ret']>0).mean()*100:.1f}%, Mean={sub_sc['koru_ret'].mean():+.2f}%, Med={sub_sc['koru_ret'].median():+.2f}%, EWY Open->Close Mean={sub_sc['ewy_intraday'].mean():+.2f}% (Med={sub_sc['ewy_intraday'].median():+.2f}%)")

# Also check what happens AFTER a -25% or worse single-day drop in KORU (for forward context!)
cond_extreme_drop = bt_valid["koru_ret"] <= -20.0
print(f"\n[Backtest D] Extreme KORU single-day drops <= -20% (N={cond_extreme_drop.sum()}):")
print(df_bt.loc[df_bt["koru_ret"] <= -20.0, ["koru_ret", "ewy_ret", "sox_ret", "vix_c", "koru_next"]].to_string())
