import json
import datetime
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

out_dir = "research/2026-11-06/soxl-data/argon"

# 1. Intraday indicators on SOXL (5m, 15m, 30m, 1h, 2h) — both Regular-only (matching TradingView daytrade-combo-study) and Extended-hours!
df5m_reg = yf.Ticker("SOXL").history(period="60d", interval="5m", prepost=False)
df15m_reg = yf.Ticker("SOXL").history(period="60d", interval="15m", prepost=False)
df30m_reg = yf.Ticker("SOXL").history(period="60d", interval="30m", prepost=False)
df1h_reg = yf.Ticker("SOXL").history(period="730d", interval="1h", prepost=False)
df1h_ext = yf.Ticker("SOXL").history(period="60d", interval="1h", prepost=True)
df5m_ext = yf.Ticker("SOXL").history(period="5d", interval="5m", prepost=True)

def calc_macd(s):
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(sig.iloc[-1]), float((macd - sig).iloc[-1])

def calc_rsi(s, p):
    d = s.diff()
    u = d.clip(lower=0).ewm(alpha=1/p, adjust=False, min_periods=p).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False, min_periods=p).mean()
    rs = u / dn.replace(0, np.nan)
    return float((100 - 100 / (1 + rs)).iloc[-1])

# Build 2h regular bars from 1h regular bars (09:30+10:30, 11:30+12:30, 13:30+14:30, 15:30)
df1h_et = df1h_reg.copy()
df1h_et.index = df1h_et.index.tz_convert("America/New_York")
bars_2h = []
for d_et, grp in df1h_et.groupby(df1h_et.index.date):
    grp = grp.sort_index()
    for i in range(0, len(grp), 2):
        chunk = grp.iloc[i:i+2]
        bars_2h.append({
            "ts": chunk.index[0],
            "Open": float(chunk["Open"].iloc[0]),
            "High": float(chunk["High"].max()),
            "Low": float(chunk["Low"].min()),
            "Close": float(chunk["Close"].iloc[-1]),
        })
df2h_reg = pd.DataFrame(bars_2h).set_index("ts")

intraday_stats = {
    "reg_5m_sma120": round(float(df5m_reg["Close"].rolling(120).mean().iloc[-1]), 2),
    "ext_5m_sma120": round(float(df5m_ext["Close"].rolling(120).mean().iloc[-1]), 2),
    "ext_5m_ema9": round(float(df5m_ext["Close"].ewm(span=9, adjust=False).mean().iloc[-1]), 2),
    "ext_5m_ema21": round(float(df5m_ext["Close"].ewm(span=21, adjust=False).mean().iloc[-1]), 2),
    "reg_15m_rsi14": round(calc_rsi(df15m_reg["Close"], 14), 2),
    "reg_15m_rsi2": round(calc_rsi(df15m_reg["Close"], 2), 2),
    "reg_30m_rsi14": round(calc_rsi(df30m_reg["Close"], 14), 2),
    "reg_30m_rsi2": round(calc_rsi(df30m_reg["Close"], 2), 2),
    "reg_30m_macd": [round(x, 3) for x in calc_macd(df30m_reg["Close"])],
    "reg_1h_rsi14": round(calc_rsi(df1h_reg["Close"], 14), 2),
    "reg_1h_macd": [round(x, 3) for x in calc_macd(df1h_reg["Close"])],
    "ext_1h_rsi14": round(calc_rsi(df1h_ext["Close"], 14), 2),
    "ext_1h_macd": [round(x, 3) for x in calc_macd(df1h_ext["Close"])],
    "reg_2h_rsi14": round(calc_rsi(df2h_reg["Close"], 14), 2),
    "reg_2h_macd": [round(x, 3) for x in calc_macd(df2h_reg["Close"])],
    "reg_2h_ema9": round(float(df2h_reg["Close"].ewm(span=9, adjust=False).mean().iloc[-1]), 2),
}

