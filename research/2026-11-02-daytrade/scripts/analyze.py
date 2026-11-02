"""Aggregate the TradingView Pine screening logs into per-timeframe CSVs and summary tables.

Usage: python3 analyze.py <screen_dir> <out_dir>
Reads screen_<tf>_b<k>.txt files written by the headless runner, parses the "R" records and writes
  data/screen_<tf>.csv          every combination with metrics
  data/top_<tf>.csv             top 50 by net return (trades >= 30)
  data/summary_buy_<tf>.csv     best exit for each buy variant
  data/summary_sell_<tf>.csv    best entry for each sell variant
  data/singles_<tf>.csv         marginal effect of each buy/sell condition (median over partners)
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os, re, glob, math
import pandas as pd
import numpy as np

NB, NS, NBV, NSV = 20, 20, 210, 210
BUY = ["RSI14<30", "RSI2<10", "StochK<20", "Close<BB_lower", "CCI<-100", "EMA9xEMA21_up", "MACD_cross_up",
       "Supertrend_bull", "PSAR_bull", "DMI_bull&ADX>20", "Donchian20_break", "ORB30_break", "PrevDayHigh_break",
       "Close_x_VWAP_up", "Close>VWAP", "VolSpike&UpBar", "CLV<0.2", "FirstHour", "Close>SMA200d", "BarDrop<=-2%"]
SELL = ["RSI14>70", "RSI2>90", "StochK>80", "Close>BB_upper", "CCI>100", "EMA9xEMA21_down", "MACD_cross_down",
        "Supertrend_flip_bear", "PSAR_flip_bear", "DMI_cross_bear", "Donchian10_low_break", "Close_x_VWAP_down",
        "Close_x_EMA9_down", "BarSurge>=+2%", "TP+3%", "SL-2%", "Trail2%", "Chandelier2ATR", "Time4h", "EOD"]
YEARS = {"5": 1.0, "15": 2.0, "30": 2.0, "60": 2.0, "120": 2.0}


def variants(n):
    v = [(i, -1) for i in range(n)]
    for i in range(n - 1):
        for j in range(i + 1, n):
            v.append((i, j))
    return v


BV, SV = variants(NB), variants(NS)


def vname(tbl, pair, joiner):
    a, b = pair
    return tbl[a] if b < 0 else f"{tbl[a]}{joiner}{tbl[b]}"


def parse_tf(screen_dir, tf, prefix="screen"):
    rows = {}
    nbars = None
    for fp in sorted(glob.glob(os.path.join(screen_dir, f"{prefix}_{tf}_b*.txt"))):
        txt = open(fp, encoding="utf-8").read()
        m = re.search(r"bars=([\d,]+)", txt)
        if m:
            nbars = int(m.group(1).replace(",", ""))
        for m in re.finditer(r"\]: R (.*)", txt):
            for rec in m.group(1).split("|"):
                p = rec.strip().split(";")
                if len(p) < 10:
                    continue
                rows[int(p[0])] = [float(x) for x in p[1:10]]
    if not rows:
        return None, nbars
    df = pd.DataFrame.from_dict(rows, orient="index", columns=["trades", "wins", "net_mult", "mdd", "gp", "gl", "mid_mult", "sum_ret", "sum_bars"])
    df.index.name = "k"
    df = df.sort_index()
    df["bv"] = df.index // NSV
    df["sv"] = df.index % NSV
    df["buy"] = [vname(BUY, BV[b], " & ") for b in df["bv"]]
    df["sell"] = [vname(SELL, SV[s], " | ") for s in df["sv"]]
    df["buy_a"] = [BV[b][0] for b in df["bv"]]
    df["buy_b"] = [BV[b][1] for b in df["bv"]]
    df["sell_a"] = [SV[s][0] for s in df["sv"]]
    df["sell_b"] = [SV[s][1] for s in df["sv"]]
    df["n_buy"] = np.where(df["buy_b"] >= 0, 2, 1)
    df["n_sell"] = np.where(df["sell_b"] >= 0, 2, 1)
    yrs = YEARS[tf]
    df["net_pct"] = (df["net_mult"] - 1) * 100
    df["cagr_pct"] = (df["net_mult"].clip(lower=1e-9) ** (1 / yrs) - 1) * 100
    df["mdd_pct"] = df["mdd"] * 100
    df["win_pct"] = np.where(df["trades"] > 0, df["wins"] / df["trades"].replace(0, np.nan) * 100, np.nan)
    df["pf"] = np.where(df["gl"] > 0, df["gp"] / df["gl"].replace(0, np.nan), np.inf)
    df["avg_ret_pct"] = np.where(df["trades"] > 0, df["sum_ret"] / df["trades"].replace(0, np.nan) * 100, np.nan)
    df["avg_bars"] = np.where(df["trades"] > 0, df["sum_bars"] / df["trades"].replace(0, np.nan), np.nan)
    df["y1_pct"] = (df["mid_mult"] - 1) * 100
    df["y2_pct"] = (df["net_mult"] / df["mid_mult"].replace(0, np.nan) - 1) * 100
    df["calmar"] = np.where(df["mdd"] > 0, df["cagr_pct"] / (df["mdd"] * 100), np.nan)
    df["tf"] = tf
    return df, nbars


def main():
    screen_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for tf in ["5", "15", "30", "60", "120"]:
        df, nbars = parse_tf(screen_dir, tf)
        if df is None:
            continue
        print(f"tf={tf}: {len(df)} combos (missing {NBV * NSV - len(df)}), bars={nbars}")
        df.to_csv(os.path.join(out_dir, f"screen_{tf}.csv"), float_format="%.4f")
        ok = df[df["trades"] >= 30]
        top = ok.sort_values("net_mult", ascending=False).head(50)
        top.to_csv(os.path.join(out_dir, f"top_{tf}.csv"), float_format="%.4f")
        # best sell for every buy variant, best buy for every sell variant
        ib = ok.groupby("bv")["net_mult"].idxmax()
        ok.loc[ib].sort_values("net_mult", ascending=False).to_csv(os.path.join(out_dir, f"summary_buy_{tf}.csv"), float_format="%.4f")
        isv = ok.groupby("sv")["net_mult"].idxmax()
        ok.loc[isv].sort_values("net_mult", ascending=False).to_csv(os.path.join(out_dir, f"summary_sell_{tf}.csv"), float_format="%.4f")
        # marginal effect of each single condition: median/mean net over all combos that contain it
        rec = []
        for i, nm in enumerate(BUY):
            sub = df[(df["buy_a"] == i) | (df["buy_b"] == i)]
            subok = sub[sub["trades"] >= 30]
            rec.append(["buy", i, nm, len(sub), float(sub["net_pct"].median()), float((sub["net_pct"] > 0).mean() * 100), float(subok["net_pct"].max()) if len(subok) else np.nan, float(sub["trades"].median())])
        for i, nm in enumerate(SELL):
            sub = df[(df["sell_a"] == i) | (df["sell_b"] == i)]
            subok = sub[sub["trades"] >= 30]
            rec.append(["sell", i, nm, len(sub), float(sub["net_pct"].median()), float((sub["net_pct"] > 0).mean() * 100), float(subok["net_pct"].max()) if len(subok) else np.nan, float(sub["trades"].median())])
        pd.DataFrame(rec, columns=["side", "idx", "name", "n_combos", "median_net_pct", "pct_positive", "best_net_pct", "median_trades"]).to_csv(os.path.join(out_dir, f"singles_{tf}.csv"), float_format="%.2f", index=False)
        # robustness of each buy variant across all 210 exits, and of each sell variant across all 210 entries
        gb = ok.groupby(["bv", "buy"]).agg(n=("net_pct", "size"), pct_pos=("net_pct", lambda x: (x > 0).mean() * 100), median_net=("net_pct", "median"),
                                           q75_net=("net_pct", lambda x: x.quantile(0.75)), best_net=("net_pct", "max"), median_mdd=("mdd_pct", "median"), median_trades=("trades", "median")).reset_index()
        gb.sort_values("median_net", ascending=False).to_csv(os.path.join(out_dir, f"robust_buy_{tf}.csv"), float_format="%.1f", index=False)
        gs = ok.groupby(["sv", "sell"]).agg(n=("net_pct", "size"), pct_pos=("net_pct", lambda x: (x > 0).mean() * 100), median_net=("net_pct", "median"),
                                            q75_net=("net_pct", lambda x: x.quantile(0.75)), best_net=("net_pct", "max"), median_mdd=("mdd_pct", "median"), median_trades=("trades", "median")).reset_index()
        gs.sort_values("median_net", ascending=False).to_csv(os.path.join(out_dir, f"robust_sell_{tf}.csv"), float_format="%.1f", index=False)
        frames.append(df)
        print(f"  positive: {(df['net_pct'] > 0).mean() * 100:.1f}%  median net {df['net_pct'].median():.1f}%  best (>=30 trades): {top.iloc[0]['buy']} -> {top.iloc[0]['sell']} net {top.iloc[0]['net_pct']:.0f}% mdd {top.iloc[0]['mdd_pct']:.0f}% trades {int(top.iloc[0]['trades'])}")
    if frames:
        pd.concat(frames).to_csv(os.path.join(out_dir, "screen_all.csv"), float_format="%.4f")
    for tf in ["15", "60"]:
        rd, _ = parse_tf(screen_dir, tf, prefix="random")
        if rd is not None:
            rd.to_csv(os.path.join(out_dir, f"random_{tf}.csv"), float_format="%.4f")
            rok = rd[rd["trades"] >= 30]
            print(f"random tf={tf}: {len(rd)} combos; positive {(rok['net_pct'] > 0).mean() * 100:.1f}%; best {rok['net_pct'].max():.0f}%; 99th pct {rok['net_pct'].quantile(0.99):.0f}%; 99.9th {rok['net_pct'].quantile(0.999):.0f}%")


if __name__ == "__main__":
    main()
