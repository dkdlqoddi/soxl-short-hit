import json
import os
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-05/koru-data/argon"
KST = ZoneInfo("Asia/Seoul")
EST = ZoneInfo("America/New_York")

def load_1m(sym):
    df = pd.read_csv(os.path.join(OUT_DIR, f"{sym.lower()}_1m_window.csv"))
    df["kst"] = pd.to_datetime(df["kst_str"]).dt.tz_localize(KST)
    return df

koru = load_1m("koru")
ewy = load_1m("ewy")
soxl = load_1m("soxl")
qcom = load_1m("qcom")
arm = load_1m("arm")

# Also fetch SOXX, MU, NVDA, AMD 1m for comparison
extra = {}
for s in ["SOXX", "MU", "AMD", "NVDA"]:
    d = yf.Ticker(s).history(period="5d", interval="1m", prepost=True)
    d["kst"] = d.index.tz_convert(KST)
    extra[s] = d

# Define phases in KST from 2026-11-04 08:40 to 2026-11-05 10:00
phases = [
    ("P1_1104_AH_Late (08:43~09:59 KST, 11/3 18:43~19:59 EST)", "2026-11-04 08:43", "2026-11-04 09:59"),
    ("P2_1104_US_Pre_Early (18:00~20:59 KST, 11/4 04:00~06:59 EST)", "2026-11-04 18:00", "2026-11-04 20:59"),
    ("P3_1104_US_Pre_Late (21:00~23:29 KST, 11/4 07:00~09:29 EST)", "2026-11-04 21:00", "2026-11-04 23:29"),
    ("P4_1104_US_Reg_Open_Bounce (23:30~00:59 KST, 11/4 09:30~10:59 EST)", "2026-11-04 23:30", "2026-11-05 00:59"),
    ("P5_1104_US_Reg_Mid_Close (01:00~05:59 KST, 11/4 11:00~15:59 EST)", "2026-11-05 01:00", "2026-11-05 05:59"),
    ("P6_1105_AH_QCOM_ARM (06:00~08:42 KST, 11/4 16:00~18:42 EST)", "2026-11-05 06:00", "2026-11-05 08:42"),
    ("P7_1105_AH_Expiry_KR_Open (08:43~09:59 KST, 11/4 18:43~19:59 EST)", "2026-11-05 08:43", "2026-11-05 09:59"),
]

print("=== KORU PHASE BREAKDOWN ===")
phase_records = []
for label, s_str, e_str in phases:
    t0 = pd.Timestamp(s_str, tz=KST)
    t1 = pd.Timestamp(e_str, tz=KST)
    sub = koru[(koru["kst"] >= t0) & (koru["kst"] <= t1)]
    esub = ewy[(ewy["kst"] >= t0) & (ewy["kst"] <= t1)]
    ssub = soxl[(soxl["kst"] >= t0) & (soxl["kst"] <= t1)]
    if not sub.empty:
        hi_row = sub.loc[sub["High"].idxmax()]
        lo_row = sub.loc[sub["Low"].idxmin()]
        rec = {
            "phase": label,
            "open_time": sub["kst_str"].iloc[0],
            "open": float(sub["Open"].iloc[0]),
            "close_time": sub["kst_str"].iloc[-1],
            "close": float(sub["Close"].iloc[-1]),
            "high": float(hi_row["High"]),
            "high_time": hi_row["kst_str"],
            "low": float(lo_row["Low"]),
            "low_time": lo_row["kst_str"],
            "ewy_open": float(esub["Open"].iloc[0]) if not esub.empty else None,
            "ewy_close": float(esub["Close"].iloc[-1]) if not esub.empty else None,
            "soxl_open": float(ssub["Open"].iloc[0]) if not ssub.empty else None,
            "soxl_close": float(ssub["Close"].iloc[-1]) if not ssub.empty else None,
        }
        phase_records.append(rec)
        print(f"{label}:")
        print(f"  KORU: {rec['open']:.4f} ({rec['open_time']}) -> {rec['close']:.4f} ({rec['close_time']}) | H={rec['high']:.4f} ({rec['high_time']}) | L={rec['low']:.4f} ({rec['low_time']})")
        if not esub.empty:
            ehi = esub.loc[esub["High"].idxmax()]
            elo = esub.loc[esub["Low"].idxmin()]
            print(f"  EWY : {rec['ewy_open']:.2f} -> {rec['ewy_close']:.2f} | H={ehi['High']:.2f} ({ehi['kst_str']}) | L={elo['Low']:.2f} ({elo['kst_str']})")
        if not ssub.empty:
            shi = ssub.loc[ssub["High"].idxmax()]
            slo = ssub.loc[ssub["Low"].idxmin()]
            print(f"  SOXL: {rec['soxl_open']:.2f} -> {rec['soxl_close']:.2f} | H={shi['High']:.2f} ({shi['kst_str']}) | L={slo['Low']:.2f} ({slo['kst_str']})")

