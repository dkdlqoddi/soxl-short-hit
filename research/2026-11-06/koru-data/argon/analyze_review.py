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

koru_1m = pd.read_csv(os.path.join(OUT_DIR, "koru_1m_window.csv"))
ewy_1m = pd.read_csv(os.path.join(OUT_DIR, "ewy_1m_window.csv"))
soxx_1m = pd.read_csv(os.path.join(OUT_DIR, "soxx_1m_window.csv"))
soxl_1m = pd.read_csv(os.path.join(OUT_DIR, "soxl_1m_window.csv"))
mu_1m = pd.read_csv(os.path.join(OUT_DIR, "mu_1m_window.csv"))
nvda_1m = pd.read_csv(os.path.join(OUT_DIR, "nvda_1m_window.csv"))
spy_1m = pd.read_csv(os.path.join(OUT_DIR, "spy_1m_window.csv"))
qqq_1m = pd.read_csv(os.path.join(OUT_DIR, "qqq_1m_window.csv"))
skhy_1m = pd.read_csv(os.path.join(OUT_DIR, "skhy_1m_window.csv"))

for df in [koru_1m, ewy_1m, soxx_1m, soxl_1m, mu_1m, nvda_1m, spy_1m, qqq_1m, skhy_1m]:
    df["dt_kst"] = pd.to_datetime(df["ts_kst"])
    df["dt_est"] = pd.to_datetime(df["ts_est"])

print("=== 1. BASE TIME VERIFICATION (2026-11-05 07:25 ~ 09:15 KST) ===")
sub_base = koru_1m[(koru_1m["dt_kst"] >= "2026-11-05 07:28:00+09:00") & (koru_1m["dt_kst"] <= "2026-11-05 07:45:00+09:00")]
print(sub_base[["ts_kst", "ts_est", "Open", "High", "Low", "Close", "Volume"]].to_string(index=False))

print("\n=== 1b. KORU 2026-11-05 08:00 ~ 10:00 KST (NXT & KR Open reaction) ===")
sub_kr_open = koru_1m[(koru_1m["dt_kst"] >= "2026-11-05 08:00:00+09:00") & (koru_1m["dt_kst"] <= "2026-11-05 10:00:00+09:00")]
for target_t in ["08:04", "08:43", "08:55", "09:00", "09:02", "09:10", "09:30", "09:58", "09:59"]:
    r = sub_kr_open[sub_kr_open["ts_kst"].str.contains(f"2026-11-05 {target_t}:")]
    if not r.empty:
        row = r.iloc[-1]
        print(f"{row['ts_kst']} | O={row['Open']:.4f} H={row['High']:.4f} L={row['Low']:.4f} C={row['Close']:.4f} V={row['Volume']}")
print(f"08:00~10:00 High={sub_kr_open['High'].max():.4f} at {sub_kr_open.loc[sub_kr_open['High'].idxmax(), 'ts_kst']}, Low={sub_kr_open['Low'].min():.4f} at {sub_kr_open.loc[sub_kr_open['Low'].idxmin(), 'ts_kst']}")

print("\n=== 2. EXPIRY TIME VERIFICATION (2026-11-06 07:20 ~ 07:50 KST) ===")
sub_exp = koru_1m[(koru_1m["dt_kst"] >= "2026-11-06 07:20:00+09:00") & (koru_1m["dt_kst"] <= "2026-11-06 07:50:00+09:00")]
print(sub_exp[["ts_kst", "ts_est", "Open", "High", "Low", "Close", "Volume"]].to_string(index=False))

print("\n=== 2b. EWY around EXPIRY (2026-11-06 07:20 ~ 07:50 KST) ===")
sub_ewy_exp = ewy_1m[(ewy_1m["dt_kst"] >= "2026-11-06 07:20:00+09:00") & (ewy_1m["dt_kst"] <= "2026-11-06 07:50:00+09:00")]
print(sub_ewy_exp[["ts_kst", "ts_est", "Open", "High", "Low", "Close", "Volume"]].to_string(index=False))