# Nov 5 regular session VWAP from 1m data
soxl_1m = yf.Ticker("SOXL").history(period="5d", interval="1m", prepost=True)
soxl_1m.index = soxl_1m.index.tz_convert("Asia/Seoul")
nov5_reg_1m = soxl_1m[(soxl_1m.index >= "2026-11-05 23:30:00+09:00") & (soxl_1m.index < "2026-11-06 06:00:00+09:00")]
nov5_ah_1m = soxl_1m[(soxl_1m.index >= "2026-11-06 06:00:00+09:00") & (soxl_1m.index < "2026-11-06 10:00:00+09:00")]
tp_reg = (nov5_reg_1m["High"] + nov5_reg_1m["Low"] + nov5_reg_1m["Close"]) / 3.0
vwap_reg = float((tp_reg * nov5_reg_1m["Volume"]).sum() / nov5_reg_1m["Volume"].sum())
tp_ah = (nov5_ah_1m["High"] + nov5_ah_1m["Low"] + nov5_ah_1m["Close"]) / 3.0
vwap_ah = float((tp_ah * nov5_ah_1m["Volume"]).sum() / nov5_ah_1m["Volume"].sum()) if nov5_ah_1m["Volume"].sum() > 0 else float(tp_ah.mean())
intraday_stats["nov5_reg_vwap"] = round(vwap_reg, 2)
intraday_stats["nov5_ah_vwap"] = round(vwap_ah, 2)
intraday_stats["nov5_ah_volume"] = int(nov5_ah_1m["Volume"].sum())

print("=== Intraday & VWAP Stats ===")
print(json.dumps(intraday_stats, indent=2))

# 2. Compute exact iNAV of SOXL at 09:59 KST ($43.59) and 10:42 KST using:
# (a) Official SOXX close ($131.90) -> AH ($133.98)
# (b) Official SMH close ($447.73) -> AH ($454.66)
# (c) Top 13 ICE Semiconductor Index modified market-cap weights proxy
with open(f"{out_dir}/ticker_info_exact.json") as f:
    exact = json.load(f)

ice_weights = {
    "AVGO": 0.085, "NVDA": 0.085, "AMD": 0.080, "MU": 0.075, "QCOM": 0.070,
    "AMAT": 0.045, "LRCX": 0.045, "TSM": 0.045, "ASML": 0.045, "KLAC": 0.045,
    "INTC": 0.040, "MRVL": 0.040, "MCHP": 0.035
}
w_sum = sum(ice_weights.values())
basket_ah_ret = sum((exact[k]["post_chg_pct"] / 100.0) * (w / w_sum) for k, w in ice_weights.items() if exact.get(k, {}).get("post_chg_pct") is not None)

soxx_ah_ret = exact["SOXX"]["post_chg_pct"] / 100.0  # +1.577%
smh_ah_ret = exact["SMH"]["post_chg_pct"] / 100.0    # +1.548%
soxl_reg = 40.87
soxl_ah = 43.5901

inav_soxx = soxl_reg * (1.0 + 3.0 * soxx_ah_ret)
inav_smh = soxl_reg * (1.0 + 3.0 * smh_ah_ret)
inav_basket = soxl_reg * (1.0 + 3.0 * basket_ah_ret)

# Also account for NQ=F move from 09:59 KST (26874.75) to 10:42 KST (26952.75) -> +0.2902%!
# Typical SOXX beta to NQ=F overnight is ~1.35 -> 3x SOXL beta ~4.0 -> +0.2902% * 4.0 = +1.16% on top of 09:59 iNAV!
nq_post_move = 26952.75 / 26874.75 - 1.0
inav_1042_est = inav_basket * (1.0 + 3.8 * nq_post_move)

