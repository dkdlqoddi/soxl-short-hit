import json
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

out_dir = "research/2026-11-06/soxl-data/argon"

# 1. Load full SOXL, SOXX, VIX, SPY, QQQ daily history and ensure 2026-11-05 official close is included accurately
print("Downloading full daily histories...")
soxl_d = yf.Ticker("SOXL").history(period="max", interval="1d", auto_adjust=False)
soxx_d = yf.Ticker("SOXX").history(period="max", interval="1d", auto_adjust=False)
vix_d = yf.Ticker("^VIX").history(period="max", interval="1d", auto_adjust=False)
spy_d = yf.Ticker("SPY").history(period="max", interval="1d", auto_adjust=False)

for df in [soxl_d, soxx_d, vix_d, spy_d]:
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    df.index = df.index.normalize()

# Fix 2026-11-05 row if Close is NaN using verified official regular close from Ticker.info / daily_summary.json
nov5 = pd.Timestamp("2026-11-05")
if nov5 in soxl_d.index and pd.isna(soxl_d.loc[nov5, "Close"]):
    soxl_d.loc[nov5, "Open"] = 56.95
    soxl_d.loc[nov5, "High"] = 57.84
    soxl_d.loc[nov5, "Low"] = 40.5901
    soxl_d.loc[nov5, "Close"] = 40.87
    soxl_d.loc[nov5, "Volume"] = 519607244
elif nov5 not in soxl_d.index:
    soxl_d.loc[nov5] = [56.95, 57.84, 40.5901, 40.87, 40.87, 519607244, 0.0, 0.0]

# Note: check SOXL historical splits in auto_adjust=False vs auto_adjust=True!
soxl_adj = yf.Ticker("SOXL").history(period="max", interval="1d", auto_adjust=True)
soxl_adj.index = soxl_adj.index.tz_convert("America/New_York").tz_localize(None).normalize()
if nov5 in soxl_adj.index and pd.isna(soxl_adj.loc[nov5, "Close"]):
    soxl_adj.loc[nov5, ["Open", "High", "Low", "Close", "Volume"]] = [56.95, 57.84, 40.5901, 40.87, 519607244]
elif nov5 not in soxl_adj.index:
    soxl_adj.loc[nov5, ["Open", "High", "Low", "Close", "Volume"]] = [56.95, 57.84, 40.5901, 40.87, 519607244]

# Check SOXX split adjustment! On 2026-11-05 SOXX split 3-for-1. Let's inspect recent rows of soxx_adj
soxx_adj = yf.Ticker("SOXX").history(period="max", interval="1d", auto_adjust=True)
soxx_adj.index = soxx_adj.index.tz_convert("America/New_York").tz_localize(None).normalize()
if nov5 in soxx_adj.index and pd.isna(soxx_adj.loc[nov5, "Close"]):
    soxx_adj.loc[nov5, ["Open", "High", "Low", "Close", "Volume"]] = [143.08, 143.7255, 130.75, 131.90, 65770030]
print("SOXX adj last 6 rows before fix:\n", soxx_adj[["Open", "High", "Low", "Close"]].tail(6))
# If any row before 2026-11-05 has Close > 300 while 2026-11-05 is ~131.90, divide pre-2026-11-05 unsplit rows by 3!
pre_nov5 = soxx_adj.index < nov5
unsplit_mask = pre_nov5 & (soxx_adj["Close"] > 280)
if unsplit_mask.any():
    print(f"Fixing {unsplit_mask.sum()} unadjusted SOXX rows for 3:1 split...")
    soxx_adj.loc[unsplit_mask, ["Open", "High", "Low", "Close"]] /= 3.0
print("SOXX adj last 6 rows after fix:\n", soxx_adj[["Open", "High", "Low", "Close"]].tail(6))

spy_adj = yf.Ticker("SPY").history(period="max", interval="1d", auto_adjust=True)
spy_adj.index = spy_adj.index.tz_convert("America/New_York").tz_localize(None).normalize()
if nov5 in spy_adj.index and pd.isna(spy_adj.loc[nov5, "Close"]):
    spy_adj.loc[nov5, ["Open", "High", "Low", "Close", "Volume"]] = [758.0, 759.5, 732.5, 733.00, 90000000]

