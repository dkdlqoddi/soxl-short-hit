#!/usr/bin/env python3
import json
import os
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"

# 1. Fetch 10y data for KORU, EWY, 278540.KS (listed 2017-11), ^KS11, KRW=X, ^SOX, MU, ^VIX
koru = yf.Ticker("KORU").history(period="10y", interval="1d")
ewy = yf.Ticker("EWY").history(period="10y", interval="1d")
ks11 = yf.Ticker("^KS11").history(period="10y", interval="1d")
msci = yf.Ticker("278540.KS").history(period="10y", interval="1d")
krw = yf.Ticker("KRW=X").history(period="10y", interval="1d")
sox = yf.Ticker("^SOX").history(period="10y", interval="1d")
mu = yf.Ticker("MU").history(period="10y", interval="1d")
vix = yf.Ticker("^VIX").history(period="10y", interval="1d")

def to_date_df(df, prefix):
    out = df[["Open", "High", "Low", "Close"]].copy()
    out.index = out.index.strftime("%Y-%m-%d")
    out = out[~out.index.duplicated(keep="last")]
    out.columns = [f"{prefix}_{c.lower()}" for c in out.columns]
    return out

us = pd.concat([
    to_date_df(koru, "koru"),
    to_date_df(ewy, "ewy"),
    to_date_df(sox, "sox"),
    to_date_df(mu, "mu"),
    to_date_df(vix, "vix"),
], axis=1).dropna(subset=["koru_close", "ewy_close", "sox_close"])

kr = pd.concat([
    to_date_df(ks11, "ks"),
    to_date_df(msci, "msci"),
    to_date_df(krw, "krw"),
], axis=1)

# Align: For US date D, Korea date D is ALREADY closed before US date D opens; Korea date D+1 (next trading day) reacts to US date D!
all_dates = sorted(set(us.index) | set(kr.index))
cal = pd.DataFrame(index=all_dates)
cal = cal.join(us).join(kr)
cal["ks_ret"] = cal["ks_close"].pct_change() * 100
cal["msci_ret"] = cal["msci_close"].pct_change() * 100

# Build US trading day table with same-day KR close (latest KR close <= D) and next-day KR close (first KR close > D, <= next US D)
us_days = us.index.tolist()
rows = []
for i in range(len(us_days) - 1):
    d = us_days[i]
    d_next = us_days[i + 1]
    # KR on or before d
    kr_upto_d = cal.loc[:d].dropna(subset=["ks_close"])
    kr_between = cal.loc[d:d_next].iloc[1:].dropna(subset=["ks_close"]) # strictly after d, up to d_next
    ks_next_ret = kr_between["ks_ret"].iloc[0] if len(kr_between) > 0 else np.nan
    ks_next_open_ret = ((kr_between["ks_open"].iloc[0] / kr_upto_d["ks_close"].iloc[-1] - 1) * 100) if len(kr_between) > 0 and len(kr_upto_d) > 0 else np.nan
    ks_same_ret = kr_upto_d["ks_ret"].iloc[-1] if len(kr_upto_d) > 0 else np.nan
    # Fair value proxy using KS11 / KRW when 278540 not available, and 278540 / KRW when available
    msci_same = kr_upto_d["msci_close"].iloc[-1] if len(kr_upto_d) > 0 else np.nan
    krw_same = cal.loc[:d, "krw_close"].dropna().iloc[-1] if len(cal.loc[:d, "krw_close"].dropna()) > 0 else np.nan
    rows.append({
        "date": d,
        "next_us_date": d_next,
        "koru_c": us.loc[d, "koru_close"],
        "koru_l": us.loc[d, "koru_low"],
        "koru_h": us.loc[d, "koru_high"],
        "koru_next_o": us.loc[d_next, "koru_open"],
        "koru_next_c": us.loc[d_next, "koru_close"],
        "ewy_c": us.loc[d, "ewy_close"],
        "ewy_next_o": us.loc[d_next, "ewy_open"],
        "ewy_next_c": us.loc[d_next, "ewy_close"],
        "sox_c": us.loc[d, "sox_close"],
        "sox_next_o": us.loc[d_next, "sox_open"],
        "sox_next_c": us.loc[d_next, "sox_close"],
        "mu_c": us.loc[d, "mu_close"],
        "vix_c": us.loc[d, "vix_close"],
        "vix_next_c": us.loc[d_next, "vix_close"],
        "ks_same_ret": ks_same_ret,
        "ks_next_open_ret": ks_next_open_ret,
        "ks_next_ret": ks_next_ret,
        "msci_same": msci_same,
        "krw_same": krw_same,
    })