print("\n=== 3. POST-EXPIRY TO NOW (2026-11-06 07:50 ~ 09:45 KST) ===")
sub_post = koru_1m[koru_1m["dt_kst"] >= "2026-11-06 07:50:00+09:00"]
if not sub_post.empty:
    print(f"Rows: {len(sub_post)}, First: {sub_post.iloc[0]['ts_kst']} C={sub_post.iloc[0]['Close']:.4f}, Last: {sub_post.iloc[-1]['ts_kst']} C={sub_post.iloc[-1]['Close']:.4f}")
    print(f"High: {sub_post['High'].max():.4f} at {sub_post.loc[sub_post['High'].idxmax(), 'ts_kst']}")
    print(f"Low:  {sub_post['Low'].min():.4f} at {sub_post.loc[sub_post['Low'].idxmin(), 'ts_kst']}")
    for t_str in ["08:00", "08:30", "08:50", "09:00", "09:03", "09:05", "09:23", "09:30", "09:40", "09:44"]:
        r = sub_post[sub_post["ts_kst"].str.contains(f"2026-11-06 {t_str}:")]
        if not r.empty:
            row = r.iloc[-1]
            print(f"  {row['ts_kst']} | O={row['Open']:.4f} H={row['High']:.4f} L={row['Low']:.4f} C={row['Close']:.4f} V={row['Volume']}")

print("\n=== 4. PHASE BREAKDOWN (2026-11-05 07:31 KST -> 2026-11-06 09:44 KST) ===")
phases = [
    ("P1_AH_NXT_KROpen", "2026-11-05 07:31:00+09:00", "2026-11-05 09:59:59+09:00"),
    ("P3_US_Early_Pre", "2026-11-05 18:00:00+09:00", "2026-11-05 21:29:59+09:00"),
    ("P4_US_Late_Pre_Macro", "2026-11-05 21:30:00+09:00", "2026-11-05 23:29:59+09:00"),
    ("P5_US_Reg_FirstHour", "2026-11-05 23:30:00+09:00", "2026-11-06 00:59:59+09:00"),
    ("P6_US_Reg_Mid_Close", "2026-11-06 01:00:00+09:00", "2026-11-06 05:59:59+09:00"),
    ("P7_US_AH_To_Expiry", "2026-11-06 06:00:00+09:00", "2026-11-06 07:40:59+09:00"),
    ("P8_Post_Expiry_KR_CB", "2026-11-06 07:41:00+09:00", "2026-11-06 09:45:00+09:00"),
]
for name, s, e in phases:
    k_sub = koru_1m[(koru_1m["dt_kst"] >= s) & (koru_1m["dt_kst"] <= e)]
    e_sub = ewy_1m[(ewy_1m["dt_kst"] >= s) & (ewy_1m["dt_kst"] <= e)]
    sx_sub = soxl_1m[(soxl_1m["dt_kst"] >= s) & (soxl_1m["dt_kst"] <= e)]
    if not k_sub.empty:
        hi_idx = k_sub["High"].idxmax()
        lo_idx = k_sub["Low"].idxmin()
        e_o = e_sub.iloc[0]["Open"] if not e_sub.empty else np.nan
        e_c = e_sub.iloc[-1]["Close"] if not e_sub.empty else np.nan
        sx_c = sx_sub.iloc[-1]["Close"] if not sx_sub.empty else np.nan
        print(f"{name}: KORU O={k_sub.iloc[0]['Open']:.4f} -> C={k_sub.iloc[-1]['Close']:.4f} | H={k_sub.loc[hi_idx,'High']:.4f} ({k_sub.loc[hi_idx,'ts_kst'][11:16]}) | L={k_sub.loc[lo_idx,'Low']:.4f} ({k_sub.loc[lo_idx,'ts_kst'][11:16]}) | Vol={int(k_sub['Volume'].sum())} | EWY {e_o:.2f}->{e_c:.2f} | SOXL end={sx_c:.2f}")

