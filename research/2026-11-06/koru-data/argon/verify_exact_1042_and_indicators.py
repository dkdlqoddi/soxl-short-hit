#!/usr/bin/env python3
"""
Verify exact 2026-11-05 OHLC indicators (patching Yahoo's temporary Close=NaN rollover)
and exact 10:42 KST Naver 1-minute bars for KOSPI, 278540, 005930, 000660, plus BLS URL.
"""
import json
import urllib.request
import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Exact Naver 1-minute bars at 09:59 KST and 10:42 KST
naver_exact = {}
for code, kind in [("KOSPI", "index"), ("KOSDAQ", "index"), ("278540", "stock"), ("005930", "stock"), ("000660", "stock")]:
    url_chart = f"https://api.stock.naver.com/chart/{'domestic/index/' + code if kind=='index' else 'domestic/item/' + code}/day"
    try:
        req = urllib.request.Request(url_chart, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            bars = json.loads(r.read().decode("utf-8"))
            if isinstance(bars, dict):
                bars = bars.get("priceInfos", [])
            le_0904 = [b for b in bars if str(b.get("localDateTime", "")) <= "20261106090400"]
            le_0939 = [b for b in bars if str(b.get("localDateTime", "")) <= "20261106093959"]
            le_0959 = [b for b in bars if str(b.get("localDateTime", "")) <= "20261106095959"]
            le_1042 = [b for b in bars if str(b.get("localDateTime", "")) <= "20261106104259"]
            naver_exact[code] = {
                "at_0903_cb": le_0904[-1] if le_0904 else None,
                "at_0939_peak": le_0939[-1] if le_0939 else None,
                "at_0959_us_ah_end": le_0959[-1] if le_0959 else None,
                "at_1042_base": le_1042[-1] if le_1042 else None,
                "latest": bars[-1] if bars else None,
            }
    except Exception as e:
        naver_exact[code] = {"err": str(e)}

# 2. Exact 2026-11-05 OHLC technical indicators for KORU and EWY
def get_clean_daily(sym, official_1105_ohlc):
    t = yf.Ticker(sym)
    df = t.history(period="2y", interval="1d", auto_adjust=True)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[df.index <= "2026-11-05"].copy()
    ts = pd.Timestamp("2026-11-05")
    for col, val in official_1105_ohlc.items():
        df.loc[ts, col] = val
    return df

koru_df = get_clean_daily("KORU", {"Open": 8.915, "High": 9.0699, "Low": 6.465, "Close": 6.53, "Volume": 137307895})
ewy_df = get_clean_daily("EWY", {"Open": 144.935, "High": 145.73, "Low": 131.65, "Close": 131.65, "Volume": 43478191})

def calc_ind(d):
    c, h, l, o = d["Close"], d["High"], d["Low"], d["Open"]
    ret = c.pct_change()
    ret2 = c / c.shift(2) - 1
    ret5 = c / c.shift(5) - 1
    clv = (c - l) / (h - l)
    sma5, sma20, sma50, sma200 = c.rolling(5).mean(), c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    std20 = c.rolling(20).std()
    bb_low, bb_high = sma20 - 2 * std20, sma20 + 2 * std20
    pct_b = (c - bb_low) / (bb_high - bb_low)
    def rsi(p):
        delta = c.diff()
        u = delta.clip(lower=0).ewm(alpha=1/p, adjust=False, min_periods=p).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1/p, adjust=False, min_periods=p).mean()
        return 100 - 100 / (1 + u / dn)
    rsi2, rsi14 = rsi(2), rsi(14)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    atr_pct = atr14 / c
    atr_med100 = atr_pct.rolling(100).median()
    up_m = h - h.shift(1)
    dn_m = l.shift(1) - l
    pdm = pd.Series(np.where((up_m > dn_m) & (up_m > 0), up_m, 0.0), index=d.index)
    mdm = pd.Series(np.where((dn_m > up_m) & (dn_m > 0), dn_m, 0.0), index=d.index)
    pdi = 100 * pdm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr14
    mdi = 100 * mdm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr14
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    adx14 = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    i = -1
    return {
        "open": round(float(o.iloc[i]), 4),
        "high": round(float(h.iloc[i]), 4),
        "low": round(float(l.iloc[i]), 4),
        "close": round(float(c.iloc[i]), 4),
        "ret_1d_pct": round(float(ret.iloc[i]*100), 2),
        "ret_2d_pct": round(float(ret2.iloc[i]*100), 2),
        "ret_5d_pct": round(float(ret5.iloc[i]*100), 2),
        "clv": round(float(clv.iloc[i]), 4),
        "rsi2": round(float(rsi2.iloc[i]), 2),
        "rsi14": round(float(rsi14.iloc[i]), 2),
        "adx14": round(float(adx14.iloc[i]), 2),
        "plus_di": round(float(pdi.iloc[i]), 2),
        "minus_di": round(float(mdi.iloc[i]), 2),
        "atr14": round(float(atr14.iloc[i]), 4),
        "atr_pct": round(float(atr_pct.iloc[i]*100), 2),
        "atr_med100_pct": round(float(atr_med100.iloc[i]*100), 2),
        "sma5": round(float(sma5.iloc[i]), 2),
        "sma20": round(float(sma20.iloc[i]), 2),
        "sma50": round(float(sma50.iloc[i]), 2),
        "sma200": round(float(sma200.iloc[i]), 2),
        "dist_sma20_pct": round(float((c.iloc[i]/sma20.iloc[i]-1)*100), 2),
        "bb_low": round(float(bb_low.iloc[i]), 2),
        "bb_high": round(float(bb_high.iloc[i]), 2),
        "pct_b": round(float(pct_b.iloc[i]), 3),
        "rule_A": bool((clv.iloc[i] < 0.20) and (atr_pct.iloc[i] > atr_med100.iloc[i])),
        "rule_E": bool((adx14.iloc[i] > 25) and (mdi.iloc[i] > pdi.iloc[i]) and (clv.iloc[i] < 0.20)),
    }

# 3. Resolve BLS URL
bls_url = "https://www.bls.gov/schedule/news_release/empsit.htm"
try:
    req = urllib.request.Request("https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFsaIkEEjRfWh2n05-yLbIvOy8CeN6kXvwJ2flzcMskGymtHuYAVeEytTeLwf0ex7z4saR-n1CM6-vIuuG2HfIyIOt4ZLwB8LesfwRYu_L1fdIpUpgagMrjJoU5Hbs4dod_bJPjhWLgJCk", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=6) as r:
        bls_url = r.geturl()
except Exception:
    pass

res = {
    "naver_exact_intraday": naver_exact,
    "koru_1105_clean": calc_ind(koru_df),
    "ewy_1105_clean": calc_ind(ewy_df),
    "bls_url": bls_url,
}
with open(f"{OUT_DIR}/forecast_exact_verified.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False, indent=2))