tdf = pd.DataFrame(rows).set_index("date")
tdf["koru_ret"] = us["koru_close"].pct_change().reindex(tdf.index) * 100
tdf["koru_next_ret"] = (tdf["koru_next_c"] / tdf["koru_c"] - 1) * 100
tdf["koru_next_oc"] = (tdf["koru_next_c"] / tdf["koru_next_o"] - 1) * 100
tdf["ewy_ret"] = us["ewy_close"].pct_change().reindex(tdf.index) * 100
tdf["ewy_next_ret"] = (tdf["ewy_next_c"] / tdf["ewy_c"] - 1) * 100
tdf["ewy_next_oc"] = (tdf["ewy_next_c"] / tdf["ewy_next_o"] - 1) * 100
tdf["sox_ret"] = us["sox_close"].pct_change().reindex(tdf.index) * 100
tdf["sox_next_ret"] = (tdf["sox_next_c"] / tdf["sox_c"] - 1) * 100
tdf["sox_next_oc"] = (tdf["sox_next_c"] / tdf["sox_next_o"] - 1) * 100
tdf["mu_ret"] = us["mu_close"].pct_change().reindex(tdf.index) * 100
tdf["vix_ret"] = us["vix_close"].pct_change().reindex(tdf.index) * 100
tdf["clv"] = (tdf["koru_c"] - tdf["koru_l"]) / (tdf["koru_h"] - tdf["koru_l"]).replace(0, np.nan)
tdf["usd_msci"] = tdf["msci_same"] / tdf["krw_same"]
tdf["inav_ratio"] = tdf["ewy_c"] / tdf["usd_msci"]
tdf["inav_gap_pct"] = (tdf["inav_ratio"] / tdf["inav_ratio"].rolling(20).median() - 1) * 100

print("=== TEST 1: Oversold Low-Close (KORU <= -4% & CLV <= 0.20) split by Next-Day KOSPI Return ===")
c_base = (tdf["koru_ret"] <= -4.0) & (tdf["clv"] <= 0.20) & tdf["ks_next_ret"].notna()
for label, mask in [
    ("All with KR session", c_base),
    ("KOSPI D+1 >= -1.0% (held)", c_base & (tdf["ks_next_ret"] >= -1.0)),
    ("KOSPI D+1 < -1.0% to -2.0%", c_base & (tdf["ks_next_ret"] < -1.0) & (tdf["ks_next_ret"] >= -2.0)),
    ("KOSPI D+1 < -2.0% (broke down, 11/5 was -5.28%)", c_base & (tdf["ks_next_ret"] < -2.0)),
    ("KOSPI D+1 <= -3.0% (crash)", c_base & (tdf["ks_next_ret"] <= -3.0)),
]:
    sub = tdf.loc[mask, "koru_next_ret"]
    print(f"  {label:48s}: N={len(sub):3d}, Up={(sub>0).mean()*100:5.1f}%, Mean={sub.mean():+6.2f}%, Med={sub.median():+6.2f}%, P25={np.percentile(sub,25):+6.2f}%, P10={np.percentile(sub,10):+6.2f}%")

print("\n=== TEST 2: Two-Day Consecutive SOX Drop (SOX_D <= -2.5% AND SOX_{D+1} <= -2.5%) ===")
c_sox1 = tdf["sox_ret"] <= -2.5
c_sox2 = c_sox1 & (tdf["sox_next_ret"] <= -2.5)
c_sox2_deep = c_sox1 & (tdf["sox_next_ret"] <= -5.0)
for label, mask in [
    ("After SOX_D <= -2.5% (unconditional)", c_sox1),
    ("  -> if SOX_{D+1} > 0% (rebound)", c_sox1 & (tdf["sox_next_ret"] > 0)),
    ("  -> if SOX_{D+1} <= -2.5% (2-day consecutive selloff)", c_sox2),
    ("  -> if SOX_{D+1} <= -5.0% (2nd-day panic)", c_sox2_deep),
]:
    sub = tdf.loc[mask, "koru_next_ret"]
    print(f"  {label:55s}: N={len(sub):3d}, Up={(sub>0).mean()*100:5.1f}%, Mean={sub.mean():+6.2f}%, Med={sub.median():+6.2f}%, Min={sub.min():+6.2f}%")

