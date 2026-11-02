"""Python replica of the Pine script's ORDER SEMANTICS (research/2026-11-01/scripts/soxl_grid.pine).

Differences from grid.simulate (the literal "one order at a time" reading of the rules):
  * orders are placed only at bar close and act on the NEXT bar (TradingView broker emulator)
  * a ladder of `levels` limit buys sits at lastFill*(1-step)^j; a gap-down open fills every level >= open AT THE OPEN
  * the take-profit limit is fixed at the previous close's avg price; buys during the bar do not move it until the next close
  * the ladder stays active after the take-profit fills inside the same bar, so re-entry can happen intrabar
  * on the re-entry bar (market buy at open) there is no ladder yet, so no further fills that bar
Intrabar tick order: up bar O,L,H,C / down bar O,H,L,C (TradingView "4 ticks per bar").
Usage: python3 -I tv_semantics.py [1d|1h] [start] [end]
"""
import sys, site; sys.path.insert(0, site.getusersitepackages())
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from grid import load_yf, metrics, simulate

def sim_tv(O, H, L, C, T, mode="total", step=0.01, N=100, levels=40, capital=8200.0, fee=0.0025, q=None, tick="closeopen", whole=False):
    n = len(C); cash = capital; lots = []            # [price, shares, tp(None until armed at a close)]
    lotq = 0.0; last = None; ladder = []; tp = None; pending = True
    eq = np.empty(n); eq_lo = np.empty(n); eq_hi = np.empty(n)
    nbuy = nsell = 0; maxlots = 0; fees = 0.0; nocash = 0; realized = 0.0; max_fills = 0
    def buy(px):
        nonlocal cash, nbuy, fees, nocash
        cost = px * lotq * (1 + fee)
        if lotq <= 0 or cost > cash + 1e-9: nocash += 1; return False
        cash -= cost; fees += px * lotq * fee; lots.append([px, lotq, None]); nbuy += 1; return True
    def sell(sel, px_of):
        nonlocal cash, nsell, fees, lots, realized
        keep = []; sold = False
        for k, (p, s, t) in enumerate(lots):
            if sel(k, p, s, t):
                px = px_of(p, t); cash += px * s * (1 - fee); fees += px * s * fee; realized += px * s * (1 - fee) - p * s * (1 + fee); sold = True
            else: keep.append([p, s, t])
        lots = keep
        if sold: nsell += 1
    for i in range(n):
        o, h, l, c = O[i], H[i], L[i], C[i]; fills = []
        if pending:
            if q is not None: lotq = q
            if buy(o): fills.append(o)
            pending = False
        def buys(floor):
            nonlocal ladder
            rem = []
            for lv in ladder:
                if lv >= floor:
                    px = o if lv >= o else lv
                    if buy(px): fills.append(px)
                else: rem.append(lv)
            ladder = rem
        def sells(tick):
            nonlocal tp
            if not lots: return
            if mode == "total":
                if tp is None: return
                if tick == "O" and o >= tp: sell(lambda k, p, s, t: True, lambda p, t: o); tp = None
                elif tick == "H" and h >= tp: sell(lambda k, p, s, t: True, lambda p, t: tp); tp = None
            else:
                if tick == "O": sell(lambda k, p, s, t: t is not None and t <= o, lambda p, t: o)
                elif tick == "H": sell(lambda k, p, s, t: t is not None and t <= h, lambda p, t: t)
        up = (c >= o) if tick == "closeopen" else ((h - o) >= (o - l))   # nearest: open closer to high -> O,H,L,C
        if up:   # O, L, H, C
            buys(o); sells("O"); buys(l); sells("H")
        else:    # O, H, L, C
            buys(o); sells("O"); sells("H"); buys(l)
        if fills: last = min(fills)
        max_fills = max(max_fills, len(fills))
        sh = sum(s for p, s, t in lots)
        eq[i] = cash + sh * c; eq_lo[i] = cash + sh * l; eq_hi[i] = cash + sh * h
        maxlots = max(maxlots, len(lots))
        # bar close: place next bar's orders (Pine: cancel_all, then entry/ladder/exit)
        if not lots:
            pending = True; ladder = []; tp = None
            if q is None: lotq = cash / (N * c)
            if whole: lotq = float(int(lotq))   # TradingView truncates stock quantities to whole shares
        else:
            base = last if last is not None else lots[-1][0]
            ladder = [base * (1 - step) ** j for j in range(1, levels + 1)]
            if mode == "total": tp = (sum(p * s for p, s, t in lots) / sh) * (1 + T)
            else:
                for lot in lots: lot[2] = lot[0] * (1 + T)
    st = dict(nbuy=nbuy, nsell=nsell, maxlots=maxlots, fees=round(fees), nocash=nocash, realized=round(realized),
              end_lots=len(lots), end_unreal=round(sum(s for p, s, t in lots) * C[-1] - sum(p * s for p, s, t in lots)), max_fills=max_fills)
    return eq, eq_lo, eq_hi, st

