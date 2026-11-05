import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-05/koru-data/argon"
os.makedirs(OUT_DIR, exist_ok=True)

KST = ZoneInfo("Asia/Seoul")
EST = ZoneInfo("America/New_York")

now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
print(f"Data fetch started at: {now_kst}")

# 1. 1-minute data for KORU, EWY, SOXL, SOXX, QCOM, ARM, MU, AMD, NVDA
tickers_1m = ["KORU", "EWY", "SOXL", "SOXX", "QCOM", "ARM", "MU", "AMD", "NVDA"]
data_1m = {}
for sym in tickers_1m:
    try:
        df = yf.Ticker(sym).history(period="5d", interval="1m", prepost=True)
        if not df.empty:
            df = df.copy()
            df["kst"] = df.index.tz_convert(KST)
            df["est"] = df.index.tz_convert(EST)
            data_1m[sym] = df
            print(f"{sym} 1m rows: {len(df)} | {df['kst'].iloc[0]} -> {df['kst'].iloc[-1]}")
    except Exception as e:
        print(f"Error fetching 1m {sym}: {e}")

# Save KORU and EWY 1m CSVs for 2026-11-04 06:00 KST ~ 2026-11-05 13:30 KST
for sym in ["KORU", "EWY", "SOXL", "QCOM", "ARM"]:
    if sym in data_1m:
        df = data_1m[sym]
        sub = df[df["kst"] >= pd.Timestamp("2026-11-04 06:00:00", tz=KST)].copy()
        sub["kst_str"] = sub["kst"].dt.strftime("%Y-%m-%d %H:%M")
        sub["est_str"] = sub["est"].dt.strftime("%Y-%m-%d %H:%M")
        sub[["kst_str", "est_str", "Open", "High", "Low", "Close", "Volume"]].to_csv(
            os.path.join(OUT_DIR, f"{sym.lower()}_1m_window.csv"), index=False
        )

# 2. Check exact expiry timestamps for the 3 models
# Codex Astra Max: 2026-11-04 08:43 -> 2026-11-05 08:43 KST (base $11.41)
# Antigravity Argon High: 2026-11-04 08:55 -> 2026-11-05 08:55 KST (base $11.30)
# Claude Fable Max: 2026-11-04 09:10 -> 2026-11-05 09:10 KST (base $11.39)
koru = data_1m["KORU"]

def get_price_at_or_before(df, target_kst_str):
    target = pd.Timestamp(target_kst_str, tz=KST)
    # Note: yfinance 1m bar timestamp `t` covers [t, t+1m). Wait! Let's inspect bars around target!
    around = df[(df["kst"] >= target - pd.Timedelta(minutes=15)) & (df["kst"] <= target + pd.Timedelta(minutes=10))]
    before_or_at = df[df["kst"] <= target]
    last_bar = before_or_at.iloc[-1] if not before_or_at.empty else None
    return around, last_bar

targets = [
    ("Codex Astra Max", "2026-11-04 08:43:00", 11.41, "2026-11-05 08:43:00"),
    ("Antigravity Argon High", "2026-11-04 08:55:00", 11.30, "2026-11-05 08:55:00"),
    ("Claude Fable Max", "2026-11-04 09:10:00", 11.39, "2026-11-05 09:10:00"),
]

print("\n=== BASE TIME 1M BARS CHECK ===")
for name, base_str, stated_base, exp_str in targets:
    around_b, last_b = get_price_at_or_before(koru, base_str)
    print(f"\n--- {name} Base ({base_str}, stated ${stated_base}) ---")
    for _, r in around_b.tail(8).iterrows():
        print(f"  {r['kst'].strftime('%Y-%m-%d %H:%M')} ({r['est'].strftime('%H:%M EST')}): O={r['Open']:.4f} H={r['High']:.4f} L={r['Low']:.4f} C={r['Close']:.4f} V={r['Volume']}")

