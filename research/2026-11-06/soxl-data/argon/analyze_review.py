#!/usr/bin/env python3
"""Deep quantitative analysis of SOXL 2026-11-05 24h forecast round, phase breakdown,
invalidation triggers, and post-mortem backtests."""

import json
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
KST = ZoneInfo("Asia/Seoul")
EST = ZoneInfo("America/New_York")

# 1. Check Nasdaq official daily JSON
nasdaq_path = os.path.join(DATA_DIR, "nasdaq_soxl_daily.json")
if os.path.exists(nasdaq_path):
    with open(nasdaq_path) as f:
        nj = json.load(f)
    rows = nj.get("data", {}).get("tradesTable", {}).get("rows", [])
    print("=== NASDAQ OFFICIAL DAILY (Top 6) ===")
    for r in rows[:6]:
        print(r)

# 2. Check Naver Korean realtime JSON
naver_path = os.path.join(DATA_DIR, "naver_kr_realtime.json")
if os.path.exists(naver_path):
    with open(naver_path) as f:
        nv = json.load(f)
    print("\n=== NAVER KR REALTIME ===")
    for k, v in nv.get("data", {}).items():
        print(k, {
            "closePrice": v.get("closePrice"),
            "compareToPreviousClosePrice": v.get("compareToPreviousClosePrice"),
            "fluctuationsRatio": v.get("fluctuationsRatio"),
            "localTradedAt": v.get("localTradedAt"),
            "marketStatus": v.get("marketStatus"),
            "overMarketPriceInfo": v.get("overMarketPriceInfo"),
        })

# 3. Load 1m CSVs
soxl = pd.read_csv(os.path.join(DATA_DIR, "soxl_1m_5d.csv"), index_col=0, parse_dates=True)
soxx = pd.read_csv(os.path.join(DATA_DIR, "soxx_1m_5d.csv"), index_col=0, parse_dates=True)
nvda = pd.read_csv(os.path.join(DATA_DIR, "nvda_1m_5d.csv"), index_col=0, parse_dates=True)
amd = pd.read_csv(os.path.join(DATA_DIR, "amd_1m_5d.csv"), index_col=0, parse_dates=True)
mu = pd.read_csv(os.path.join(DATA_DIR, "mu_1m_5d.csv"), index_col=0, parse_dates=True)
avgo = pd.read_csv(os.path.join(DATA_DIR, "avgo_1m_5d.csv"), index_col=0, parse_dates=True)
qcom = pd.read_csv(os.path.join(DATA_DIR, "qcom_1m_5d.csv"), index_col=0, parse_dates=True)
arm = pd.read_csv(os.path.join(DATA_DIR, "arm_1m_5d.csv"), index_col=0, parse_dates=True)
qqq = pd.read_csv(os.path.join(DATA_DIR, "qqq_1m_5d.csv"), index_col=0, parse_dates=True)
spy = pd.read_csv(os.path.join(DATA_DIR, "spy_1m_5d.csv"), index_col=0, parse_dates=True)
nq = pd.read_csv(os.path.join(DATA_DIR, "nq_1m_5d.csv"), index_col=0, parse_dates=True)
vix = pd.read_csv(os.path.join(DATA_DIR, "vix_1m_5d.csv"), index_col=0, parse_dates=True)
soxl_15m = pd.read_csv(os.path.join(DATA_DIR, "soxl_15m_5d.csv"), index_col=0, parse_dates=True)

print("\n=== DAILY SUMMARY ALL PEERS (11/3, 11/4, 11/5) ===")
with open(os.path.join(DATA_DIR, "daily_summary.json")) as f:
    ds = json.load(f)["daily"]
for sym, rows in ds.items():
    last3 = [r for r in rows if r["date"] >= "2026-11-03"]
    s_str = " | ".join([f"{r['date']}: O={r['open']} H={r['high']} L={r['low']} C={r['close']}" for r in last3])
    print(f"{sym:10s} -> {s_str}")

# 4. Detailed Phase Breakdown from 2026-11-04 23:30 KST to 2026-11-06 09:45 KST
phases = [
    ("P1_open_first_1h", "2026-11-04 23:30:00", "2026-11-05 00:30:59"),
    ("P2_wed_midday_breakdown", "2026-11-05 00:31:00", "2026-11-05 02:59:59"),
    ("P3_wed_afternoon_close", "2026-11-05 03:00:00", "2026-11-05 05:59:59"),
    ("P4_wed_afterhours_qcom_arm", "2026-11-05 06:00:00", "2026-11-05 09:59:59"),
    ("P5_thu_early_premarket_asia_spillover", "2026-11-05 18:00:00", "2026-11-05 22:29:59"),
    ("P6_thu_late_premarket_macro_830", "2026-11-05 22:30:00", "2026-11-05 23:29:59"),
    ("P7_expiry_open_and_codex_window", "2026-11-05 23:30:00", "2026-11-06 00:05:59"),
    ("P8_post_expiry_thu_crash", "2026-11-06 00:06:00", "2026-11-06 05:59:59"),
    ("P9_thu_afterhours_fri_kr", "2026-11-06 06:00:00", "2026-11-06 09:59:59"),
]