inav_summary = {
    "soxl_reg_close": soxl_reg,
    "soxl_base_0959": round(soxl_ah, 2),
    "soxl_ah_chg_pct": round((soxl_ah / soxl_reg - 1) * 100, 2),
    "soxx_ah_chg_pct": round(soxx_ah_ret * 100, 2),
    "inav_from_soxx_official": round(inav_soxx, 2),
    "prem_vs_soxx_official_pct": round((soxl_ah / inav_soxx - 1) * 100, 2),
    "smh_ah_chg_pct": round(smh_ah_ret * 100, 2),
    "inav_from_smh": round(inav_smh, 2),
    "basket_13_ah_chg_pct": round(basket_ah_ret * 100, 2),
    "inav_from_basket_0959": round(inav_basket, 2),
    "prem_vs_basket_0959_pct": round((soxl_ah / inav_basket - 1) * 100, 2),
    "nq_0959_to_1042_chg_pct": round(nq_post_move * 100, 2),
    "inav_at_1042_with_nq": round(inav_1042_est, 2),
    "prem_at_1042_with_nq_pct": round((soxl_ah / inav_1042_est - 1) * 100, 2),
}
print("\n=== iNAV & Extended-Hours Dislocation Summary ===")
print(json.dumps(inav_summary, indent=2))

# 3. Summarize N=16 episodes (reg <= -10% & ah >= +2%) from forecast_backtest_all.json
with open(f"{out_dir}/forecast_backtest_all.json") as f:
    bt = json.load(f)
eps = pd.DataFrame(bt["episodes_crash_plus_ah_bounce"])
print("\n=== Summary of N=16 Episodes (Reg <= -10% & AH >= +2%) ===")
print("N:", len(eps))
print("AH->Open win%:", round((eps["ah_to_open_pct"] > 0).mean() * 100, 1), "med:", round(eps["ah_to_open_pct"].median(), 2))
print("AH->AH 24h win%:", round((eps["ret_24h_ahah_pct"] > 0).mean() * 100, 1), "mean:", round(eps["ret_24h_ahah_pct"].mean(), 2), "med:", round(eps["ret_24h_ahah_pct"].median(), 2))
print("vs RegClose win%:", round((eps["ret_vs_reg_close_pct"] > 0).mean() * 100, 1), "mean:", round(eps["ret_vs_reg_close_pct"].mean(), 2), "med:", round(eps["ret_vs_reg_close_pct"].median(), 2))

# Check latest post-10:42 KST prices right now (~10:52 KST)
now_kst_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
nq_now = yf.Ticker("NQ=F").history(period="1d", interval="1m", prepost=True)
es_now = yf.Ticker("ES=F").history(period="1d", interval="1m", prepost=True)
krw_now = yf.Ticker("KRW=X").history(period="1d", interval="1m", prepost=True)
headers = {"User-Agent": "Mozilla/5.0"}
kospi_now = json.loads(urllib.request.urlopen(urllib.request.Request("https://m.stock.naver.com/api/index/KOSPI/basic", headers=headers), timeout=8).read().decode("utf-8"))
sam_now = json.loads(urllib.request.urlopen(urllib.request.Request("https://m.stock.naver.com/api/stock/005930/basic", headers=headers), timeout=8).read().decode("utf-8"))
hyn_now = json.loads(urllib.request.urlopen(urllib.request.Request("https://m.stock.naver.com/api/stock/000660/basic", headers=headers), timeout=8).read().decode("utf-8"))

post_check = {
    "checked_at_kst": now_kst_str,
    "nq_f": round(float(nq_now["Close"].iloc[-1]), 2) if not nq_now.empty else None,
    "es_f": round(float(es_now["Close"].iloc[-1]), 2) if not es_now.empty else None,
    "krw_x": round(float(krw_now["Close"].iloc[-1]), 2) if not krw_now.empty else None,
    "kospi": kospi_now.get("closePrice"),
    "kospi_pct": kospi_now.get("fluctuationsRatio"),
    "samsung": sam_now.get("closePrice"),
    "samsung_pct": sam_now.get("fluctuationsRatio"),
    "skhynix": hyn_now.get("closePrice"),
    "skhynix_pct": hyn_now.get("fluctuationsRatio"),
}
print("\n=== Post-10:42 KST Additional Check ===")
print(json.dumps(post_check, indent=2, ensure_ascii=False))

with open(f"{out_dir}/forecast_intraday_inav.json", "w", encoding="utf-8") as f:
    json.dump({"intraday": intraday_stats, "inav": inav_summary, "post_check": post_check}, f, ensure_ascii=False, indent=2)
