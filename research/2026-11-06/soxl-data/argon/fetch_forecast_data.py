import json
import datetime
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

now_kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
print("Fetch started KST:", now_kst.strftime("%Y-%m-%d %H:%M:%S"))

out_dir = "research/2026-11-06/soxl-data/argon"

# 1. Fetch 1m data (5d, prepost=True) for key US tickers & futures
tickers_1m = [
    "SOXL", "SOXS", "SOXX", "SMH",
    "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "QCOM", "ARM", "INTC", "MRVL", "TXN", "AMAT", "LRCX", "KLAC",
    "QQQ", "SPY", "NQ=F", "ES=F", "^VIX", "^TNX", "KRW=X", "DX-Y.NYB",
    "EWY", "KORU"
]

snapshot = {"fetched_at_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S"), "tickers": {}}

for sym in tickers_1m:
    try:
        t = yf.Ticker(sym)
        df1m = t.history(period="5d", interval="1m", prepost=True)
        df1d = t.history(period="15d", interval="1d", auto_adjust=False)
        info_rec = {}
        if not df1d.empty:
            df1d_idx = df1d.index.tz_convert("America/New_York") if df1d.index.tz is not None else df1d.index
            last_days = []
            for idx, row in df1d.tail(5).iterrows():
                d_str = idx.strftime("%Y-%m-%d")
                last_days.append({
                    "date": d_str,
                    "open": round(float(row["Open"]), 4) if pd.notna(row["Open"]) else None,
                    "high": round(float(row["High"]), 4) if pd.notna(row["High"]) else None,
                    "low": round(float(row["Low"]), 4) if pd.notna(row["Low"]) else None,
                    "close": round(float(row["Close"]), 4) if pd.notna(row["Close"]) else None,
                    "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
                })
            info_rec["daily_tail"] = last_days

        if not df1m.empty:
            df1m_et = df1m.copy()
            df1m_et.index = df1m_et.index.tz_convert("America/New_York")
            df1m_kst = df1m.copy()
            df1m_kst.index = df1m_kst.index.tz_convert("Asia/Seoul")

            # Check Nov 5 regular close (15:59 ET) and AH close (<= 20:42 ET on Nov 5)
            nov5_reg = df1m_et[(df1m_et.index >= "2026-11-05 09:30:00") & (df1m_et.index < "2026-11-05 16:00:00")]
            nov5_ah = df1m_et[(df1m_et.index >= "2026-11-05 16:00:00") & (df1m_et.index <= "2026-11-05 20:42:00")]
            up_to_base = df1m_kst[df1m_kst.index <= "2026-11-06 10:42:59"]
            after_base = df1m_kst[df1m_kst.index > "2026-11-06 10:42:59"]

            if not nov5_reg.empty:
                info_rec["nov5_reg_open"] = round(float(nov5_reg["Open"].iloc[0]), 4)
                info_rec["nov5_reg_high"] = round(float(nov5_reg["High"].max()), 4)
                info_rec["nov5_reg_low"] = round(float(nov5_reg["Low"].min()), 4)
                info_rec["nov5_reg_last_1m"] = round(float(nov5_reg["Close"].iloc[-1]), 4)
                info_rec["nov5_reg_vol"] = int(nov5_reg["Volume"].sum())

            if not nov5_ah.empty:
                info_rec["nov5_ah_open"] = round(float(nov5_ah["Open"].iloc[0]), 4)
                info_rec["nov5_ah_high"] = round(float(nov5_ah["High"].max()), 4)
                info_rec["nov5_ah_low"] = round(float(nov5_ah["Low"].min()), 4)
                info_rec["nov5_ah_high_time_kst"] = nov5_ah["High"].idxmax().tz_convert("Asia/Seoul").strftime("%Y-%m-%d %H:%M")
                info_rec["nov5_ah_low_time_kst"] = nov5_ah["Low"].idxmin().tz_convert("Asia/Seoul").strftime("%Y-%m-%d %H:%M")
                info_rec["nov5_ah_last"] = round(float(nov5_ah["Close"].iloc[-1]), 4)
                info_rec["nov5_ah_last_time_kst"] = nov5_ah.index[-1].tz_convert("Asia/Seoul").strftime("%Y-%m-%d %H:%M")
                info_rec["nov5_ah_vol"] = int(nov5_ah["Volume"].sum())

            if not up_to_base.empty:
                info_rec["at_base_1042_price"] = round(float(up_to_base["Close"].iloc[-1]), 4)
                info_rec["at_base_1042_bar_kst"] = up_to_base.index[-1].strftime("%Y-%m-%d %H:%M")

            info_rec["latest_1m_price"] = round(float(df1m_kst["Close"].iloc[-1]), 4)
            info_rec["latest_1m_bar_kst"] = df1m_kst.index[-1].strftime("%Y-%m-%d %H:%M")

            if sym in ["SOXL", "SOXX", "SMH", "NVDA", "AMD", "MU", "AVGO", "TSM", "NQ=F", "^VIX"]:
                clean_sym = sym.replace("^", "").replace("=", "_").lower()
                df1m_kst.to_csv(f"{out_dir}/forecast_{clean_sym}_1m.csv")

        snapshot["tickers"][sym] = info_rec
    except Exception as e:
        snapshot["tickers"][sym] = {"error": str(e)}

