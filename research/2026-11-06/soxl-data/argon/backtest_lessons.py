#!/usr/bin/env python3
"""Run empirical backtests on SOXL (2010-2026 daily, 2y 1h, 60d 5m) to verify
exact sample sizes (N), win rates, means, and medians for the review lessons."""

import json
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
EST = ZoneInfo("America/New_York")

# 1. Long-term daily SOXL, SOXX, SPY, ^VIX (2010-03 to 2026-11-05)
soxl_d = yf.Ticker("SOXL").history(period="max", interval="1d", auto_adjust=False)
spy_d = yf.Ticker("SPY").history(period="max", interval="1d", auto_adjust=False)
vix_d = yf.Ticker("^VIX").history(period="max", interval="1d", auto_adjust=False)
soxx_d = yf.Ticker("SOXX").history(period="max", interval="1d", auto_adjust=True)
for d in (soxl_d, spy_d, vix_d, soxx_d):
    d.index = d.index.tz_convert(EST).strftime("%Y-%m-%d")
# Adjust SOXX pre-2026-11-05 bars if yfinance daily has not yet retroactively applied the 3-for-1 split on 2026-11-05
if "2026-11-04" in soxx_d.index and "2026-11-05" in soxx_d.index:
    if soxx_d.loc["2026-11-04", "Close"] > 300 and soxx_d.loc["2026-11-05", "Close"] < 200:
        soxx_d.loc[soxx_d.index < "2026-11-05", ["Open", "High", "Low", "Close"]] /= 3.0

df = pd.DataFrame({
    "O": soxl_d["Open"],
    "H": soxl_d["High"],
    "L": soxl_d["Low"],
    "C": soxl_d["Close"],
    "spy_ret": spy_d["Close"].pct_change() * 100,
    "soxx_ret": soxx_d["Close"].pct_change() * 100,
    "vix_c": vix_d["Close"],
    "vix_chg": vix_d["Close"].pct_change() * 100,
}).dropna(subset=["O", "H", "L", "C"])

# Only up to 2026-11-05 (confirmed daily bars)
df = df[df.index <= "2026-11-05"].copy()
df["prev_C"] = df["C"].shift(1)
df["prev_ret"] = df["C"].pct_change().shift(1) * 100
df["gap"] = (df["O"] / df["prev_C"] - 1) * 100
df["oc"] = (df["C"] / df["O"] - 1) * 100
df["cc"] = (df["C"] / df["prev_C"] - 1) * 100
df["next_O"] = df["O"].shift(-1)
df["next_C"] = df["C"].shift(-1)
df["oo"] = (df["next_O"] / df["O"] - 1) * 100
df["co_next"] = (df["next_O"] / df["C"] - 1) * 100
df["cc_next"] = (df["next_C"] / df["C"] - 1) * 100
df["clv"] = (df["C"] - df["L"]) / (df["H"] - df["L"]).replace(0, np.nan)

# Wilder ATR(14) as % of Close
tr = pd.concat([
    df["H"] - df["L"],
    (df["H"] - df["prev_C"]).abs(),
    (df["L"] - df["prev_C"]).abs()
], axis=1).max(axis=1)
df["atr14_pct"] = tr.ewm(alpha=1/14, adjust=False).mean() / df["C"] * 100
df["dd20"] = (df["C"] / df["C"].rolling(20).max() - 1) * 100

def summarize(s, label):
    s = s.dropna()
    n = len(s)
    if n == 0:
        return {"label": label, "N": 0}
    res = {
        "label": label,
        "N": int(n),
        "up_pct": round(float((s > 0).mean() * 100), 2),
        "mean": round(float(s.mean()), 2),
        "median": round(float(s.median()), 2),
        "p10": round(float(np.percentile(s, 10)), 2),
        "p25": round(float(np.percentile(s, 25)), 2),
        "p75": round(float(np.percentile(s, 75)), 2),
        "le_minus15_pct": round(float((s <= -15.0).mean() * 100), 2),
    }
    print(f"{label:65s} | N={res['N']:4d} | Up={res['up_pct']:5.1f}% | Mean={res['mean']:+6.2f}% | Med={res['median']:+6.2f}% | P10={res['p10']:+6.2f}% | <=-15%={res['le_minus15_pct']:4.1f}%")
    return res

results = []
print("=== BACKTEST 1: DAILY OO & NEXT-DAY STATS (2010-03 ~ 2026-11-05) ===")
valid_oo = df.dropna(subset=["oo"])
results.append(summarize(valid_oo["oo"], "All days OO (2010-2026)"))
results.append(summarize(valid_oo[valid_oo["atr14_pct"].shift(1) >= 14]["oo"], "Prior ATR14/C >= 14% -> OO"))
results.append(summarize(valid_oo[valid_oo["atr14_pct"].shift(1) >= 16]["oo"], "Prior ATR14/C >= 16% -> OO"))
results.append(summarize(valid_oo[(valid_oo["atr14_pct"].shift(1) >= 14) & (valid_oo["gap"] <= -3)]["oo"], "Prior ATR14/C >= 14% & Gap <= -3% -> OO"))

