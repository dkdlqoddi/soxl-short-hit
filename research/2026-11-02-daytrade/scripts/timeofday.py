"""Time-of-day profile (KST) of the confirmed strategies' trades.

Usage: python3 timeofday.py <confirm_dir> <out_csv>
Entry/exit times in the logs are America/New_York; converts to Asia/Seoul and summarises per job:
share of entries in the user's awake windows (US open 22:30-01:00 KST in EDT / 23:30-02:00 in EST, i.e. first 2.5 h of the session),
share of exits in the last hour (needs to be awake at the US close), and overnight holds.
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os
import pandas as pd


def main():
    cdir, out = sys.argv[1], sys.argv[2]
    T = pd.read_csv(os.path.join(cdir, "confirm_trades.csv"))
    S = pd.read_csv(os.path.join(cdir, "confirm_summary.csv"))
    if T.empty:
        print("no trades")
        return
    for c in ("entry_time", "exit_time"):
        T[c] = pd.to_datetime(T[c]).dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
        T[c + "_kst"] = T[c].dt.tz_convert("Asia/Seoul")
    T["entry_et_min"] = T.entry_time.dt.hour * 60 + T.entry_time.dt.minute
    T["exit_et_min"] = T.exit_time.dt.hour * 60 + T.exit_time.dt.minute
    T["overnight"] = T.entry_time.dt.date != T.exit_time.dt.date
    T["hold_h"] = (T.exit_time - T.entry_time).dt.total_seconds() / 3600
    T["entry_first150"] = (T.entry_et_min >= 9 * 60 + 30) & (T.entry_et_min < 12 * 60)      # 09:30-12:00 ET = 22:30/23:30-01:00/02:00 KST
    T["exit_last60"] = T.exit_et_min >= 15 * 60                                                 # 15:00-16:00 ET = during Korean sleep
    T["ret_pct"] = T.profit / (T.entry_px * T["size"]) * 100
    g = T.groupby("id").agg(trades=("profit", "size"), entry_first150_pct=("entry_first150", "mean"), exit_last60_pct=("exit_last60", "mean"),
                            overnight_pct=("overnight", "mean"), median_hold_h=("hold_h", "median"), avg_ret_pct=("ret_pct", "mean"),
                            ret_first150=("ret_pct", lambda x: x[T.loc[x.index, "entry_first150"]].mean()),
                            ret_other=("ret_pct", lambda x: x[~T.loc[x.index, "entry_first150"]].mean()))
    for c in ("entry_first150_pct", "exit_last60_pct", "overnight_pct"):
        g[c] = g[c] * 100
    g = g.merge(S[["id", "tf", "buy", "sell", "label", "net_pct"]], left_index=True, right_on="id")
    g.to_csv(out, index=False, float_format="%.2f")
    print(g.sort_values("net_pct", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