print("\n=== TEST 3: EWY Intraday Beta to SOX (Open->Close) on US Regular Session ===")
valid_oc = tdf.dropna(subset=["ewy_next_oc", "sox_next_oc", "koru_next_oc"])
slope, intercept = np.polyfit(valid_oc["sox_next_oc"], valid_oc["ewy_next_oc"], 1)
r2 = valid_oc["sox_next_oc"].corr(valid_oc["ewy_next_oc"]) ** 2
print(f"  10y all days (N={len(valid_oc)}): EWY_OC = {intercept:+.3f} + {slope:.3f} * SOX_OC (R2={r2:.3f})")
crash_oc = valid_oc[valid_oc["sox_next_oc"] <= -3.0]
slope_c, intercept_c = np.polyfit(crash_oc["sox_next_oc"], crash_oc["ewy_next_oc"], 1)
r2_c = crash_oc["sox_next_oc"].corr(crash_oc["ewy_next_oc"]) ** 2
print(f"  When SOX_OC <= -3% (N={len(crash_oc)}): EWY_OC = {intercept_c:+.3f} + {slope_c:.3f} * SOX_OC (R2={r2_c:.3f}), KORU_OC Mean={crash_oc['koru_next_oc'].mean():+.2f}%, Med={crash_oc['koru_next_oc'].median():+.2f}%")
rec_2026 = valid_oc.loc["2026-01-01":]
slope_26, intercept_26 = np.polyfit(rec_2026["sox_next_oc"], rec_2026["ewy_next_oc"], 1)
r2_26 = rec_2026["sox_next_oc"].corr(rec_2026["ewy_next_oc"]) ** 2
print(f"  2026 YTD (N={len(rec_2026)}): EWY_OC = {intercept_26:+.3f} + {slope_26:.3f} * SOX_OC (R2={r2_26:.3f})")
print(f"  Actual 2026-11-05 SOX Open->Close: {(9011.14/9806.31 - 1)*100:+.2f}%, EWY Open->Close: {(131.65/144.935 - 1)*100:+.2f}%, KORU Open->Close: {(6.53/8.915 - 1)*100:+.2f}%")

print("\n=== TEST 4: First-Hour US Open Breakdown Filter (Claude's 1st-hour SOX rule & Stop-loss verification) ===")
# Check 11/5 US session 1st hour for KORU, EWY, SOXX, SPY, QQQ
koru_1m = pd.read_csv(os.path.join(OUT_DIR, "koru_1m_window.csv"))
soxx_1m = pd.read_csv(os.path.join(OUT_DIR, "soxx_1m_window.csv"))
koru_1m["dt_kst"] = pd.to_datetime(koru_1m["ts_kst"])
soxx_1m["dt_kst"] = pd.to_datetime(soxx_1m["ts_kst"])
s1h = soxx_1m[(soxx_1m["dt_kst"] >= "2026-11-05 23:30:00+09:00") & (soxx_1m["dt_kst"] <= "2026-11-06 00:30:00+09:00")]
k1h = koru_1m[(koru_1m["dt_kst"] >= "2026-11-05 23:30:00+09:00") & (koru_1m["dt_kst"] <= "2026-11-06 00:30:00+09:00")]
print(f"  SOXX 1st hour (23:30~00:30 KST): Open={s1h.iloc[0]['Open']:.2f}, High={s1h['High'].max():.2f} at {s1h.loc[s1h['High'].idxmax(),'ts_kst'][11:16]}, Low={s1h['Low'].min():.2f}, 00:30 Close={s1h.iloc[-1]['Close']:.2f}")
print(f"  KORU 1st hour (23:30~00:30 KST): Open={k1h.iloc[0]['Open']:.2f}, High={k1h['High'].max():.2f} at {k1h.loc[k1h['High'].idxmax(),'ts_kst'][11:16]}, Low={k1h['Low'].min():.2f}, 00:30 Close={k1h.iloc[-1]['Close']:.2f}")

# 5. Also check Nasdaq Historical API for KORU 11/4 and 11/5 official OHLCV
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
try:
    req = urllib.request.Request("https://api.nasdaq.com/api/quote/KORU/historical?assetclass=etf&fromdate=2026-10-28&todate=2026-11-06&limit=20", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        nd = json.loads(resp.read().decode("utf-8"))
    print("\n=== Nasdaq Official Historical OHLCV for KORU ===")
    for r in nd.get("data", {}).get("tradesTable", {}).get("rows", [])[:5]:
        print(" ", r)
except Exception as e:
    print("Nasdaq API err:", e)