# Sector divergence on Day t -> Overnight (C_t -> O_{t+1}) and Next Day (C_t -> C_{t+1})
print("\n=== BACKTEST 2: INDEX RALLY + VIX DROP BUT SEMIS FALL (SECTOR LIQUIDATION) ===")
c1 = valid_oo[(valid_oo["spy_ret"] >= 1.0) & (valid_oo["soxx_ret"] <= -1.0)]
results.append(summarize(c1["co_next"], "SPY >= +1% & SOXX <= -1% -> Overnight (C->O')"))
results.append(summarize(c1["cc_next"], "SPY >= +1% & SOXX <= -1% -> Next Day (C->C')"))

c2 = valid_oo[(valid_oo["spy_ret"] >= 1.0) & (valid_oo["soxx_ret"] <= -2.0)]
results.append(summarize(c2["co_next"], "SPY >= +1% & SOXX <= -2% -> Overnight (C->O')"))
results.append(summarize(c2["cc_next"], "SPY >= +1% & SOXX <= -2% -> Next Day (C->C')"))

c3 = valid_oo[(valid_oo["vix_chg"] <= -10.0) & (valid_oo["cc"] <= -5.0)]
results.append(summarize(c3["co_next"], "VIX <= -10% & SOXL <= -5% -> Overnight (C->O')"))
results.append(summarize(c3["cc_next"], "VIX <= -10% & SOXL <= -5% -> Next Day (C->C')"))

# 2. 60-day 5m & 2-year 1h intraday trap backtest!
print("\n=== BACKTEST 3: 60D 5M & 730D 1H FIRST-HOUR UPPER-WICK REVERSAL TRAP ===")
h1 = yf.Ticker("SOXL").history(period="730d", interval="1h", prepost=False, auto_adjust=False)
h1["dt_est"] = h1.index.tz_convert(EST)
h1["date"] = h1["dt_est"].dt.strftime("%Y-%m-%d")
h1["hm"] = h1["dt_est"].dt.strftime("%H:%M")

# First 1h bar is 09:30 EST
first_h = h1[h1["hm"] == "09:30"].set_index("date")
m = df.join(first_h[["Open", "High", "Low", "Close"]].rename(columns={"Open": "h1_O", "High": "h1_H", "Low": "h1_L", "Close": "h1_C"}), how="inner")
m = m.dropna(subset=["oo", "h1_C"])
m["h1_ret"] = (m["h1_C"] / m["O"] - 1) * 100
m["h1_hi_ret"] = (m["h1_H"] / m["O"] - 1) * 100
m["h1_lo_ret"] = (m["h1_L"] / m["O"] - 1) * 100

# Case A: Gap <= -2%, 1h High >= +2% above Open, AND 1h Close >= +1.5% above Open (Sustained 1h rebound)
sustained = m[(m["gap"] <= -2.0) & (m["h1_hi_ret"] >= 2.0) & (m["h1_ret"] >= 1.5)]
results.append(summarize(sustained["oc"], "730d 1h: Gap<=-2%, 1h High>=+2%, 1h Close>=+1.5% -> O->C"))
results.append(summarize(sustained["oo"], "730d 1h: Gap<=-2%, 1h High>=+2%, 1h Close>=+1.5% -> O->O'"))

# Case B: Gap <= -2%, 1h High >= +2% above Open, BUT 1h Close < Open (Failed 1h pop = Nov 4 exact pattern!)
failed_pop = m[(m["gap"] <= -2.0) & (m["h1_hi_ret"] >= 2.0) & (m["h1_C"] < m["O"])]
results.append(summarize(failed_pop["oc"], "730d 1h: Gap<=-2%, 1h High>=+2%, BUT 1h Close < Open -> O->C"))
results.append(summarize(failed_pop["oo"], "730d 1h: Gap<=-2%, 1h High>=+2%, BUT 1h Close < Open -> O->O'"))

# Case C: Any day where 1h High >= +3% above Open, BUT 1h Close < Open (Upper-wick trap regardless of gap)
wick_trap = m[(m["h1_hi_ret"] >= 3.0) & (m["h1_C"] < m["O"])]
results.append(summarize(wick_trap["oc"], "730d 1h: 1h High>=+3% above Open, BUT 1h Close < Open -> O->C"))
results.append(summarize(wick_trap["oo"], "730d 1h: 1h High>=+3% above Open, BUT 1h Close < Open -> O->O'"))

# Case D: Using 60d 5m to check 10:05/10:15 EST (>+2% vs open) -> 10:30 EST (< open)
m5 = yf.Ticker("SOXL").history(period="60d", interval="5m", prepost=False, auto_adjust=False)
m5["dt_est"] = m5.index.tz_convert(EST)
m5["date"] = m5["dt_est"].dt.strftime("%Y-%m-%d")
m5["hm"] = m5["dt_est"].dt.strftime("%H:%M")

