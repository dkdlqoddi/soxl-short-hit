"""Parse Pine Logs text dumps (one file per batch) from the screening indicator into one CSV.

Usage: python3 parse_logs.py <logs_dir> <out.csv>
Each log file contains lines like
  [2026-10-30T19:45:00.000-00:00]: R 0;12;7;1.0345;0.0821;0.12;0.08;1.01;0.03;120|1;...
"""
import sys, re, glob, os, csv

NB, NS, NBV, NSV = 20, 20, 210, 210

BUY = ["RSI14<30", "RSI2<10", "StochK<20", "Close<BB_lower", "CCI<-100", "EMA9xEMA21_up", "MACD_cross_up",
       "Supertrend_bull", "PSAR_bull", "DMI_bull&ADX>20", "Donchian20_break", "ORB30_break", "PrevDayHigh_break",
       "Close_x_VWAP_up", "Close>VWAP", "VolSpike&UpBar", "CLV<0.2", "FirstHour", "Close>SMA200d", "BarDrop<=-2%"]
SELL = ["RSI14>70", "RSI2>90", "StochK>80", "Close>BB_upper", "CCI>100", "EMA9xEMA21_down", "MACD_cross_down",
        "Supertrend_flip_bear", "PSAR_flip_bear", "DMI_cross_bear", "Donchian10_low_break", "Close_x_VWAP_down", "Close_x_EMA9_down", "BarSurge>=+2%",
        "TP+3%", "SL-2%", "Trail2%", "Chandelier2ATR", "Time4h", "EOD"]


def variants(n):
    v = [(i, -1) for i in range(n)]
    for i in range(n - 1):
        for j in range(i + 1, n):
            v.append((i, j))
    return v


BV = variants(NB)
SV = variants(NS)


def name(tbl, pair, joiner):
    a, b = pair
    return tbl[a] if b < 0 else tbl[a] + joiner + tbl[b]


def parse_dir(d):
    rows = {}
    for fp in sorted(glob.glob(os.path.join(d, "*.txt"))):
        txt = open(fp, encoding="utf-8").read()
        for m in re.finditer(r"\]: R (.*)", txt):
            for rec in m.group(1).split("|"):
                rec = rec.strip()
                if not rec:
                    continue
                parts = rec.split(";")
                if len(parts) < 10:
                    continue
                k = int(parts[0])
                rows[k] = parts
    return rows


def main():
    d, out = sys.argv[1], sys.argv[2]
    rows = parse_dir(d)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["k", "bv", "sv", "buy", "sell", "buy_a", "buy_b", "sell_a", "sell_b", "trades", "wins", "net_mult", "mdd", "gp", "gl", "mid_mult", "sum_ret", "sum_bars"])
        for k in sorted(rows):
            p = rows[k]
            bv, sv = k // NSV, k % NSV
            w.writerow([k, bv, sv, name(BUY, BV[bv], " & "), name(SELL, SV[sv], " | "), BV[bv][0], BV[bv][1], SV[sv][0], SV[sv][1]] + p[1:10])
    print(f"{len(rows)} combos written to {out}; missing={NBV * NSV - len(rows)}")


if __name__ == "__main__":
    main()
