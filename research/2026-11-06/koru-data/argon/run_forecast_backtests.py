#!/usr/bin/env python3
"""
Comprehensive quantitative analysis & backtest script for KORU 24h forecast (2026-11-06 10:42 KST).
Computes:
1. Exact daily closes, rollover check, technical indicators (Rule A, Rule E, RSI2, BB, ATR, ADX).
2. Multi-anchor iNAV & EWY/KORU after-market microstructure divergence (09:00~10:00 KST & 10:42 KST).
3. Full-history (2013~2026) & 10-year (2016~2026) conditional daily backtests:
   - Extreme crash days (KORU <= -15%, <= -20%, <= -25%) complete table + stats
   - Rule A, Rule E, RSI(2)<5, %B<0, 2-day crash, VIX>=25
   - Lesson 3 test: EWY forward discount vs non-discount on crash days
   - Lesson 1 test: Next-day KOSPI holding vs breaching EWY pre-discounted fair value
   - Friday effect & NFP (first Friday of month) effect
   - 2026 intraday SOX->KORU beta (Lesson 2)
4. 2-year 1h extended-hours (prepost=True) exact 20:00 EST -> next-day 20:00 EST backtests,
   including KORU vs 3x EWY after-market lag arbitrage and Friday 16:00->20:00 EST drift.
"""
import json
import datetime as dt
import urllib.request
import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def stats_dict(s, thresh=0.0):
    s = pd.Series(s).dropna()
    n = len(s)
    if n == 0:
        return {"N": 0}
    return {
        "N": int(n),
        "up_pct": round(float((s > thresh).mean() * 100), 1),
        "mean_pct": round(float(s.mean() * 100), 2),
        "median_pct": round(float(s.median() * 100), 2),
        "q25_pct": round(float(s.quantile(0.25) * 100), 2),
        "q75_pct": round(float(s.quantile(0.75) * 100), 2),
        "p10_pct": round(float(s.quantile(0.10) * 100), 2),
        "p90_pct": round(float(s.quantile(0.90) * 100), 2),
        "min_pct": round(float(s.min() * 100), 2),
        "max_pct": round(float(s.max() * 100), 2),
    }