piv_c = m5.pivot_table(index="date", columns="hm", values="Close")
piv_o = m5.pivot_table(index="date", columns="hm", values="Open")
if "09:30" in piv_o.columns and "10:15" in piv_c.columns and "10:25" in piv_c.columns:
    d60 = pd.DataFrame({
        "open": piv_o["09:30"],
        "c_1000": piv_c["10:00"],
        "c_1015": piv_c["10:15"],
        "c_1025": piv_c["10:25"],
        "close": piv_c["15:55"],
    }).join(df[["oo", "oc", "gap"]], how="inner").dropna()
    d60["r_1000"] = (d60["c_1000"] / d60["open"] - 1) * 100
    d60["r_1015"] = (d60["c_1015"] / d60["open"] - 1) * 100
    d60["r_1025"] = (d60["c_1025"] / d60["open"] - 1) * 100
    print(f"\n60d 5m total valid days with OO: {len(d60)}")
    up_1015 = d60[d60["r_1015"] >= 1.5]
    flip_1025 = d60[(d60["r_1000"] >= 1.5) & (d60["r_1025"] < 0)]
    results.append(summarize(up_1015["oo"], "60d 5m: +1.5% at 10:15 EST -> OO"))
    results.append(summarize(flip_1025["oo"], "60d 5m: >=+1.5% at 10:00 EST then <0% by 10:30 EST -> OO"))

# Also check 730d 1h SPY vs SOXL divergence at 10:30 EST!
spy_h1 = yf.Ticker("SPY").history(period="730d", interval="1h", prepost=False, auto_adjust=False)
spy_h1["dt_est"] = spy_h1.index.tz_convert(EST)
spy_h1["date"] = spy_h1["dt_est"].dt.strftime("%Y-%m-%d")
spy_h1["hm"] = spy_h1["dt_est"].dt.strftime("%H:%M")
spy_first = spy_h1[spy_h1["hm"] == "09:30"].set_index("date")
m["spy_1h_vs_prevC"] = (spy_first["Close"] / spy_d["Close"].shift(1) - 1) * 100
m["soxl_1h_vs_prevC"] = (m["h1_C"] / m["prev_C"] - 1) * 100

div_1h = m[(m["spy_1h_vs_prevC"] >= 0.5) & (m["soxl_1h_vs_prevC"] <= -2.0)]
results.append(summarize(div_1h["oc"], "730d 1h: At 10:30 EST SPY >=+0.5% vs prevC & SOXL <=-2% vs prevC -> O->C"))
results.append(summarize(div_1h["oo"], "730d 1h: At 10:30 EST SPY >=+0.5% vs prevC & SOXL <=-2% vs prevC -> O->O'"))

div_1h_b = m[(m["spy_1h_vs_prevC"] >= 0.5) & (m["h1_C"] < m["O"])]
results.append(summarize(div_1h_b["oc"], "730d 1h: At 10:30 EST SPY >=+0.5% vs prevC & SOXL 1h < Open -> O->C"))
results.append(summarize(div_1h_b["oo"], "730d 1h: At 10:30 EST SPY >=+0.5% vs prevC & SOXL 1h < Open -> O->O'"))

print("\n=== DATES OF SPY >= +1% & SOXX <= -1% ===")
for idx, r in c1.iterrows():
    print(f"  {idx}: SPY={r['spy_ret']:+.2f}%, SOXX={r['soxx_ret']:+.2f}%, SOXL_CC={r['cc']:+.2f}%, Next_CO={r['co_next']:+.2f}%, Next_CC={r['cc_next']:+.2f}%")

# Print Nov 4 and Nov 5 exact daily metrics
print("\n=== NOV 4 & NOV 5 EXACT DAILY METRICS ===")
for dt_k in ["2026-11-03", "2026-11-04", "2026-11-05"]:
    if dt_k in df.index:
        r = df.loc[dt_k]
        print(dt_k, {
            "O": round(float(r["O"]), 4),
            "H": round(float(r["H"]), 4),
            "L": round(float(r["L"]), 4),
            "C": round(float(r["C"]), 4),
            "gap": round(float(r["gap"]), 2),
            "oc": round(float(r["oc"]), 2),
            "cc": round(float(r["cc"]), 2),
            "oo": round(float(r["oo"]), 2) if not pd.isna(r["oo"]) else None,
            "clv": round(float(r["clv"]), 4),
            "atr14_pct": round(float(r["atr14_pct"]), 2),
            "dd20": round(float(r["dd20"]), 2),
            "soxx_ret": round(float(r["soxx_ret"]), 2),
            "spy_ret": round(float(r["spy_ret"]), 2),
            "vix_c": round(float(r["vix_c"]), 2),
            "vix_chg": round(float(r["vix_chg"]), 2),
        })

with open(os.path.join(DATA_DIR, "backtest_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
