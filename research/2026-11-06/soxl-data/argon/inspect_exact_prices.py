import json
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

out_dir = "research/2026-11-06/soxl-data/argon"

with open(f"{out_dir}/daily_summary.json") as f:
    ds = json.load(f)

print("=== 09:45 KST daily_summary.json check ===")
for k in sorted(ds.keys()):
    v = ds[k]
    if isinstance(v, dict):
        print(k, v)
    elif isinstance(v, list) and len(v) > 0:
        print(k, v[-2:])

syms = [
    "SOXL", "SOXS", "SOXX", "SMH",
    "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "QCOM", "ARM", "MCHP", "ANET", "INTC", "MRVL", "AMAT", "LRCX", "KLAC",
    "QQQ", "SPY", "NQ=F", "ES=F", "^VIX", "^TNX", "KRW=X", "^N225", "^KS11", "005930.KS", "000660.KS", "EWY", "KORU"
]

exact = {}
for s in syms:
    try:
        t = yf.Ticker(s)
        inf = t.info
        exact[s] = {
            "shortName": inf.get("shortName"),
            "reg_price": inf.get("regularMarketPrice"),
            "reg_prev_close": inf.get("regularMarketPreviousClose"),
            "reg_open": inf.get("regularMarketOpen"),
            "reg_high": inf.get("regularMarketDayHigh"),
            "reg_low": inf.get("regularMarketDayLow"),
            "reg_chg_pct": inf.get("regularMarketChangePercent"),
            "post_price": inf.get("postMarketPrice"),
            "post_chg_pct": inf.get("postMarketChangePercent"),
            "pre_price": inf.get("preMarketPrice"),
            "bid": inf.get("bid"),
            "ask": inf.get("ask"),
        }
        rp = exact[s]["reg_price"]
        rpc = exact[s]["reg_prev_close"]
        rcp = exact[s]["reg_chg_pct"]
        pp = exact[s]["post_price"]
        pcp = exact[s]["post_chg_pct"]
        print(f"{s:10s} | reg={rp} (prev={rpc}, {rcp}%) | post={pp} ({pcp}%)")
    except Exception as e:
        print(f"{s:10s} | ERR: {e}")

with open(f"{out_dir}/ticker_info_exact.json", "w") as f:
    json.dump(exact, f, indent=2)

# Detailed minute-by-minute check of SOXL, SOXX, SMH, NQ=F from 05:55 KST to latest
print("\n=== Detailed 1m check around Regular Close (06:00 KST) -> AH Low -> AH Close (09:59 KST) -> Base Time (10:42 KST) -> Latest ===")
for sym in ["SOXL", "SOXX", "SMH", "NVDA", "AMD", "MU", "AVGO", "TSM", "NQ=F", "ES=F"]:
    clean = sym.replace("^", "").replace("=", "_").lower()
    try:
        df = pd.read_csv(f"{out_dir}/forecast_{clean}_1m.csv", index_col=0, parse_dates=True)
    except Exception:
        df = yf.Ticker(sym).history(period="5d", interval="1m", prepost=True)
        df.index = df.index.tz_convert("Asia/Seoul")
    sub = df[df.index >= "2026-11-06 05:55:00+09:00"]
    reg_end = df[(df.index >= "2026-11-06 05:55:00+09:00") & (df.index < "2026-11-06 06:00:00+09:00")]
    ah = df[(df.index >= "2026-11-06 06:00:00+09:00") & (df.index < "2026-11-06 10:00:00+09:00")]
    post_1000 = df[(df.index >= "2026-11-06 10:00:00+09:00") & (df.index <= "2026-11-06 10:42:59+09:00")]
    after_1042 = df[df.index > "2026-11-06 10:42:59+09:00"]
    r_last = float(reg_end["Close"].iloc[-1]) if not reg_end.empty else None
    ah_lo = float(ah["Low"].min()) if not ah.empty else None
    ah_lo_t = ah["Low"].idxmin().strftime("%H:%M") if not ah.empty else None
    ah_hi = float(ah["High"].max()) if not ah.empty else None
    ah_hi_t = ah["High"].idxmax().strftime("%H:%M") if not ah.empty else None
    ah_end = float(ah["Close"].iloc[-1]) if not ah.empty else None
    ah_end_t = ah.index[-1].strftime("%H:%M") if not ah.empty else None
    p1042 = float(post_1000["Close"].iloc[-1]) if not post_1000.empty else ah_end
    lat = float(after_1042["Close"].iloc[-1]) if not after_1042.empty else p1042
    lat_t = after_1042.index[-1].strftime("%H:%M") if not after_1042.empty else (post_1000.index[-1].strftime("%H:%M") if not post_1000.empty else ah_end_t)
    print(f"{sym:6s}: 05:59={r_last} | AH low={ah_lo}@{ah_lo_t}, high={ah_hi}@{ah_hi_t}, 09:59={ah_end}@{ah_end_t} | 10:42={p1042} | latest={lat}@{lat_t}")

# Check Naver investor trends & details
with open(f"{out_dir}/forecast_naver_1044.json") as f:
    nv = json.load(f)
print("\n=== Naver KR details (10:44~10:45 KST) ===")
for k in ["KOSPI", "KOSDAQ", "005930_Samsung", "000660_SKHynix", "042700_HanmiSemi"]:
    d = nv.get(k, {})
    print(k, "close:", d.get("closePrice"), "chg:", d.get("compareToPreviousClosePrice"), "ratio:", d.get("fluctuationsRatio"),
          "open:", d.get("openPrice"), "high:", d.get("highPrice"), "low:", d.get("lowPrice"), "overMarket:", d.get("overMarketPriceInfo"))
for k in ["KOSPI_trend", "005930_trend", "000660_trend"]:
    print(k, str(nv.get(k))[:400])