# Detailed 30-min snapshots of KORU, EWY, SOXL from 11/4 08:30 to 11/5 10:00
print("\n=== 30-MIN KEY TIMESTAMPS (KORU / EWY / SOXL / QCOM / ARM) ===")
check_times = [
    "2026-11-04 08:43", "2026-11-04 08:55", "2026-11-04 09:00", "2026-11-04 09:10",
    "2026-11-04 09:15", "2026-11-04 09:30", "2026-11-04 09:59",
    "2026-11-04 18:00", "2026-11-04 19:00", "2026-11-04 19:34", "2026-11-04 20:00",
    "2026-11-04 21:00", "2026-11-04 22:00", "2026-11-04 22:15", "2026-11-04 23:00",
    "2026-11-04 23:30", "2026-11-04 23:34", "2026-11-04 23:47", "2026-11-05 00:00",
    "2026-11-05 00:15", "2026-11-05 00:30", "2026-11-05 01:00", "2026-11-05 02:00",
    "2026-11-05 03:00", "2026-11-05 04:00", "2026-11-05 05:00", "2026-11-05 05:59",
    "2026-11-05 06:05", "2026-11-05 06:15", "2026-11-05 06:30", "2026-11-05 07:00",
    "2026-11-05 07:30", "2026-11-05 08:00", "2026-11-05 08:30",
    "2026-11-05 08:43", "2026-11-05 08:55", "2026-11-05 09:00", "2026-11-05 09:10",
    "2026-11-05 09:30", "2026-11-05 09:59"
]

def val_at(df, ts_str):
    t = pd.Timestamp(ts_str, tz=KST)
    s = df[df["kst"] <= t]
    if s.empty:
        return "N/A"
    r = s.iloc[-1]
    return f"{r['Close']:.4f}@{r['kst_str'][-5:]}"

for ts in check_times:
    print(f"{ts} KST | KORU={val_at(koru, ts)} | EWY={val_at(ewy, ts)} | SOXL={val_at(soxl, ts)} | QCOM={val_at(qcom, ts)} | ARM={val_at(arm, ts)}")

# Check when invalidation levels were hit for KORU after 2026-11-04 08:43 KST!
post_base = koru[koru["kst"] >= pd.Timestamp("2026-11-04 08:43", tz=KST)]
print("\n=== INVALIDATION LEVEL CROSSINGS (from 2026-11-04 08:43 KST) ===")
print("Overall High after 08:43:", post_base.loc[post_base["High"].idxmax()][["kst_str", "High", "Close"]].to_dict())
print("Overall Low after 08:43:", post_base.loc[post_base["Low"].idxmin()][["kst_str", "Low", "Close"]].to_dict())

for lvl, direction in [(11.56, "above"), (11.59, "above"), (10.83, "below"), (10.37, "below")]:
    if direction == "above":
        hits = post_base[post_base["High"] >= lvl]
    else:
        hits = post_base[post_base["Low"] <= lvl]
    if hits.empty:
        print(f"Level {lvl} ({direction}): NEVER HIT")
    else:
        print(f"Level {lvl} ({direction}): FIRST HIT at {hits.iloc[0]['kst_str']} (H={hits.iloc[0]['High']:.4f}, L={hits.iloc[0]['Low']:.4f}, C={hits.iloc[0]['Close']:.4f}), total bars={len(hits)}")

# Korean 5m intraday trajectory on 2026-11-04 and 2026-11-05
print("\n=== KOREAN KOSPI 30-MIN TRAJECTORY ON 2026-11-04 & 2026-11-05 ===")
ks = yf.Ticker("^KS11").history(period="5d", interval="5m")
ks["kst"] = ks.index.tz_convert(KST)
ss = yf.Ticker("005930.KS").history(period="5d", interval="5m")
ss["kst"] = ss.index.tz_convert(KST)
sk = yf.Ticker("000660.KS").history(period="5d", interval="5m")
sk["kst"] = sk.index.tz_convert(KST)
fx = yf.Ticker("KRW=X").history(period="5d", interval="5m")
fx["kst"] = fx.index.tz_convert(KST)

for idx, r in ks[ks["kst"] >= pd.Timestamp("2026-11-04 09:00", tz=KST)].iterrows():
    t = r["kst"]
    if t.minute in (0, 10, 15, 30, 45) or r["High"] > 5820 or r["Low"] < 5450:
        s_val = ss[ss["kst"] <= t]["Close"].iloc[-1] if not ss[ss["kst"] <= t].empty else np.nan
        h_val = sk[sk["kst"] <= t]["Close"].iloc[-1] if not sk[sk["kst"] <= t].empty else np.nan
        f_val = fx[fx["kst"] <= t]["Close"].iloc[-1] if not fx[fx["kst"] <= t].empty else np.nan
        print(f"{t.strftime('%Y-%m-%d %H:%M')} | KOSPI={r['Close']:.2f} (H={r['High']:.2f}, L={r['Low']:.2f}) | 005930={s_val:.0f} | 000660={h_val:.0f} | USDKRW={f_val:.2f}")

with open(os.path.join(OUT_DIR, "phase_summary.json"), "w", encoding="utf-8") as f:
    json.dump(phase_records, f, ensure_ascii=False, indent=2)