vix_clean = vix_d[["Open", "High", "Low", "Close"]].copy()
if nov5 in vix_clean.index and pd.isna(vix_clean.loc[nov5, "Close"]):
    vix_clean.loc[nov5, ["Open", "High", "Low", "Close"]] = [17.14, 28.36, 16.70, 28.18]

# Remove any rows after 2026-11-05 (e.g., partial 11-06 row if any)
df = soxl_adj[soxl_adj.index <= nov5].copy()
df = df.dropna(subset=["Open", "High", "Low", "Close"])
print(f"SOXL daily rows: {len(df)}, start={df.index[0].strftime('%Y-%m-%d')}, end={df.index[-1].strftime('%Y-%m-%d')}")
print("Last 6 SOXL daily rows:\n", df[["Open", "High", "Low", "Close", "Volume"]].tail(6))

# 2. Compute exact technical indicators matching engine.py!
# Let's check engine.py formulas if present
c = df["Close"]
o = df["Open"]
h = df["High"]
l = df["Low"]
v = df["Volume"]

df["ret"] = c.pct_change()
df["ret_2d"] = c / c.shift(2) - 1.0
df["ret_3d"] = c / c.shift(3) - 1.0
df["ret_5d"] = c / c.shift(5) - 1.0
df["ret_20d"] = c / c.shift(20) - 1.0
df["dd_20d"] = c / c.rolling(20).max() - 1.0
df["dd_60d"] = c / c.rolling(60).max() - 1.0
df["clv"] = (c - l) / (h - l).replace(0, np.nan)

# Wilder RSI
def calc_rsi(series, period):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))

df["rsi2"] = calc_rsi(c, 2)
df["rsi14"] = calc_rsi(c, 14)

# Moving averages & Bollinger
for p in [5, 10, 20, 50, 200]:
    df[f"sma{p}"] = c.rolling(p).mean()
bb_std = c.rolling(20).std()
df["bb_low"] = df["sma20"] - 2.0 * bb_std
df["bb_high"] = df["sma20"] + 2.0 * bb_std
df["bb_pctb"] = (c - df["bb_low"]) / (df["bb_high"] - df["bb_low"])