# 2. Nasdaq Historical API for SOXL and SOXX to cross-verify official close & split
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}
nasdaq_check = {}
for nsym in ["SOXL", "SOXX", "SMH"]:
    try:
        url = f"https://api.nasdaq.com/api/quote/{nsym}/historical?assetclass=etf&fromdate=2026-10-15&todate=2026-11-06&limit=30"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("data", {}).get("tradesTable", {}).get("rows", [])
            nasdaq_check[nsym] = rows[:10]
    except Exception as e:
        nasdaq_check[nsym] = {"error": str(e)}
snapshot["nasdaq_official_recent"] = nasdaq_check

# 3. Naver Mobile API for Korean market realtime (around 10:44 KST!)
naver_urls = {
    "KOSPI": "https://m.stock.naver.com/api/index/KOSPI/basic",
    "KOSDAQ": "https://m.stock.naver.com/api/index/KOSDAQ/basic",
    "005930_Samsung": "https://m.stock.naver.com/api/stock/005930/basic",
    "000660_SKHynix": "https://m.stock.naver.com/api/stock/000660/basic",
    "042700_HanmiSemi": "https://m.stock.naver.com/api/stock/042700/basic",
}
naver_data = {"fetched_at_kst": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")}
for k, url in naver_urls.items():
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            naver_data[k] = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        naver_data[k] = {"error": str(e)}

# Also fetch investor trend for KOSPI & Samsung & SK Hynix if available
for k, url in [
    ("KOSPI_trend", "https://m.stock.naver.com/api/index/KOSPI/trend"),
    ("005930_trend", "https://m.stock.naver.com/api/stock/005930/trend"),
    ("000660_trend", "https://m.stock.naver.com/api/stock/000660/trend"),
]:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            naver_data[k] = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        naver_data[k] = {"error": str(e)}

with open(f"{out_dir}/forecast_snapshot_1044.json", "w", encoding="utf-8") as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)

with open(f"{out_dir}/forecast_naver_1044.json", "w", encoding="utf-8") as f:
    json.dump(naver_data, f, ensure_ascii=False, indent=2)

print("Saved forecast_snapshot_1044.json and forecast_naver_1044.json successfully.")
# Print quick summary of SOXL, SOXX, SMH, NQ=F, VIX, KOSPI
for s in ["SOXL", "SOXS", "SOXX", "SMH", "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "NQ=F", "ES=F", "^VIX", "^TNX", "KRW=X"]:
    d = snapshot["tickers"].get(s, {})
    print(s, "-> reg_last:", d.get("nov5_reg_last_1m"), "ah_last:", d.get("nov5_ah_last"), "at_1042:", d.get("at_base_1042_price"), "latest:", d.get("latest_1m_price"), "daily_tail_last:", d.get("daily_tail", [{}])[-1] if d.get("daily_tail") else None)
print("Nasdaq SOXL:", nasdaq_check.get("SOXL", [])[:3])
for k in ["KOSPI", "KOSDAQ", "005930_Samsung", "000660_SKHynix"]:
    nd = naver_data.get(k, {})
    print(k, "->", nd.get("closePrice"), nd.get("fluctuationsRatio"), nd.get("localTradedAt"))