# 0. Check Naver intraday 1-minute chart for KOSPI & 278540 around 10:42 KST
naver_1042 = {}
for code, kind in [("KOSPI", "index"), ("278540", "stock"), ("005930", "stock"), ("000660", "stock")]:
    try:
        url = f"https://m.stock.naver.com/api/{kind}/{code}/price?pageSize=5&page=1"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            naver_1042[f"{code}_daily"] = json.loads(r.read().decode("utf-8"))[:2]
    except Exception as e:
        naver_1042[f"{code}_daily_err"] = str(e)
    try:
        # Naver intraday chart API
        url_chart = f"https://api.stock.naver.com/chart/{ 'domestic/index/' + code if kind=='index' else 'domestic/item/' + code }/day"
        req = urllib.request.Request(url_chart, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            cdata = json.loads(r.read().decode("utf-8"))
            bars = cdata.get("priceInfos", cdata if isinstance(cdata, list) else [])
            # Find bars around 09:03, 09:39, 09:59, 10:42
            picked = {}
            for b in bars:
                t = str(b.get("localDateTime", b.get("dateTime", "")))
                if any(k in t for k in ["0903", "0904", "0923", "0939", "0959", "1000", "1041", "1042", "1045"]):
                    picked[t] = b.get("currentPrice", b.get("closePrice"))
            if bars:
                picked["first"] = bars[0]
                picked["last"] = bars[-1]
                # Exact <= 20261106104200
                le_1042 = [b for b in bars if str(b.get("localDateTime", "")) <= "20261106104259"]
                if le_1042:
                    picked["at_1042"] = le_1042[-1]
                le_0959 = [b for b in bars if str(b.get("localDateTime", "")) <= "20261106095959"]
                if le_0959:
                    picked["at_0959"] = le_0959[-1]
            naver_1042[f"{code}_intraday"] = picked
    except Exception as e:
        naver_1042[f"{code}_chart_err"] = str(e)

# 1. Fetch long daily histories
syms_daily = ["KORU", "EWY", "^SOX", "SOXX", "SOXL", "MU", "NVDA", "^GSPC", "^IXIC", "^VIX", "KRW=X", "^KS11", "278540.KS"]
daily_dfs = {}
raw_tail_check = {}
for sym in syms_daily:
    df = yf.Ticker(sym).history(period="max", interval="1d", auto_adjust=False)
    raw_tail_check[sym] = df.tail(3)[["Open", "High", "Low", "Close", "Volume"]].to_dict(orient="index")
    raw_tail_check[sym] = {str(k)[:10]: v for k, v in raw_tail_check[sym].items()}
    # Use adjusted OHLC for backtesting splits cleanly
    t_obj = yf.Ticker(sym)
    df_adj = t_obj.history(period="max", interval="1d", auto_adjust=True)
    df_adj.index = pd.to_datetime(df_adj.index).tz_localize(None).normalize()
    # Yahoo Finance daily table sets 2026-11-05 Close=NaN briefly after 20:00 EST; restore from fast_info.lastPrice
    if pd.Timestamp("2026-11-05") in df_adj.index and pd.isna(df_adj.loc["2026-11-05", "Close"]):
        lp = t_obj.fast_info.get("lastPrice")
        if lp is not None and not np.isnan(lp):
            df_adj.loc["2026-11-05", "Close"] = float(lp)
    df_adj = df_adj.dropna(subset=["Close"])
    # Exclude incomplete today US row (2026-11-06) if present for US tickers
    if sym not in ["^KS11", "278540.KS", "KRW=X"]:
        df_adj = df_adj[df_adj.index <= "2026-11-05"]
    daily_dfs[sym] = df_adj

# Compute Wilder RSI, ATR, ADX on KORU & EWY (matching engine.py)
def compute_indicators(df):
    d = df.copy()
    c = d["Close"]
    h = d["High"]
    l = d["Low"]
    o = d["Open"]
    d["ret"] = c.pct_change()
    d["intraday_ret"] = c / o - 1.0
    d["overnight_ret"] = o / c.shift(1) - 1.0
    rng = (h - l).replace(0, np.nan)
    d["clv"] = (c - l) / rng
    for w in [5, 20, 50, 200]:
        d[f"sma{w}"] = c.rolling(w).mean()
    std20 = c.rolling(20).std()
    d["bb_low"] = d["sma20"] - 2 * std20
    d["bb_high"] = d["sma20"] + 2 * std20
    d["pct_b"] = (c - d["bb_low"]) / (d["bb_high"] - d["bb_low"])
    # Wilder RSI
    for period in [2, 14]:
        delta = c.diff()
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        ma_up = up.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        ma_down = down.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        rs = ma_up / ma_down.replace(0, np.nan)
        d[f"rsi{period}"] = 100 - (100 / (1 + rs))
    # Wilder ATR(14) & ADX(14)
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    d["atr_pct"] = d["atr14"] / c
    d["atr_pct_med100"] = d["atr_pct"].rolling(100).median()
    up_move = h - h.shift(1)
    down_move = l.shift(1) - l
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_di = 100 * pd.Series(plus_dm, index=d.index).ewm(alpha=1/14, adjust=False, min_periods=14).mean() / d["atr14"]
    minus_di = 100 * pd.Series(minus_dm, index=d.index).ewm(alpha=1/14, adjust=False, min_periods=14).mean() / d["atr14"]
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    d["plus_di"] = plus_di
    d["minus_di"] = minus_di
    d["adx14"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    d["rule_A"] = (d["clv"] < 0.20) & (d["atr_pct"] > d["atr_pct_med100"])
    d["rule_E"] = (d["adx14"] > 25) & (d["minus_di"] > d["plus_di"]) & (d["clv"] < 0.20)
    d["ret_2d"] = c / c.shift(2) - 1.0
    d["dow"] = d.index.dayofweek # 0=Mon, 3=Thu, 4=Fri
    return d

koru_ind = compute_indicators(daily_dfs["KORU"])
ewy_ind = compute_indicators(daily_dfs["EWY"])

latest_koru = koru_ind.loc["2026-11-05"]
latest_ewy = ewy_ind.loc["2026-11-05"]

indicators_summary = {
    "KORU_1105": {
        "open": round(float(latest_koru["Open"]), 4),
        "high": round(float(latest_koru["High"]), 4),
        "low": round(float(latest_koru["Low"]), 4),
        "close": round(float(latest_koru["Close"]), 4),
        "ret_1d_pct": round(float(latest_koru["ret"] * 100), 2),
        "ret_2d_pct": round(float(latest_koru["ret_2d"] * 100), 2),
        "clv": round(float(latest_koru["clv"]), 4),
        "rsi2": round(float(latest_koru["rsi2"]), 2),
        "rsi14": round(float(latest_koru["rsi14"]), 2),
        "adx14": round(float(latest_koru["adx14"]), 2),
        "plus_di": round(float(latest_koru["plus_di"]), 2),
        "minus_di": round(float(latest_koru["minus_di"]), 2),
        "atr14": round(float(latest_koru["atr14"]), 4),
        "atr_pct": round(float(latest_koru["atr_pct"] * 100), 2),
        "atr_pct_med100": round(float(latest_koru["atr_pct_med100"] * 100), 2),
        "sma5": round(float(latest_koru["sma5"]), 2),
        "sma20": round(float(latest_koru["sma20"]), 2),
        "sma50": round(float(latest_koru["sma50"]), 2),
        "sma200": round(float(latest_koru["sma200"]), 2),
        "dist_sma20_pct": round(float((latest_koru["Close"] / latest_koru["sma20"] - 1) * 100), 2),
        "bb_low": round(float(latest_koru["bb_low"]), 2),
        "bb_high": round(float(latest_koru["bb_high"]), 2),
        "pct_b": round(float(latest_koru["pct_b"]), 3),
        "rule_A": bool(latest_koru["rule_A"]),
        "rule_E": bool(latest_koru["rule_E"]),
    },
    "EWY_1105": {
        "close": round(float(latest_ewy["Close"]), 2),
        "ret_1d_pct": round(float(latest_ewy["ret"] * 100), 2),
        "clv": round(float(latest_ewy["clv"]), 4),
        "rsi2": round(float(latest_ewy["rsi2"]), 2),
        "rsi14": round(float(latest_ewy["rsi14"]), 2),
        "adx14": round(float(latest_ewy["adx14"]), 2),
        "plus_di": round(float(latest_ewy["plus_di"]), 2),
        "minus_di": round(float(latest_ewy["minus_di"]), 2),
        "atr14": round(float(latest_ewy["atr14"]), 2),
        "atr_pct": round(float(latest_ewy["atr_pct"] * 100), 2),
        "sma5": round(float(latest_ewy["sma5"]), 2),
        "sma20": round(float(latest_ewy["sma20"]), 2),
        "sma50": round(float(latest_ewy["sma50"]), 2),
        "sma200": round(float(latest_ewy["sma200"]), 2),
        "bb_low": round(float(latest_ewy["bb_low"]), 2),
        "bb_high": round(float(latest_ewy["bb_high"]), 2),
        "pct_b": round(float(latest_ewy["pct_b"]), 3),
    }
}

# 2. Build merged master daily dataframe for backtesting
m = koru_ind[["Open", "High", "Low", "Close", "ret", "ret_2d", "clv", "rsi2", "rsi14", "adx14", "plus_di", "minus_di", "atr_pct", "atr_pct_med100", "sma20", "sma200", "pct_b", "rule_A", "rule_E", "dow"]].copy()
m["next_ret"] = m["Close"].shift(-1) / m["Close"] - 1.0
m["next_open_ret"] = m["Open"].shift(-1) / m["Close"] - 1.0
m["next_intraday_ret"] = m["Close"].shift(-1) / m["Open"].shift(-1) - 1.0
m["next_dow"] = m["dow"].shift(-1)
# Base price today ($6.46) is -1.072% below prev regular close ($6.53)
# SoKORU_t+1 > Base_t is equivalent to next_ret > -0.01072!
BASE_REL = 6.46 / 6.53 - 1.0  # -0.01071975

m["ewy_close"] = ewy_ind["Close"]
m["ewy_ret"] = ewy_ind["ret"]
m["sox_ret"] = daily_dfs["^SOX"]["Close"].pct_change()
m["mu_ret"] = daily_dfs["MU"]["Close"].pct_change()
m["vix_close"] = daily_dfs["^VIX"]["Close"]
m["vix_ret"] = daily_dfs["^VIX"]["Close"].pct_change()
m["gspc_ret"] = daily_dfs["^GSPC"]["Close"].pct_change()

# Align Korean KOSPI & FX to compute daily EWY fair-value premium/discount
# On US date D, Korean market closed earlier on date D (15:30 KST = 01:30/02:30 ET of date D)
ks = daily_dfs["^KS11"]["Close"].reindex(m.index).ffill()
fx = daily_dfs["KRW=X"]["Close"].reindex(m.index).ffill()
kr_usd = ks / fx
# Rolling 20d ratio of EWY / kr_usd
ratio_20d = (m["ewy_close"] / kr_usd).rolling(20).median()
m["ewy_fv_ks"] = kr_usd * ratio_20d
m["ewy_prem"] = m["ewy_close"] / m["ewy_fv_ks"] - 1.0  # negative = EWY forward discount!

# Next Korean day KOSPI return (Korean date D+1, which happens BEFORE US regular session D+1!)
ks_raw = daily_dfs["^KS11"]["Close"]
ks_ret = ks_raw.pct_change()
# Map US date t -> next trading day t+1's Korean return (same calendar date as US t+1)
m["next_date"] = pd.Series(m.index, index=m.index).shift(-1)
m["next_ks_ret"] = m["next_date"].map(ks_ret)
fx_ret = daily_dfs["KRW=X"]["Close"].pct_change()
m["next_fx_ret"] = m["next_date"].map(fx_ret)
# Approximate USD-adjusted Korean return on D+1 relative to D's Korean close
m["next_kr_usd_ret"] = (1 + m["next_ks_ret"]) / (1 + m["next_fx_ret"]) - 1.0
# Excess Korean shock beyond what EWY already discounted on night D:
# EWY_D / FV_D - 1 = ewy_prem. If next_kr_usd_ret > ewy_prem, Korea fell LESS than EWY already discounted!
m["kr_minus_ewy_disc"] = m["next_kr_usd_ret"] - m["ewy_prem"]

# Filter completed rows (exclude 2026-11-05 where next_ret is NaN)
m_full = m.dropna(subset=["next_ret"]).copy()
m_10y = m_full[m_full.index >= "2016-11-06"].copy()

# First Friday of month flag for next trading day (NFP Friday)
nfp_dates = []
for (yr, mo), grp in m_full.groupby([m_full.index.year, m_full.index.month]):
    fris = grp[grp.index.dayofweek == 4]
    if len(fris) > 0:
        nfp_dates.append(fris.index[0])
nfp_set = set(nfp_dates)
m_full["next_is_nfp_fri"] = m_full["next_date"].isin(nfp_set)
m_10y["next_is_nfp_fri"] = m_10y["next_date"].isin(nfp_set)

def cond_row(df, mask, label):
    sub = df[mask]
    st_cc = stats_dict(sub["next_ret"], 0.0)
    st_base = stats_dict(sub["next_ret"], BASE_REL)
    st_open = stats_dict(sub["next_open_ret"], 0.0)
    return {
        "label": label,
        "cc": st_cc,
        "vs_base_minus_1_07pct": {
            "up_pct": st_base.get("up_pct"),
            "mean_pct": round(float(((1 + sub["next_ret"]) / (1 + BASE_REL) - 1).mean() * 100), 2) if len(sub) else None,
            "median_pct": round(float(((1 + sub["next_ret"]) / (1 + BASE_REL) - 1).median() * 100), 2) if len(sub) else None,
        },
        "next_open_median_pct": st_open.get("median_pct"),
        "next_ks_median_pct": round(float(sub["next_ks_ret"].dropna().median() * 100), 2) if len(sub["next_ks_ret"].dropna()) else None,
    }

daily_bt_10y = [
    cond_row(m_10y, pd.Series(True, index=m_10y.index), "0. 전체 거래일 (10년 기준선, 2016-11~2026-11)"),
    cond_row(m_10y, m_10y["ret"] <= -0.10, "1. KORU 당일 -10% 이하 급락일"),
    cond_row(m_10y, m_10y["ret"] <= -0.15, "2. KORU 당일 -15% 이하 폭락일"),
    cond_row(m_10y, m_10y["ret"] <= -0.20, "3. KORU 당일 -20% 이하 극단 폭락일 (현재 -37.39%)"),
    cond_row(m_10y, m_10y["rule_A"], "4. 규칙 A: 저가마감(CLV<0.20) & 고변동(ATR/C > 100d 중앙값)"),
    cond_row(m_10y, m_10y["rule_E"], "5. 규칙 E: 하락추세(ADX>25, -DI>+DI) & 저가마감(CLV<0.20)"),
    cond_row(m_10y, m_10y["rsi2"] < 5.0, "6. 일봉 RSI(2) < 5 극단 과매도 (현재 해당)"),
    cond_row(m_10y, m_10y["pct_b"] < 0.0, "7. 볼린저 밴드(20, 2σ) 하단 이탈 (%B < 0)"),
    cond_row(m_10y, (m_10y["ret"] <= -0.10) & (m_10y["ewy_prem"] <= -0.02), "8. [교훈3] KORU -10%↓ & EWY 선할인(괴리 <= -2%, 현재 -7.41%)"),
    cond_row(m_10y, (m_10y["ret"] <= -0.10) & (m_10y["ewy_prem"] > -0.02), "9. [대조군] KORU -10%↓ & EWY 비할인(괴리 > -2%)"),
    cond_row(m_10y, (m_10y["ret"] <= -0.10) & (m_10y["kr_minus_ewy_disc"] >= -0.015), "10. [교훈1·3] KORU -10%↓ & 익일 한국 낙폭이 EWY 선할인 범위 내 방어 (현재 부합)"),
    cond_row(m_10y, (m_10y["ret"] <= -0.10) & (m_10y["kr_minus_ewy_disc"] < -0.015), "11. [대조군] KORU -10%↓ & 익일 한국이 EWY 선할인보다 1.5%p+ 추가 붕괴"),
    cond_row(m_10y, (m_10y["sox_ret"] <= -0.06) & (m_10y["vix_close"] >= 25), "12. 미국 반도체 패닉 (^SOX <= -6% & VIX >= 25, 현재 -12.25% & 28.18)"),
    cond_row(m_10y, (m_10y["ret"] <= -0.08) & (m_10y["next_dow"] == 4), "13. 목요일 KORU -8%↓ 급락 후 맞이하는 금요일 미국장"),
    cond_row(m_10y, m_10y["next_is_nfp_fri"], "14. 미국 비농업 고용보고서(NFP) 발표 금요일 전체"),
    cond_row(m_10y, m_10y["next_is_nfp_fri"] & (m_10y["Close"] / m_10y["Close"].shift(4) - 1 <= -0.05), "15. 직전 5일 -5%↓ 하락 후 맞이한 NFP 발표 금요일"),
]

# Full history (2013-04 ~ 2026-11) check on extreme crashes
daily_bt_full_extremes = [
    cond_row(m_full, pd.Series(True, index=m_full.index), "전체 기간 (2013-04~2026-11)"),
    cond_row(m_full, m_full["ret"] <= -0.15, "전체 기간 KORU <= -15%"),
    cond_row(m_full, m_full["ret"] <= -0.20, "전체 기간 KORU <= -20%"),
    cond_row(m_full, m_full["ret"] <= -0.25, "전체 기간 KORU <= -25%"),
]

# Extract ALL historical instances where KORU <= -18% since inception (2013)
extreme_rows = []
sub_ext = m_full[m_full["ret"] <= -0.18].copy()
for idx, r in sub_ext.iterrows():
    extreme_rows.append({
        "date": str(idx)[:10],
        "dow": ["Mon", "Tue", "Wed", "Thu", "Fri"][int(r["dow"])],
        "koru_ret_pct": round(float(r["ret"] * 100), 2),
        "clv": round(float(r["clv"]), 3),
        "sox_ret_pct": round(float(r["sox_ret"] * 100), 2) if pd.notna(r["sox_ret"]) else None,
        "vix": round(float(r["vix_close"]), 2) if pd.notna(r["vix_close"]) else None,
        "ewy_prem_pct": round(float(r["ewy_prem"] * 100), 2) if pd.notna(r["ewy_prem"]) else None,
        "next_ks_ret_pct": round(float(r["next_ks_ret"] * 100), 2) if pd.notna(r["next_ks_ret"]) else None,
        "next_open_ret_pct": round(float(r["next_open_ret"] * 100), 2),
        "next_cc_ret_pct": round(float(r["next_ret"] * 100), 2),
        "vs_minus107_ret_pct": round(float(((1 + r["next_ret"]) / (1 + BASE_REL) - 1) * 100), 2),
    })

# Also extract recent Oct-Nov 2026 regime days where KORU <= -5%
oct_nov_rows = []
sub_rec = m[m.index >= "2026-10-01"].copy()
for idx, r in sub_rec.iterrows():
    if r["ret"] <= -0.05:
        oct_nov_rows.append({
            "date": str(idx)[:10],
            "dow": ["Mon", "Tue", "Wed", "Thu", "Fri"][int(r["dow"])],
            "koru_close": round(float(r["Close"]), 2),
            "koru_ret_pct": round(float(r["ret"] * 100), 2),
            "clv": round(float(r["clv"]), 3),
            "sox_ret_pct": round(float(r["sox_ret"] * 100), 2) if pd.notna(r["sox_ret"]) else None,
            "vix": round(float(r["vix_close"]), 2) if pd.notna(r["vix_close"]) else None,
            "ewy_prem_pct": round(float(r["ewy_prem"] * 100), 2) if pd.notna(r["ewy_prem"]) else None,
            "next_ks_ret_pct": round(float(r["next_ks_ret"] * 100), 2) if pd.notna(r["next_ks_ret"]) else None,
            "next_cc_ret_pct": round(float(r["next_ret"] * 100), 2) if pd.notna(r["next_ret"]) else None,
        })

# 3. 2-year 1h extended-hours backtest (exact 19:00-20:00 EST after-market close -> +24h)
h_koru = yf.Ticker("KORU").history(period="730d", interval="1h", prepost=True, auto_adjust=True)
h_ewy = yf.Ticker("EWY").history(period="730d", interval="1h", prepost=True, auto_adjust=True)
h_soxx = yf.Ticker("SOXX").history(period="730d", interval="1h", prepost=True, auto_adjust=True)

# Group by US trading date:
# Regular close bar is hour==15 (15:00-16:00 ET), After-market final bar is hour==19 (19:00-20:00 ET, i.e., 09:00-10:00 KST next morning)
def extract_daily_ah(hdf):
    hdf = hdf.copy()
    hdf["us_date"] = hdf.index.strftime("%Y-%m-%d")
    hdf["hour"] = hdf.index.hour
    reg = hdf[hdf["hour"] == 15].groupby("us_date")["Close"].last()
    ah_end = hdf[hdf["hour"].isin([18, 19])].groupby("us_date")["Close"].last()
    pm_open = hdf[hdf["hour"] == 9].groupby("us_date")["Open"].first()
    out = pd.DataFrame({"reg_close": reg, "ah_close": ah_end, "reg_open": pm_open})
    out.index = pd.to_datetime(out.index)
    return out

ah_k = extract_daily_ah(h_koru)
ah_e = extract_daily_ah(h_ewy)
ah_s = extract_daily_ah(h_soxx)

ah_df = ah_k.join(ah_e, lsuffix="_k", rsuffix="_e").join(ah_s.add_suffix("_s"))
ah_df["reg_ret_k"] = ah_df["reg_close_k"].pct_change()
ah_df["ah_move_k"] = ah_df["ah_close_k"] / ah_df["reg_close_k"] - 1.0
ah_df["ah_move_e"] = ah_df["ah_close_e"] / ah_df["reg_close_e"] - 1.0
ah_df["ah_move_s"] = ah_df["ah_close_s"] / ah_df["reg_close_s"] - 1.0
# Relative lag of KORU in after-market vs 3x EWY after-market move:
# Today: KORU ah_move = -1.07%, 3 * EWY ah_move = +3.37%, lag = -4.44%!
ah_df["koru_vs_3x_ewy_ah"] = ah_df["ah_move_k"] - 3.0 * ah_df["ah_move_e"]
# Next trading day (+1 trading day; note for Thu -> Fri it IS exact +24h!)
ah_df["next_date"] = pd.Series(ah_df.index, index=ah_df.index).shift(-1)
ah_df["days_diff"] = (ah_df["next_date"] - ah_df.index).dt.days
ah_df["ret_ah_to_ah"] = ah_df["ah_close_k"].shift(-1) / ah_df["ah_close_k"] - 1.0
ah_df["ret_ah_to_next_reg"] = ah_df["reg_close_k"].shift(-1) / ah_df["ah_close_k"] - 1.0
ah_df["ret_reg_to_next_ah"] = ah_df["ah_close_k"].shift(-1) / ah_df["reg_close_k"] - 1.0
ah_df["dow"] = ah_df.index.dayofweek # 3 = Thu US -> Fri US (exact 24h to weekend close!)
# Friday regular close -> Friday AH close drift (same day, dow==4)
fri_ah_drift = ah_df[ah_df["dow"] == 4]["ah_move_k"].dropna()

# Exact 24h pairs (Mon-Thu US dates where days_diff == 1, excluding weekends/holidays)
ah_24h = ah_df[(ah_df["days_diff"] == 1) & ah_df["ret_ah_to_ah"].notna()].copy()

def ah_row(df, mask, label):
    sub = df[mask]
    return {
        "label": label,
        "ah_to_ah": stats_dict(sub["ret_ah_to_ah"], 0.0),
        "reg_to_next_ah_up_pct": round(float((sub["ret_reg_to_next_ah"] > 0).mean() * 100), 1) if len(sub) else None,
        "next_open_vs_ah_median_pct": round(float((sub["reg_open_k"].shift(-1).reindex(sub.index) / sub["ah_close_k"] - 1).dropna().median() * 100), 2) if len(sub) else None,
    }

# Fix next_open_vs_ah properly on ah_df before filtering
ah_df["next_open_vs_ah"] = ah_df["reg_open_k"].shift(-1) / ah_df["ah_close_k"] - 1.0
ah_24h = ah_df[(ah_df["days_diff"] == 1) & ah_df["ret_ah_to_ah"].notna()].copy()

def ah_row_clean(df, mask, label):
    sub = df[mask]
    return {
        "label": label,
        "ah_to_ah": stats_dict(sub["ret_ah_to_ah"], 0.0),
        "reg_to_next_ah_up_pct": round(float((sub["ret_reg_to_next_ah"] > 0).mean() * 100), 1) if len(sub) else None,
        "next_open_vs_ah_median_pct": round(float(sub["next_open_vs_ah"].dropna().median() * 100), 2) if len(sub["next_open_vs_ah"].dropna()) else None,
    }

hourly_bt_2y = [
    ah_row_clean(ah_24h, pd.Series(True, index=ah_24h.index), "0. 2년 전체 24h (미 애프터 마감 20:00 ET → 익일 20:00 ET)"),
    ah_row_clean(ah_24h, ah_24h["dow"] == 3, "1. 목요일 애프터 마감 → 금요일 애프터 마감 (주말 직전 24h, 현재 동일 요일)"),
    ah_row_clean(ah_24h, ah_24h["reg_ret_k"] <= -0.05, "2. 직전 정규장 KORU -5%↓ 급락일 이후 24h"),
    ah_row_clean(ah_24h, ah_24h["reg_ret_k"] <= -0.10, "3. 직전 정규장 KORU -10%↓ 폭락일 이후 24h"),
    ah_row_clean(ah_24h, ah_24h["koru_vs_3x_ewy_ah"] <= -0.015, "4. 애프터 마감 시 KORU가 3×EWY 대비 -1.5%p↓ 저평가 괴리 (현재 -4.44%p)"),
    ah_row_clean(ah_24h, ah_24h["koru_vs_3x_ewy_ah"] <= -0.030, "5. 애프터 마감 시 KORU가 3×EWY 대비 -3.0%p↓ 심화 저평가 (현재 -4.44%p)"),
    ah_row_clean(ah_24h, (ah_24h["ah_move_e"] >= 0.005) & (ah_24h["ah_move_k"] <= 0.0), "6. 애프터 EWY +0.5%↑ 반등했는데 KORU 보합/하락 역행 마감 (현재 EWY +1.12% vs KORU -1.07%)"),
    ah_row_clean(ah_24h, (ah_24h["reg_ret_k"] <= -0.04) & (ah_24h["ah_move_s"] >= 0.01), "7. 정규장 KORU -4%↓ 급락 후 애프터 SOXX +1.0%↑ 반등 (현재 SOXX +1.58%)"),
]

fri_ah_stats = stats_dict(fri_ah_drift, 0.0)
fri_ah_abs_median = round(float(fri_ah_drift.abs().median() * 100), 2)

# 4. Minute-by-minute check of 2026-11-06 08:00~10:00 KST KORU vs EWY vs SOXX
k1m = pd.read_csv(f"{OUT_DIR}/forecast_KORU_intraday.csv", index_col=0, parse_dates=True)
e1m = pd.read_csv(f"{OUT_DIR}/forecast_EWY_intraday.csv", index_col=0, parse_dates=True)
s1m = pd.read_csv(f"{OUT_DIR}/forecast_SOXX_intraday.csv", index_col=0, parse_dates=True)
m1m = pd.read_csv(f"{OUT_DIR}/forecast_MU_intraday.csv", index_col=0, parse_dates=True)
es1m = pd.read_csv(f"{OUT_DIR}/forecast_ESF_intraday.csv", index_col=0, parse_dates=True)
nq1m = pd.read_csv(f"{OUT_DIR}/forecast_NQF_intraday.csv", index_col=0, parse_dates=True)

def bar_at(df, ts_str):
    sub = df[df.index <= ts_str]
    if sub.empty:
        return None
    return {"ts": str(sub.index[-1]), "close": round(float(sub["Close"].iloc[-1]), 4)}

key_timestamps = [
    "2026-11-06 06:00:00+09:00",
    "2026-11-06 08:19:00+09:00",
    "2026-11-06 09:03:00+09:00",
    "2026-11-06 09:25:00+09:00",
    "2026-11-06 09:39:00+09:00",
    "2026-11-06 09:55:00+09:00",
    "2026-11-06 09:59:00+09:00",
    "2026-11-06 10:42:00+09:00",
]
intraday_trace = {}
for ts in key_timestamps:
    intraday_trace[ts] = {
        "KORU": bar_at(k1m, ts),
        "EWY": bar_at(e1m, ts),
        "SOXX": bar_at(s1m, ts),
        "MU": bar_at(m1m, ts),
        "ES=F": bar_at(es1m, ts),
        "NQ=F": bar_at(nq1m, ts),
    }

out = {
    "raw_tail_check": raw_tail_check,
    "naver_1042": naver_1042,
    "indicators_summary": indicators_summary,
    "daily_bt_10y": daily_bt_10y,
    "daily_bt_full_extremes": daily_bt_full_extremes,
    "extreme_rows_le_minus18": extreme_rows,
    "oct_nov_2026_rows": oct_nov_rows,
    "hourly_bt_2y": hourly_bt_2y,
    "fri_ah_drift_stats": {"stats": fri_ah_stats, "abs_median_pct": fri_ah_abs_median},
    "intraday_trace": intraday_trace,
}

with open(f"{OUT_DIR}/forecast_quant_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("Saved forecast_quant_results.json successfully.")
