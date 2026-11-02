"""Parse the Strategy Tester confirmation logs (out/confirm/<id>.txt) into CSVs.

Usage: python3 parse_confirm.py <confirm_dir> <jobs.json> <out_dir>
Writes confirm_summary.csv (one row per job), confirm_trades.csv (all trades), confirm_equity.csv (daily equity per job).
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os, re, json, glob
import pandas as pd

BUY = ["RSI14<30", "RSI2<10", "StochK<20", "Close<BB_lower", "CCI<-100", "EMA9xEMA21_up", "MACD_cross_up",
       "Supertrend_bull", "PSAR_bull", "DMI_bull&ADX>20", "Donchian20_break", "ORB30_break", "PrevDayHigh_break",
       "Close_x_VWAP_up", "Close>VWAP", "VolSpike&UpBar", "CLV<0.2", "FirstHour", "Close>SMA200d", "BarDrop<=-2%"]
SELL = ["RSI14>70", "RSI2>90", "StochK>80", "Close>BB_upper", "CCI>100", "EMA9xEMA21_down", "MACD_cross_down",
        "Supertrend_flip_bear", "PSAR_flip_bear", "DMI_cross_bear", "Donchian10_low_break", "Close_x_VWAP_down",
        "Close_x_EMA9_down", "BarSurge>=+2%", "TP+3%", "SL-2%", "Trail2%", "Chandelier2ATR", "Time4h", "EOD"]


def nm(tbl, a, b, j):
    return tbl[a] if b < 0 else f"{tbl[a]}{j}{tbl[b]}"


def num(s):
    return float(s.replace(",", ""))


def main():
    d, jobs_fp, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    jobs = {j["id"]: j for j in json.load(open(jobs_fp))}
    summ, trades, eq = [], [], []
    for fp in sorted(glob.glob(os.path.join(d, "*.txt")), key=lambda p: int(os.path.basename(p)[:-4]) if os.path.basename(p)[:-4].isdigit() else 0):
        jid = os.path.basename(fp)[:-4]
        if not jid.isdigit():
            continue
        jid = int(jid)
        J = jobs.get(jid, {})
        txt = open(fp, encoding="utf-8").read()
        m = re.search(r"S run=([\d,]+) buyA=(-?[\d,]+) buyB=(-?[\d,]+) sellA=(-?[\d,]+) sellB=(-?[\d,]+) tf=(\S+) netpct=(\S+) mddpct=(\S+) trades=([\d,]+) wins=([\d,]+) gp=(\S+) gl=(\S+) equity=(\S+) open=([\d,]+)", txt)
        if not m:
            print("no summary in", fp)
            continue
        g = [x.replace(",", "") for x in m.groups()]
        bA, bB, sA, sB = int(g[1]), int(g[2]), int(g[3]), int(g[4])
        key = re.search(r"KEYSTATS (.*)", txt)
        row = dict(id=jid, tf=g[5], buy=nm(BUY, bA, bB, " & "), sell=nm(SELL, sA, sB, " | "), buyA=bA, buyB=bB, sellA=sA, sellB=sB,
                   net_pct=float(g[6]), mdd_pct=float(g[7]), trades=int(g[8]), wins=int(g[9]), gp=float(g[10]), gl=float(g[11]), equity=float(g[12]), open_trades=int(g[13]),
                   params=json.dumps(J.get("params", {})), label=J.get("label", ""), keystats=key.group(1).strip() if key else "")
        # official Strategy Tester key stats (Total PnL includes the position still open at the end; the S line counts closed trades only)
        ks = row["keystats"].replace("\u2212", "-")
        km = re.search(r"Total PnL / ([+-]?[\d,\.]+)USD([+-]?[\d\.]+)% / Max drawdown / ([\d,\.]+)USD([\d\.]+)% / Profitable trades / ([\d\.]+)%(\d+)/(\d+) / Profit factor / ([\d\.]+)", ks)
        if km:
            row.update(tv_net_pct=float(km.group(2)), tv_mdd_pct=float(km.group(4)), tv_win_pct=float(km.group(5)), tv_wins=int(km.group(6)), tv_trades=int(km.group(7)), tv_pf=float(km.group(8)))
        else:
            row.update(tv_net_pct=float("nan"), tv_mdd_pct=float("nan"), tv_win_pct=float("nan"), tv_wins=0, tv_trades=0, tv_pf=float("nan"))
        row["win_pct"] = row["wins"] / row["trades"] * 100 if row["trades"] else float("nan")
        row["pf"] = row["gp"] / row["gl"] if row["gl"] > 0 else float("inf")
        summ.append(row)
        for tm in re.finditer(r"\]: T (.*)", txt):
            for rec in tm.group(1).split("|"):
                p = rec.strip().split(";")
                if len(p) < 7:
                    continue
                trades.append(dict(id=jid, tf=g[5], entry_time=p[0], exit_time=p[1], entry_px=float(p[2]), exit_px=float(p[3]), profit=float(p[4]), size=float(p[5]), exit_comment=p[6]))
        for qm in re.finditer(r"\]: Q (.*)", txt):
            for rec in qm.group(1).split("|"):
                parts = rec.strip().split(":")
                if len(parts) < 3:
                    continue
                eq.append(dict(id=jid, date=parts[0], equity=float(parts[1]), close=float(parts[2])))
    pd.DataFrame(summ).to_csv(os.path.join(out, "confirm_summary.csv"), index=False, float_format="%.4f")
    pd.DataFrame(trades).to_csv(os.path.join(out, "confirm_trades.csv"), index=False, float_format="%.4f")
    pd.DataFrame(eq).to_csv(os.path.join(out, "confirm_equity.csv"), index=False, float_format="%.2f")
    print(f"{len(summ)} jobs, {len(trades)} trades, {len(eq)} equity points")


if __name__ == "__main__":
    main()