print("\n=== 5. KEY LEVEL CROSSING TIMES FOR KORU ===")
levels = [10.85, 10.60, 10.43, 10.23, 10.225, 10.07, 10.03, 9.95, 9.60, 9.20, 9.10, 8.80, 8.00, 7.50, 7.00]
koru_after_base = koru_1m[koru_1m["dt_kst"] >= "2026-11-05 07:31:00+09:00"]
print(f"Max High from 11/5 07:31 to 11/6 07:40: {koru_after_base[koru_after_base['dt_kst']<='2026-11-06 07:40:59+09:00']['High'].max():.4f} at {koru_after_base.loc[koru_after_base[koru_after_base['dt_kst']<='2026-11-06 07:40:59+09:00']['High'].idxmax(), 'ts_kst']}")
print(f"Min Low  from 11/5 07:31 to 11/6 07:40: {koru_after_base[koru_after_base['dt_kst']<='2026-11-06 07:40:59+09:00']['Low'].min():.4f} at {koru_after_base.loc[koru_after_base[koru_after_base['dt_kst']<='2026-11-06 07:40:59+09:00']['Low'].idxmin(), 'ts_kst']}")
for lv in [10.43, 10.23, 10.225, 10.07, 10.03, 9.95, 9.60, 9.20, 9.10, 8.80, 8.00, 7.50, 7.00]:
    breach = koru_after_base[koru_after_base["Low"] < lv]
    if not breach.empty:
        first_b = breach.iloc[0]
        print(f"  First Low < ${lv:.3f}: {first_b['ts_kst']} (Low={first_b['Low']:.4f}, Close={first_b['Close']:.4f})")

print("\n=== 6. DAILY CLOSES & RETURNS (11/4 vs 11/5 US, 11/4 vs 11/5 vs 11/6 KR) ===")
with open(os.path.join(OUT_DIR, "daily_recent.json")) as f:
    daily = json.load(f)["data"]

for sym, rows in daily.items():
    if len(rows) >= 2:
        last2 = rows[-2:]
        r_prev, r_curr = last2[0], last2[1]
        pct = (r_curr["close"] / r_prev["close"] - 1) * 100
        print(f"{sym:10s} | {r_prev['date']} C={r_prev['close']:10.4f} -> {r_curr['date']} O={r_curr['open']:10.4f} H={r_curr['high']:10.4f} L={r_curr['low']:10.4f} C={r_curr['close']:10.4f} ({pct:+6.2f}%) Vol={r_curr['volume']}")

# Also check ^SOX directly via yfinance
try:
    sox_d = yf.Ticker("^SOX").history(period="5d", interval="1d")
    print("\n=== ^SOX Daily ===")
    for idx, row in sox_d.iterrows():
        print(idx.strftime("%Y-%m-%d"), f"O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f}")
except Exception as e:
    print("^SOX err:", e)

print("\n=== 7. NAVER REALTIME & 11/5 SUMMARY ===")
with open(os.path.join(OUT_DIR, "naver_realtime.json")) as f:
    nav = json.load(f)
for k in ["KOSPI", "KOSDAQ", "005930_basic", "000660_basic", "278540_basic"]:
    if k in nav:
        d = nav[k]
        print(f"[{k}] closePrice={d.get('closePrice')} compareToPreviousClosePrice={d.get('compareToPreviousClosePrice')} fluctuationsRatio={d.get('fluctuationsRatio')} marketStatus={d.get('marketStatus')} localTradedAt={d.get('localTradedAt')}")
        if "overMarketPriceInfo" in d and d["overMarketPriceInfo"]:
            print(f"   overMarketPriceInfo: {d['overMarketPriceInfo']}")

for k in ["KOSPI_price", "005930_price", "000660_price", "278540_price"]:
    if k in nav and isinstance(nav[k], list):
        print(f"[{k}] top 3 rows:")
        for row in nav[k][:3]:
            print("  ", row)
for k in ["KOSPI_trend", "005930_trend", "000660_trend"]:
    if k in nav:
        print(f"[{k}]:", str(nav[k])[:400])