print("\n=== EXPIRY TIME 1M BARS CHECK ===")
for name, base_str, stated_base, exp_str in targets:
    around_e, last_e = get_price_at_or_before(koru, exp_str)
    print(f"\n--- {name} Expiry ({exp_str}, base ${stated_base}) ---")
    for _, r in around_e.iterrows():
        print(f"  {r['kst'].strftime('%Y-%m-%d %H:%M')} ({r['est'].strftime('%H:%M EST')}): O={r['Open']:.4f} H={r['High']:.4f} L={r['Low']:.4f} C={r['Close']:.4f} V={r['Volume']}")
    if last_e is not None:
        print(f"  => Last bar <= {exp_str}: {last_e['kst'].strftime('%Y-%m-%d %H:%M')} Close=${last_e['Close']:.4f} (vs stated base ${stated_base}: {(last_e['Close']/stated_base - 1)*100:+.2f}%)")

# 3. Korean market & FX & Macro 5m / 1d data
kr_syms = ["^KS11", "^KQ11", "005930.KS", "000660.KS", "278540.KS", "KRW=X", "^TNX", "^VIX", "ES=F", "NQ=F", "KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "AMD", "QCOM", "ARM"]
print("\n=== DAILY BARS (2026-11-02 ~ 2026-11-05) ===")
daily_summary = {}
for sym in kr_syms:
    try:
        d = yf.Ticker(sym).history(period="10d", interval="1d")
        sub = d[d.index >= "2026-10-30"]
        print(f"\n[{sym}]")
        for idx, r in sub.iterrows():
            print(f"  {idx.strftime('%Y-%m-%d')}: O={r['Open']:.2f} H={r['High']:.2f} L={r['Low']:.2f} C={r['Close']:.2f} V={r['Volume']}")
        daily_summary[sym] = sub.reset_index().astype(str).to_dict(orient="records")
    except Exception as e:
        print(f"Error daily {sym}: {e}")

# 4. Korean intraday 5m bars for 2026-11-04 and 2026-11-05
print("\n=== KOREAN 5M INTRADAY (11/4 & 11/5) ===")
for sym in ["^KS11", "005930.KS", "000660.KS", "278540.KS", "KRW=X"]:
    try:
        df5 = yf.Ticker(sym).history(period="5d", interval="5m")
        if not df5.empty:
            df5["kst"] = df5.index.tz_convert(KST)
            for day_str in ["2026-11-04", "2026-11-05"]:
                dsub = df5[df5["kst"].dt.strftime("%Y-%m-%d") == day_str]
                if not dsub.empty:
                    print(f"{sym} {day_str}: Open={dsub['Open'].iloc[0]:.2f} ({dsub['kst'].iloc[0].strftime('%H:%M')}), High={dsub['High'].max():.2f} ({dsub.loc[dsub['High'].idxmax(), 'kst'].strftime('%H:%M')}), Low={dsub['Low'].min():.2f} ({dsub.loc[dsub['Low'].idxmin(), 'kst'].strftime('%H:%M')}), Last={dsub['Close'].iloc[-1]:.2f} ({dsub['kst'].iloc[-1].strftime('%H:%M')})")
    except Exception as e:
        print(f"Error 5m {sym}: {e}")

# 5. Naver Finance Real-time JSON check
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
naver_urls = {
    "KOSPI": "https://m.stock.naver.com/api/index/KOSPI/basic",
    "KOSDAQ": "https://m.stock.naver.com/api/index/KOSDAQ/basic",
    "005930": "https://m.stock.naver.com/api/stock/005930/basic",
    "000660": "https://m.stock.naver.com/api/stock/000660/basic",
    "278540": "https://m.stock.naver.com/api/stock/278540/basic",
}
print("\n=== NAVER REALTIME API ===")
naver_out = {}
for k, url in naver_urls.items():
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            j = json.loads(resp.read().decode("utf-8"))
            naver_out[k] = j
            print(f"{k}: closePrice={j.get('closePrice')} fluctuationsRatio={j.get('fluctuationsRatio')}% localTradedAt={j.get('localTradedAt')}")
    except Exception as e:
        print(f"Naver error {k}: {e}")

with open(os.path.join(OUT_DIR, "naver_realtime.json"), "w", encoding="utf-8") as f:
    json.dump({"fetched_at": now_kst, "data": naver_out}, f, ensure_ascii=False, indent=2)