def mdd_variants(eq, eq_lo, eq_hi):
    peak_c = np.maximum.accumulate(eq); peak_h = np.maximum.accumulate(eq_hi)
    return dict(mdd_close=round((eq / peak_c - 1).min() * 100, 1),
                mdd_low_peakclose=round((eq_lo / peak_c - 1).min() * 100, 1),
                mdd_low_peakhigh=round((eq_lo / peak_h - 1).min() * 100, 1))

if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tf = sys.argv[1] if len(sys.argv) > 1 else "1d"
    start = sys.argv[2] if len(sys.argv) > 2 else "2016-10-24"
    end = sys.argv[3] if len(sys.argv) > 3 else "2026-10-30"
    levels = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    df = load_yf(os.path.join(here, "data", f"soxl_{tf}_yf.csv"))
    if df.index.tz is not None:
        s = pd.Timestamp(start, tz="America/New_York"); e = pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1)
        df = df[(df.index >= s) & (df.index < e)]
    else:
        df = df.loc[start:end]
    O, H, L, C = [df[k].to_numpy(float) for k in ("open", "high", "low", "close")]
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"{tf}: {df.index[0]} .. {df.index[-1]}  bars={len(df)}  years={years:.2f}")
    tv = pd.read_csv(os.path.join(here, "data", "H_tradingview.csv"))
    tv = tv[(tv.tf == tf) & (tv.levels == levels)]
    rows = []
    for mode, T in [("total", .03), ("total", .05), ("total", .07), ("total", .10), ("total", .20),
                    ("perlot", .05), ("perlot", .10), ("perlot", .15), ("perlot", .20)]:
        eq, lo, hi, st = sim_tv(O, H, L, C, T, mode, levels=levels)
        m = metrics(eq, years); v = mdd_variants(eq, lo, hi)
        eqn, lon, hin, stn = sim_tv(O, H, L, C, T, mode, levels=levels, tick="nearest")
        mn = metrics(eqn, years); vn = mdd_variants(eqn, lon, hin)
        eqw, low_, hiw, stw = sim_tv(O, H, L, C, T, mode, levels=levels, whole=True)
        mw = metrics(eqw, years); vw = mdd_variants(eqw, low_, hiw)
        eq2, st2, _ = simulate(O, H, L, C, T, mode)
        m2 = metrics(eq2, years)
        r = tv[(tv.rule == mode) & (tv["T"] == round(T * 100))]
        rows.append(dict(rule=f"{mode} +{T*100:g}%",
                         tv_total=float(r.tv_total_pct.iloc[0]) if len(r) else np.nan, tv_mdd=float(r.tv_mdd_pct.iloc[0]) if len(r) else np.nan,
                         tv_trades=int(r.tv_trades.iloc[0]) if len(r) else -1,
                         py_tv_total=m["total"], py_tv_realized_pct=round(st["realized"] / 82, 1), **v,
                         py_whole_total=mw["total"], py_whole_mdd=mw["mdd"], py_whole_mdd_low=vw["mdd_low_peakclose"], py_whole_buys=stw["nbuy"], py_whole_endlots=stw["end_lots"],
                         py_near_total=mn["total"], py_near_realized_pct=round(stn["realized"] / 82, 1), py_near_mdd=mn["mdd"], py_near_mdd_low=vn["mdd_low_peakclose"], py_near_buys=stn["nbuy"], py_tv_buys=st["nbuy"], py_tv_sells=st["nsell"],
                         py_tv_maxlots=st["maxlots"], py_tv_maxfills=st["max_fills"], py_tv_end_unreal=st["end_unreal"],
                         py_seq_total=m2["total"], py_seq_mdd=m2["mdd"], py_seq_buys=st2["nbuy"]))
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(out.to_string(index=False))
    out.to_csv(os.path.join(here, "data", f"H_tv_vs_python_{tf}.csv"), index=False)