# ATR(14) & ADX(14) Wilder
prev_c = c.shift(1)
tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
df["atr14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
df["atrp"] = df["atr14"] / c
df["atrp_med100"] = df["atrp"].rolling(100).median()

up_move = h - h.shift(1)
down_move = l.shift(1) - l
plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
atr_w = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
plus_di = 100.0 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_w
minus_di = 100.0 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_w
dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
df["adx14"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
df["plus_di"] = plus_di
df["minus_di"] = minus_di

# Stochastic(14,3)
low14 = l.rolling(14).min()
high14 = h.rolling(14).max()
df["stoch_k"] = 100.0 * (c - low14) / (high14 - low14).replace(0, np.nan)
df["vol_ratio20"] = v / v.rolling(20).mean()

# Join VIX & SOXX
df["vix_close"] = vix_clean["Close"].reindex(df.index)
df["vix_chg"] = df["vix_close"].pct_change()
df["soxx_close"] = soxx_adj["Close"].reindex(df.index)
df["soxx_ret"] = df["soxx_close"].pct_change()
df["soxx_sma50"] = df["soxx_close"].rolling(50).mean()
df["soxx_sma200"] = df["soxx_close"].rolling(200).mean()
df["dow"] = df.index.dayofweek  # 0=Mon, 3=Thu, 4=Fri

# Next-day targets (from day t close to day t+1 open / close)
df["next_co"] = o.shift(-1) / c - 1.0   # Overnight Close_t -> Open_{t+1}
df["next_cc"] = c.shift(-1) / c - 1.0   # Close_t -> Close_{t+1}
df["next_oc"] = c.shift(-1) / o.shift(-1) - 1.0  # Intraday on day t+1
df["next_dow"] = df["dow"].shift(-1)
# First Friday of month flag for day t+1 (approximate NFP day!)
next_dates = pd.Series(df.index, index=df.index).shift(-1)
df["next_is_nfp_fri"] = next_dates.apply(lambda d: (d.dayofweek == 4 and 1 <= d.day <= 7) if pd.notna(d) else False)

# Print 2026-11-05 exact indicator snapshot!
today_row = df.loc[nov5]
ind_snap = {
    "close": float(today_row["Close"]),
    "open": float(today_row["Open"]),
    "high": float(today_row["High"]),
    "low": float(today_row["Low"]),
    "ret_1d_pct": round(float(today_row["ret"] * 100), 2),
    "ret_2d_pct": round(float(today_row["ret_2d"] * 100), 2),
    "ret_5d_pct": round(float(today_row["ret_5d"] * 100), 2),
    "ret_20d_pct": round(float(today_row["ret_20d"] * 100), 2),
    "dd_20d_pct": round(float(today_row["dd_20d"] * 100), 2),
    "dd_60d_pct": round(float(today_row["dd_60d"] * 100), 2),
    "clv": round(float(today_row["clv"]), 4),
    "rsi2": round(float(today_row["rsi2"]), 2),
    "rsi14": round(float(today_row["rsi14"]), 2),
    "sma5": round(float(today_row["sma5"]), 2),
    "sma10": round(float(today_row["sma10"]), 2),
    "sma20": round(float(today_row["sma20"]), 2),
    "sma50": round(float(today_row["sma50"]), 2),
    "sma200": round(float(today_row["sma200"]), 2),
    "bb_low": round(float(today_row["bb_low"]), 2),
    "bb_high": round(float(today_row["bb_high"]), 2),
    "bb_pctb": round(float(today_row["bb_pctb"]), 4),
    "atr14": round(float(today_row["atr14"]), 2),
    "atrp_pct": round(float(today_row["atrp"] * 100), 2),
    "atrp_med100_pct": round(float(today_row["atrp_med100"] * 100), 2),
    "adx14": round(float(today_row["adx14"]), 2),
    "plus_di": round(float(today_row["plus_di"]), 2),
    "minus_di": round(float(today_row["minus_di"]), 2),
    "stoch_k": round(float(today_row["stoch_k"]), 2),
    "vol_ratio20": round(float(today_row["vol_ratio20"]), 2),
    "vix_close": round(float(today_row["vix_close"]), 2),
    "vix_chg_pct": round(float(today_row["vix_chg"] * 100), 2),
    "soxx_close": round(float(today_row["soxx_close"]), 2),
    "soxx_ret_pct": round(float(today_row["soxx_ret"] * 100), 2),
    "soxx_sma50": round(float(today_row["soxx_sma50"]), 2),
    "soxx_sma200": round(float(today_row["soxx_sma200"]), 2),
}
print("\n=== 2026-11-05 Exact Technical Indicators ===")
print(json.dumps(ind_snap, indent=2))

# Rank of 2026-11-05 daily drop (-38.71%) in entire SOXL history!
worst_days = df.sort_values("ret").head(15)
print("\n=== Top 15 Worst Single-Day Drops in SOXL History (2010-03 ~ 2026-11-05) ===")
worst_list = []
for dt, r in worst_days.iterrows():
    rec = {
        "date": dt.strftime("%Y-%m-%d"),
        "dow": dt.strftime("%a"),
        "close": round(float(r["Close"]), 2),
        "ret_pct": round(float(r["ret"] * 100), 2),
        "clv": round(float(r["clv"]), 3),
        "vix": round(float(r["vix_close"]), 2) if pd.notna(r["vix_close"]) else None,
        "next_co_pct": round(float(r["next_co"] * 100), 2) if pd.notna(r["next_co"]) else None,
        "next_cc_pct": round(float(r["next_cc"] * 100), 2) if pd.notna(r["next_cc"]) else None,
        "beats_ah_666": bool(r["next_cc"] > 0.066555) if pd.notna(r["next_cc"]) else None,
    }
    worst_list.append(rec)
    print(rec)

# Helper to summarize condition on historical rows (excluding 2026-11-05 where next_cc is NaN)
hist_full = df.dropna(subset=["next_cc", "next_co"]).copy()
hist_10y = hist_full[hist_full.index >= "2016-11-06"].copy()

ah_hurdle = 43.5901 / 40.87 - 1.0  # +0.0665549 (+6.66%)

def summarize_cond(sub, label):
    n = len(sub)
    if n == 0:
        return {"label": label, "N": 0}
    cc = sub["next_cc"] * 100.0
    co = sub["next_co"] * 100.0
    vs_ah = ((1.0 + sub["next_cc"]) / (1.0 + ah_hurdle) - 1.0) * 100.0
    res = {
        "label": label,
        "N": int(n),
        "co_win_pct": round(float((co > 0).mean() * 100), 1),
        "co_med_pct": round(float(co.median()), 2),
        "cc_win_pct": round(float((cc > 0).mean() * 100), 1),
        "cc_mean_pct": round(float(cc.mean()), 2),
        "cc_med_pct": round(float(cc.median()), 2),
        "cc_q25_pct": round(float(cc.quantile(0.25)), 2),
        "cc_q75_pct": round(float(cc.quantile(0.75)), 2),
        "cc_p10_pct": round(float(cc.quantile(0.10)), 2),
        "cc_p90_pct": round(float(cc.quantile(0.90)), 2),
        "vs_ah666_win_pct": round(float((vs_ah > 0).mean() * 100), 1),
        "vs_ah666_mean_pct": round(float(vs_ah.mean()), 2),
        "vs_ah666_med_pct": round(float(vs_ah.median()), 2),
        "vs_ah666_q25_pct": round(float(vs_ah.quantile(0.25)), 2),
        "vs_ah666_q75_pct": round(float(vs_ah.quantile(0.75)), 2),
    }
    return res

print("\n=== 16.6-Year Full History Conditional Backtests (2010-03 ~ 2026-11-04, N=4190) ===")
conds_full = [
    ("0. 전체 거래일 기준선 (2010~2026)", hist_full),
    ("1. 당일 -10% 이하 급락 (ret <= -10%)", hist_full[hist_full["ret"] <= -0.10]),
    ("2. 당일 -15% 이하 폭락 (ret <= -15%)", hist_full[hist_full["ret"] <= -0.15]),
    ("3. 당일 -20% 이하 대폭락 (ret <= -20%)", hist_full[hist_full["ret"] <= -0.20]),
    ("4. 당일 -25% 이하 패닉 투매 (ret <= -25%)", hist_full[hist_full["ret"] <= -0.25]),
    ("5. 규칙 A (CLV < 0.20 & ATR/C > 100d 중앙값)", hist_full[(hist_full["clv"] < 0.20) & (hist_full["atrp"] > hist_full["atrp_med100"])]),
    ("6. 규칙 E (ADX > 25 하락추세 & CLV < 0.20)", hist_full[(hist_full["adx14"] > 25) & (hist_full["minus_di"] > hist_full["plus_di"]) & (hist_full["clv"] < 0.20)]),
    ("7. 극단 약세마감 & 폭락 (ret <= -12% & CLV < 0.10)", hist_full[(hist_full["ret"] <= -0.12) & (hist_full["clv"] < 0.10)]),
    ("8. 극단 과매도 교집합 (RSI2 < 5 & 종가 < 볼린저하단)", hist_full[(hist_full["rsi2"] < 5) & (hist_full["Close"] < hist_full["bb_low"])]),
    ("9. 200일선 아래 & 당일 -12%↓ 폭락 (조정·약세장 급락)", hist_full[(hist_full["Close"] < hist_full["sma200"]) & (hist_full["ret"] <= -0.12)]),
    ("10. 초고변동(ATR/C >= 20%) & 당일 -12%↓ 폭락", hist_full[(hist_full["atrp"] >= 0.20) & (hist_full["ret"] <= -0.12)]),
    ("11. VIX >= 25 & 당일 VIX +25%↑ 폭등일 (현재 VIX 28.18, +69.7%)", hist_full[(hist_full["vix_close"] >= 25) & (hist_full["vix_chg"] >= 0.25)]),
    ("12. 목요일 급락(ret <= -8%) → 금요일 마감 (주말 리스크 회피 점검)", hist_full[(hist_full["dow"] == 3) & (hist_full["ret"] <= -0.08)]),
    ("13. 비농업고용(NFP, 매월 첫 금요일) 당일 전체", hist_full[hist_full["next_is_nfp_fri"]]),
    ("14. NFP 전일(목요일) SOXL 하락 마감 후 → NFP 금요일", hist_full[hist_full["next_is_nfp_fri"] & (hist_full["ret"] < -0.03)]),
]
res_full = []
for lbl, sub in conds_full:
    r = summarize_cond(sub, lbl)
    res_full.append(r)
    print(f"{lbl:55s} | N={r['N']:4d} | CC win={r.get('cc_win_pct')}% med={r.get('cc_med_pct')}% mean={r.get('cc_mean_pct')}% | vs +6.66% AH win={r.get('vs_ah666_win_pct')}% med={r.get('vs_ah666_med_pct')}% (Q25~Q75: {r.get('vs_ah666_q25_pct')}~{r.get('vs_ah666_q75_pct')}%)")

print("\n=== 10-Year Conditional Backtests (2016-11 ~ 2026-11-04, N=2514) ===")
conds_10y = [
    ("10Y-0. 전체 거래일 (10년 기준선)", hist_10y),
    ("10Y-1. 규칙 A (CLV < 0.20 & ATRhi)", hist_10y[(hist_10y["clv"] < 0.20) & (hist_10y["atrp"] > hist_10y["atrp_med100"])]),
    ("10Y-2. 규칙 E (ADX > 25 하락 & CLV < 0.20)", hist_10y[(hist_10y["adx14"] > 25) & (hist_10y["minus_di"] > hist_10y["plus_di"]) & (hist_10y["clv"] < 0.20)]),
    ("10Y-3. 당일 -12%↓ & CLV < 0.15", hist_10y[(hist_10y["ret"] <= -0.12) & (hist_10y["clv"] < 0.15)]),
    ("10Y-4. 당일 -15%↓ 폭락", hist_10y[hist_10y["ret"] <= -0.15]),
    ("10Y-5. 당일 -20%↓ 대폭락", hist_10y[hist_10y["ret"] <= -0.20]),
    ("10Y-6. RSI(2) < 5 & 볼린저 하단 이탈", hist_10y[(hist_10y["rsi2"] < 5) & (hist_10y["Close"] < hist_10y["bb_low"])]),
    ("10Y-7. VIX >= 25 & VIX 당일 +25%↑ 폭등", hist_10y[(hist_10y["vix_close"] >= 25) & (hist_10y["vix_chg"] >= 0.25)]),
    ("10Y-8. 목요일 -8%↓ 급락 → 금요일 마감", hist_10y[(hist_10y["dow"] == 3) & (hist_10y["ret"] <= -0.08)]),
]
res_10y = []
for lbl, sub in conds_10y:
    r = summarize_cond(sub, lbl)
    res_10y.append(r)
    print(f"{lbl:45s} | N={r['N']:4d} | CC win={r.get('cc_win_pct')}% med={r.get('cc_med_pct')}% | vs +6.66% AH win={r.get('vs_ah666_win_pct')}% med={r.get('vs_ah666_med_pct')}%")

# 3. 2-Year (730d) Extended-Hours 1h Backtest: Exact AH Close (19:00~20:00 ET) -> Next Day AH Close (19:00~20:00 ET)!
print("\nDownloading 730d 1h extended-hours SOXL data...")
h1 = yf.Ticker("SOXL").history(period="730d", interval="1h", prepost=True)
h1.index = h1.index.tz_convert("America/New_York")

# Group by ET calendar date to extract:
# - Regular Open (09:30 bar Open), Regular High/Low (09:30..15:30), Regular Close (15:30 bar Close)
# - After-hours Low/High (16:00..19:00), After-hours final Close (last bar between 16:00 and 19:59 ET)
daily_ext = []
for d_et, grp in h1.groupby(h1.index.date):
    reg = grp[(grp.index.hour >= 9) & (grp.index.hour <= 15)]
    # Note: yfinance 1h regular bars have timestamps 09:30, 10:30, ..., 15:30!
    reg = grp[(grp.index.time >= pd.Timestamp("09:30").time()) & (grp.index.time <= pd.Timestamp("15:30").time())]
    ah = grp[(grp.index.time >= pd.Timestamp("16:00").time()) & (grp.index.time <= pd.Timestamp("19:59").time())]
    if reg.empty or ah.empty:
        continue
    daily_ext.append({
        "date": pd.Timestamp(d_et),
        "reg_open": float(reg["Open"].iloc[0]),
        "reg_high": float(reg["High"].max()),
        "reg_low": float(reg["Low"].min()),
        "reg_close_1h": float(reg["Close"].iloc[-1]),
        "ah_high": float(ah["High"].max()),
        "ah_low": float(ah["Low"].min()),
        "ah_close": float(ah["Close"].iloc[-1]),
    })
ext_df = pd.DataFrame(daily_ext).set_index("date")
# Align official daily close where available
ext_df["reg_close"] = df["Close"].reindex(ext_df.index).fillna(ext_df["reg_close_1h"])
ext_df["reg_ret"] = ext_df["reg_close"].pct_change()
ext_df["clv"] = df["clv"].reindex(ext_df.index)
ext_df["ah_ret"] = ext_df["ah_close"] / ext_df["reg_close"] - 1.0  # Day t AH bounce vs Day t reg close!
ext_df["next_reg_open"] = ext_df["reg_open"].shift(-1)
ext_df["next_reg_close"] = ext_df["reg_close"].shift(-1)
ext_df["next_ah_close"] = ext_df["ah_close"].shift(-1)
ext_df["dow"] = ext_df.index.dayofweek

# 24h exact horizon: AH_close_t -> AH_close_{t+1}!
ext_df["ret_24h_ahah"] = ext_df["next_ah_close"] / ext_df["ah_close"] - 1.0
# Also vs Day t reg close: AH_close_{t+1} / Reg_close_t - 1.0!
ext_df["ret_reg_to_next_ah"] = ext_df["next_ah_close"] / ext_df["reg_close"] - 1.0
# Also AH_close_t -> Next Reg Open (premarket/open fade test!)
ext_df["ret_ah_to_next_open"] = ext_df["next_reg_open"] / ext_df["ah_close"] - 1.0

print("Last 5 rows of 730d extended-hours table:\n", ext_df[["reg_close", "reg_ret", "ah_close", "ah_ret", "ret_24h_ahah"]].tail(5))

ext_hist = ext_df.dropna(subset=["ret_24h_ahah", "reg_ret", "ah_ret"]).copy()
print(f"\n=== 2-Year Extended-Hours Exact Horizon Backtests (AH_close_t -> AH_close_{{t+1}}, N={len(ext_hist)}) ===")

def sum_ext(sub, lbl):
    n = len(sub)
    if n == 0:
        return {"label": lbl, "N": 0}
    r24 = sub["ret_24h_ahah"] * 100.0
    r_prev = sub["ret_reg_to_next_ah"] * 100.0
    r_open = sub["ret_ah_to_next_open"] * 100.0
    return {
        "label": lbl,
        "N": int(n),
        "ahah_win_pct": round(float((r24 > 0).mean() * 100), 1),
        "ahah_mean_pct": round(float(r24.mean()), 2),
        "ahah_med_pct": round(float(r24.median()), 2),
        "ahah_q25_pct": round(float(r24.quantile(0.25)), 2),
        "ahah_q75_pct": round(float(r24.quantile(0.75)), 2),
        "ahah_p10_pct": round(float(r24.quantile(0.10)), 2),
        "ahah_p90_pct": round(float(r24.quantile(0.90)), 2),
        "to_open_win_pct": round(float((r_open > 0).mean() * 100), 1),
        "to_open_med_pct": round(float(r_open.median()), 2),
        "vs_reg_close_win_pct": round(float((r_prev > 0).mean() * 100), 1),
        "vs_reg_close_med_pct": round(float(r_prev.median()), 2),
    }

ext_conds = [
    ("2Y-0. 전체 거래일 (AH종가 → 익일 AH종가)", ext_hist),
    ("2Y-1. 정규장 -6%↓ 급락일 전체", ext_hist[ext_hist["reg_ret"] <= -0.06]),
    ("2Y-2. 정규장 -8%↓ 급락일 전체", ext_hist[ext_hist["reg_ret"] <= -0.08]),
    ("2Y-3. 정규장 -10%↓ 폭락일 전체", ext_hist[ext_hist["reg_ret"] <= -0.10]),
    ("2Y-4. 정규장 -6%↓ 급락 후 애프터 추가하락/보합(AH <= +1%)", ext_hist[(ext_hist["reg_ret"] <= -0.06) & (ext_hist["ah_ret"] <= 0.01)]),
    ("2Y-5. 정규장 -6%↓ 급락 후 애프터 +1.5%↑ 반등 선반영", ext_hist[(ext_hist["reg_ret"] <= -0.06) & (ext_hist["ah_ret"] >= 0.015)]),
    ("2Y-6. 정규장 -6%↓ 급락 후 애프터 +3.0%↑ 강반등 (현재 +6.66%)", ext_hist[(ext_hist["reg_ret"] <= -0.06) & (ext_hist["ah_ret"] >= 0.03)]),
    ("2Y-7. 애프터마켓 단독 +3.0%↑ 급등한 모든 날 (정규장 무관)", ext_hist[ext_hist["ah_ret"] >= 0.03]),
    ("2Y-8. 애프터마켓 단독 +5.0%↑ 급등한 모든 날 (현재 +6.66%)", ext_hist[ext_hist["ah_ret"] >= 0.05]),
    ("2Y-9. 저가마감(CLV < 0.20) & 정규장 -6%↓ 급락", ext_hist[(ext_hist["clv"] < 0.20) & (ext_hist["reg_ret"] <= -0.06)]),
    ("2Y-10. 목요일 AH종가 → 금요일 AH종가 (전체 목요일)", ext_hist[ext_hist["dow"] == 3]),
    ("2Y-11. 목요일 정규장 -5%↓ 하락 후 → 금요일 AH종가", ext_hist[(ext_hist["dow"] == 3) & (ext_hist["reg_ret"] <= -0.05)]),
]
res_ext = []
for lbl, sub in ext_conds:
    r = sum_ext(sub, lbl)
    res_ext.append(r)
    print(f"{lbl:55s} | N={r['N']:3d} | AH->AH win={r.get('ahah_win_pct')}% med={r.get('ahah_med_pct')}% mean={r.get('ahah_mean_pct')}% (Q25~Q75: {r.get('ahah_q25_pct')}~{r.get('ahah_q75_pct')}%) | vs RegClose win={r.get('vs_reg_close_win_pct')}% med={r.get('vs_reg_close_med_pct')}%")

# OLS regression: Does AH_ret predict next-day fade or continuation after big down days?
down_sub = ext_hist[ext_hist["reg_ret"] <= -0.05].copy()
x = down_sub["ah_ret"].values * 100.0
y_ahah = down_sub["ret_24h_ahah"].values * 100.0
y_open = down_sub["ret_ah_to_next_open"].values * 100.0
slope_ahah, intercept_ahah = np.polyfit(x, y_ahah, 1)
corr_ahah = np.corrcoef(x, y_ahah)[0, 1]
slope_open, intercept_open = np.polyfit(x, y_open, 1)
corr_open = np.corrcoef(x, y_open)[0, 1]
ols_info = {
    "sample": "2Y days with reg_ret <= -5%",
    "N": int(len(down_sub)),
    "ahah_slope": round(float(slope_ahah), 3),
    "ahah_intercept": round(float(intercept_ahah), 3),
    "ahah_corr": round(float(corr_ahah), 3),
    "pred_at_plus_6_66_ahah_pct": round(float(intercept_ahah + slope_ahah * 6.6555), 2),
    "open_slope": round(float(slope_open), 3),
    "open_intercept": round(float(intercept_open), 3),
    "open_corr": round(float(corr_open), 3),
    "pred_at_plus_6_66_to_open_pct": round(float(intercept_open + slope_open * 6.6555), 2),
}
print("\n=== OLS Regression on Big Down Days (reg_ret <= -5%): Next 24h Return vs AH Bounce ===")
print(json.dumps(ols_info, indent=2))

# List all specific episodes in last 2 years where reg_ret <= -10% AND ah_ret >= +2%!
episodes = ext_hist[(ext_hist["reg_ret"] <= -0.10) & (ext_hist["ah_ret"] >= 0.02)].copy()
print(f"\n=== Specific 2Y Episodes with Reg <= -10% AND AH Bounce >= +2% (N={len(episodes)}) ===")
ep_list = []
for dt, r in episodes.iterrows():
    ep = {
        "date": dt.strftime("%Y-%m-%d"),
        "dow": dt.strftime("%a"),
        "reg_close": round(float(r["reg_close"]), 2),
        "reg_ret_pct": round(float(r["reg_ret"] * 100), 2),
        "ah_close": round(float(r["ah_close"]), 2),
        "ah_ret_pct": round(float(r["ah_ret"] * 100), 2),
        "next_open": round(float(r["next_reg_open"]), 2),
        "ah_to_open_pct": round(float(r["ret_ah_to_next_open"] * 100), 2),
        "next_ah_close": round(float(r["next_ah_close"]), 2),
        "ret_24h_ahah_pct": round(float(r["ret_24h_ahah"] * 100), 2),
        "ret_vs_reg_close_pct": round(float(r["ret_reg_to_next_ah"] * 100), 2),
    }
    ep_list.append(ep)
    print(ep)

# Also check April 2025 tariff crash & Oct-Nov 2026 recent crash days in detail!
recent_crashes = ext_df[ext_df["reg_ret"] <= -0.14].copy()
print(f"\n=== All 2Y Extreme Crash Days (reg_ret <= -14%, N={len(recent_crashes)}) ===")
rc_list = []
for dt, r in recent_crashes.iterrows():
    rc = {
        "date": dt.strftime("%Y-%m-%d"),
        "dow": dt.strftime("%a"),
        "reg_close": round(float(r["reg_close"]), 2),
        "reg_ret_pct": round(float(r["reg_ret"] * 100), 2),
        "clv": round(float(r["clv"]), 3) if pd.notna(r["clv"]) else None,
        "ah_close": round(float(r["ah_close"]), 2),
        "ah_ret_pct": round(float(r["ah_ret"] * 100), 2),
        "next_open": round(float(r["next_reg_open"]), 2) if pd.notna(r["next_reg_open"]) else None,
        "next_reg_close": round(float(r["next_reg_close"]), 2) if pd.notna(r["next_reg_close"]) else None,
        "next_ah_close": round(float(r["next_ah_close"]), 2) if pd.notna(r["next_ah_close"]) else None,
        "ret_24h_ahah_pct": round(float(r["ret_24h_ahah"] * 100), 2) if pd.notna(r["ret_24h_ahah"]) else None,
        "ret_vs_reg_close_pct": round(float(r["ret_reg_to_next_ah"] * 100), 2) if pd.notna(r["ret_reg_to_next_ah"]) else None,
    }
    rc_list.append(rc)
    print(rc)

all_bt = {
    "indicators_2026_11_05": ind_snap,
    "worst_15_days_all_time": worst_list,
    "backtest_full_16y": res_full,
    "backtest_10y": res_10y,
    "backtest_2y_ext_ahah": res_ext,
    "ols_ah_bounce": ols_info,
    "episodes_crash_plus_ah_bounce": ep_list,
    "all_2y_crashes_le_14pct": rc_list,
}
with open(f"{out_dir}/forecast_backtest_all.json", "w", encoding="utf-8") as f:
    json.dump(all_bt, f, ensure_ascii=False, indent=2)
print("\nSaved forecast_backtest_all.json successfully!")