print("\n=== PHASE BREAKDOWN (SOXL 1m) ===")
phase_records = []
for name, start_k, end_k in phases:
    sub = soxl[(soxl["ts_kst"] >= start_k) & (soxl["ts_kst"] <= end_k)]
    if sub.empty:
        continue
    hi_idx = sub["High"].idxmax()
    lo_idx = sub["Low"].idxmin()
    rec = {
        "phase": name,
        "start_kst": sub.iloc[0]["ts_kst"],
        "end_kst": sub.iloc[-1]["ts_kst"],
        "open": round(float(sub.iloc[0]["Open"]), 4),
        "close": round(float(sub.iloc[-1]["Close"]), 4),
        "high": round(float(sub.loc[hi_idx, "High"]), 4),
        "high_kst": sub.loc[hi_idx, "ts_kst"],
        "low": round(float(sub.loc[lo_idx, "Low"]), 4),
        "low_kst": sub.loc[lo_idx, "ts_kst"],
        "vol": int(sub["Volume"].sum()),
    }
    phase_records.append(rec)
    print(rec)

# 5. Check exact timestamps when invalidation lines were crossed!
print("\n=== INVALIDATION LINE TIMESTAMPS ===")
w = soxl[(soxl["ts_kst"] >= "2026-11-04 23:30:00") & (soxl["ts_kst"] <= "2026-11-06 00:10:00")].copy()

# When did SOXL drop below $70.03 after 00:17 KST?
after_0017 = w[w["ts_kst"] >= "2026-11-05 00:17:00"]
below_7003 = after_0017[after_0017["Close"] < 70.03]
if not below_7003.empty:
    print("First 1m close < $70.03 after 00:17 KST:", below_7003.iloc[0]["ts_kst"], below_7003.iloc[0]["Close"])

# Did SOXL ever recover $70.03 after 00:30 KST?
after_0030 = w[w["ts_kst"] >= "2026-11-05 00:31:00"]
above_7003 = after_0030[after_0030["High"] >= 70.03]
print("Max High after 00:31 KST:", after_0030["High"].max(), "at", after_0030.loc[after_0030["High"].idxmax(), "ts_kst"])
if not above_7003.empty:
    print("Bars with High >= $70.03 after 00:31 KST:", len(above_7003), "last:", above_7003.iloc[-1]["ts_kst"], above_7003.iloc[-1]["High"])

# When did SOXL break $67.50 and $67.26 after 00:17 KST?
below_6726 = after_0017[after_0017["Low"] < 67.26]
if not below_6726.empty:
    print("First Low < $67.26 after 00:17 KST:", below_6726.iloc[0]["ts_kst"], "Low=", below_6726.iloc[0]["Low"], "Close=", below_6726.iloc[0]["Close"])
below_6726_c = after_0017[after_0017["Close"] < 67.26]
if not below_6726_c.empty:
    print("First 1m Close < $67.26 after 00:17 KST:", below_6726_c.iloc[0]["ts_kst"], "Close=", below_6726_c.iloc[0]["Close"])

# Check Codex's 15m rule: "SOXL이 $67.26 아래에서 15분봉 두 개를 연속 마감" & SOXX < $452.46!
w15 = soxl_15m[(soxl_15m["ts_kst"] >= "2026-11-04 23:30:00") & (soxl_15m["ts_kst"] <= "2026-11-05 06:00:00")].copy()
print("\n=== SOXL 15m BARS ON NOV 4 REGULAR SESSION ===")
for _, r in w15.iterrows():
    flag = " <-- <67.26" if r["Close"] < 67.26 else ""
    print(f"  {r['ts_kst']} ({r['ts_est']} EST) | O={r['Open']:.2f} H={r['High']:.2f} L={r['Low']:.2f} C={r['Close']:.2f}{flag}")

# Check SOXX 3-for-1 split adjustment in yfinance!
print("\n=== SOXX 1m AROUND NOV 4 AND NOV 5 ===")
for tk in ["2026-11-04 23:30:00", "2026-11-05 00:30:00", "2026-11-05 01:00:00", "2026-11-05 05:59:00", "2026-11-05 07:00:00", "2026-11-05 23:30:00", "2026-11-06 05:59:00"]:
    s_sub = soxx[soxx["ts_kst"] <= tk].tail(1)
    if not s_sub.empty:
        r = s_sub.iloc[0]
        print(f"  SOXX <= {tk}: {r['ts_kst']} C={r['Close']:.4f} (x3={r['Close']*3:.2f})")

# Check QCOM & ARM after-hours on Nov 4 (06:00~10:00 KST Nov 5)
for nm, df_p in [("QCOM", qcom), ("ARM", arm)]:
    ah = df_p[(df_p["ts_kst"] >= "2026-11-05 05:59:00") & (df_p["ts_kst"] <= "2026-11-05 09:59:59")]
    if not ah.empty:
        print(f"\n=== {nm} AFTER-HOURS (Nov 5 06:00~10:00 KST) ===")
        print("  Reg close (~05:59):", ah.iloc[0]["ts_kst"], ah.iloc[0]["Close"])
        print("  AH High:", ah["High"].max(), "at", ah.loc[ah["High"].idxmax(), "ts_kst"])
        print("  AH Low:", ah["Low"].min(), "at", ah.loc[ah["Low"].idxmin(), "ts_kst"])
        print("  AH End:", ah.iloc[-1]["ts_kst"], ah.iloc[-1]["Close"])

# Check Claude's "CLV < 0.2 close buy rule" on Nov 4 close!
# Nov 4 daily: Open=70.03, High=75.29, Low=62.23, Close=66.68
h4, l4, c4 = 75.29, 62.23, 66.68
clv4 = (c4 - l4) / (h4 - l4)
print(f"\nNov 4 Regular Session CLV = ({c4} - {l4}) / ({h4} - {l4}) = {clv4:.4f}")

with open(os.path.join(DATA_DIR, "phase_analysis.json"), "w", encoding="utf-8") as f:
    json.dump({"phases": phase_records, "nov4_clv": round(clv4, 4)}, f, ensure_ascii=False, indent=2)
