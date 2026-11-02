import sys, site; sys.path.insert(0, site.getusersitepackages())
import pandas as pd, numpy as np, itertools, time
out = sys.argv[1]
d = pd.read_csv(f"{out}/soxl_daily_nasdaq.csv", parse_dates=["date"]).set_index("date").sort_index()
O,H,L,C = [d[c].values.astype(float) for c in ["open","high","low","close"]]
idx = d.index; n = len(d); YEARS = (idx[-1]-idx[0]).days/365.25
FEE=0.0025; SLIP=0.0005; CUSH=0.002
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
def sma(a,w): return pd.Series(a).rolling(w).mean().values
SMA20, SMA50, SMA200 = sma(C,20), sma(C,50), sma(C,200)

def summarize(trades, name, params, years=YEARS):
    res = dict(strategy=name, **params)
    if not trades: res.update(trades=0); return res
    t = pd.DataFrame(trades); eq=(1+t.ret).cumprod(); dd=(eq/eq.cummax()-1).min(); w=t.ret>0
    gw=t.ret[w].sum(); gl=-t.ret[~w].sum()
    res.update(trades=len(t), per_yr=round(len(t)/years,1), win=round(w.mean()*100,1), avg=round(t.ret.mean()*100,2), med=round(t.ret.median()*100,2),
               avgW=round(t.ret[w].mean()*100,2) if w.any() else np.nan, avgL=round(t.ret[~w].mean()*100,2) if (~w).any() else np.nan,
               worst=round(t.ret.min()*100,1), total=round((eq.iloc[-1]-1)*100,0), cagr=round((eq.iloc[-1]**(1/years)-1)*100,1), mdd=round(dd*100,1),
               pf=round(gw/gl,2) if gl>0 else np.inf, hold=round(t.hold.mean(),1),
               tstat=round(t.ret.mean()/t.ret.std()*np.sqrt(len(t)),2) if len(t)>2 and t.ret.std()>0 else np.nan)
    return res

def dip_limit(disc, target=None, stop=None, hold=1, exit_at="close", trend=None, tf=20, fee=FEE, start=0):
    """Place a limit buy at prev_close*(1-disc) each session while flat. Fill if low <= limit (0.2% cushion); gap-down fills at open.
       hold=0: sell at that day's close. hold>=1: evaluate stop/target on following sessions, time-exit at close (or open) of session fill+hold."""
    ma = {20:SMA20,50:SMA50,200:SMA200}.get(tf)
    trades=[]; i=max(1,start)
    while i < n:
        if trend=="above" and not (C[i-1] > ma[i-1]): i+=1; continue
        if trend=="below" and not (C[i-1] < ma[i-1]): i+=1; continue
        lim = C[i-1]*(1-disc)
        if L[i] <= lim*(1-CUSH):
            entry = min(O[i], lim); ex=None; exfee=fee+SLIP; j=i
            if hold==0:
                ex=C[i]
            else:
                last = i+hold
                for j in range(i+1, min(last, n-1)+1):
                    if exit_at=="open" and j==last: ex=O[j]; break
                    if stop is not None:
                        sp=entry*(1-stop)
                        if O[j] <= sp: ex=O[j]; break
                        if L[j] <= sp: ex=sp; break
                    if target is not None:
                        tp=entry*(1+target)
                        if O[j] >= tp: ex=O[j]; exfee=fee; break
                        if H[j] >= tp: ex=tp; exfee=fee; break
                    if j==last: ex=C[j]; break
                if ex is None: ex=C[j]
            ret = ex*(1-exfee)/(entry*(1+fee)) - 1
            trades.append(dict(entry_date=idx[i], exit_date=idx[j], entry=entry, exit=ex, ret=ret, hold=j-i))
            i=j+1
        else: i+=1
    return trades

def mr(thresh, hold=1, exit_at="close", lookback=1, trend=None, tf=20, fee=FEE):
    """Signal: close-to-close drop <= -thresh over `lookback` sessions. Buy next open. Exit at close of session (entry+hold-1) or open of (entry+hold)."""
    ma = {20:SMA20,50:SMA50,200:SMA200}.get(tf); trades=[]; i=max(lookback,200)
    while i < n-1:
        r = C[i]/C[i-lookback]-1; ok = r <= -thresh
        if trend=="above": ok = ok and C[i] > ma[i]
        if trend=="below": ok = ok and C[i] < ma[i]
        if ok:
            e=i+1; entry=O[e]
            if exit_at=="close": j=min(e+hold-1, n-1); ex=C[j]; hd=j-e+1
            else: j=min(e+hold, n-1); ex=O[j]; hd=j-e
            ret = ex*(1-fee-SLIP)/(entry*(1+fee+SLIP))-1
            trades.append(dict(entry_date=idx[e], exit_date=idx[j], entry=entry, exit=ex, ret=ret, hold=hd)); i=j+1
        else: i+=1
    return trades

def breakout(w_in=20, w_out=10, fee=FEE):
    hh = pd.Series(H).rolling(w_in).max().shift(1).values; ll = pd.Series(L).rolling(w_out).min().shift(1).values
    trades=[]; i=max(w_in,w_out)+1
    while i < n-2:
        if C[i] > hh[i]:
            e=i+1; entry=O[e]; j=e
            while j < n-2 and not (C[j] < ll[j]): j+=1
            x=j+1; ex=O[x]; ret=ex*(1-fee-SLIP)/(entry*(1+fee+SLIP))-1
            trades.append(dict(entry_date=idx[e], exit_date=idx[x], entry=entry, exit=ex, ret=ret, hold=x-e)); i=x
        else: i+=1
    return trades

t0=time.time()
print(f"data {idx[0].date()} -> {idx[-1].date()}, {n} sessions, {YEARS:.1f} years. fee {FEE*100:.2f}%/side (0.5% round trip), slip {SLIP*100:.2f}%/side on market orders, limit fill needs low <= limit*(1-{CUSH})")
bh = C[-1]/C[0]-1; print(f"\n[benchmark] SOXL buy&hold 10y: {bh*100:,.0f}%  (CAGR {((1+bh)**(1/YEARS)-1)*100:.1f}%), max drawdown {((pd.Series(C)/pd.Series(C).cummax()-1).min())*100:.0f}%")
for lab, k in [("1y",250),("3y",750)]:
    print(f"[benchmark] SOXL buy&hold last {lab}: {(C[-1]/C[-k-1]-1)*100:.0f}%")

# ---------- S5: where do returns come from (gross, no fees) ----------
gap = O[1:]/C[:-1]-1; intra = C/O-1
print("\n=== S5 overnight vs intraday (gross, no fees) ===")
for lab, sl in [("10y", slice(None)), ("3y", slice(-750,None)), ("1y", slice(-250,None))]:
    g=gap[sl]; it=intra[1:][sl]
    print(f"{lab}: overnight(close->open) mean {g.mean()*100:+.2f}%/day cum {np.prod(1+g)-1:+.0%} | intraday(open->close) mean {it.mean()*100:+.2f}%/day cum {np.prod(1+it)-1:+.0%} | net of 0.5% fee+0.1% slip per daily round trip: overnight {np.prod(1+g-0.006)-1:+.0%}, intraday {np.prod(1+it-0.006)-1:+.0%}")

# ---------- regime tables ----------
print("\n=== next-day return by MA regime (close-to-close, gross) ===")
ret = pd.Series(C).pct_change().shift(-1).values  # next-day return
for name, ma in [("SMA20",SMA20),("SMA50",SMA50),("SMA200",SMA200)]:
    ab = (C>ma); ok=~np.isnan(ma)&~np.isnan(ret)
    for lab, m in [("above", ab&ok), ("below", (~ab)&ok)]:
        r=ret[m]; print(f"{name} {lab:5s}: n={m.sum():4d} days {m.sum()/ok.sum()*100:4.0f}%  mean {r.mean()*100:+.2f}%  std {r.std()*100:.1f}%  share of days<=-15%: {(r<=-0.15).mean()*100:.1f}%  share>=+10%: {(r>=0.10).mean()*100:.1f}%")
big = pd.Series(C).pct_change() <= -0.15
print(f"\nall sessions with ret <= -15%: {int(big.sum())}; of these, prior close below SMA20: {int((big & (pd.Series(C).shift(1) < pd.Series(SMA20).shift(1))).sum())}, below SMA50: {int((big & (pd.Series(C).shift(1) < pd.Series(SMA50).shift(1))).sum())}")

print("\n=== forward returns after a big down day (gross, close->close) ===")
r1 = pd.Series(C).pct_change()
for th in [-0.10,-0.15,-0.20]:
    m = r1 <= th; rows=[]
    for k in [1,3,5,10,20]:
        f = pd.Series(C).shift(-k)/pd.Series(C)-1; x=f[m].dropna()
        rows.append(f"+{k}d: mean {x.mean()*100:+.1f}% med {x.median()*100:+.1f}% win {(x>0).mean()*100:.0f}%")
    print(f"day <= {th*100:.0f}% (n={int(m.sum())}): " + " | ".join(rows))

# ---------- S1 grid ----------
print("\n=== S1 dip-limit grid: baseline (no target/stop, no filter), avg net %/trade [fill count] ===")
discs=[0.01,0.02,0.03,0.04,0.05,0.07,0.10]; holds=[0,1,2,3,5]
rows=[]
for dsc in discs:
    row={"disc%":dsc*100}
    for hd in holds:
        s=summarize(dip_limit(dsc,hold=hd),"dip",{}); row[f"hold{hd}"]=f"{s.get('avg',np.nan):+.2f} [{s.get('trades',0)}] w{s.get('win',np.nan):.0f} dd{s.get('mdd',np.nan):.0f}"
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== S1 same grid, last 1 year only (start=n-250) ===")
rows=[]
for dsc in discs:
    row={"disc%":dsc*100}
    for hd in holds:
        s=summarize(dip_limit(dsc,hold=hd,start=n-250),"dip",{},years=1.0); row[f"hold{hd}"]=f"{s.get('avg',np.nan):+.2f} [{s.get('trades',0)}] w{s.get('win',np.nan):.0f}"
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))

allres=[]
for dsc,hd,tg,sp,tr,ea in itertools.product(discs,holds,[None,0.02,0.03,0.05,0.08],[None,0.05,0.08,0.12],[None,"above","below"],["close","open"]):
    if hd==0 and (tg or sp or ea=="open"): continue
    allres.append(summarize(dip_limit(dsc,target=tg,stop=sp,hold=hd,exit_at=ea,trend=tr,tf=20),"dip",dict(disc=dsc,hold=hd,target=tg,stop=sp,trend=tr,exit_at=ea)))
R=pd.DataFrame(allres); R.to_csv(f"{out}/grid_dip.csv",index=False)
R30=R[R.trades>=40]
print(f"\n=== S1 full grid: {len(R)} configs, {len(R30)} with >=40 trades. Top 15 by t-stat ===")
cols=["disc","hold","target","stop","trend","exit_at","trades","per_yr","win","avg","avgW","avgL","worst","total","cagr","mdd","pf","tstat"]
print(R30.sort_values("tstat",ascending=False).head(15)[cols].to_string(index=False))
print("\n--- Top 10 by total return (>=40 trades) ---"); print(R30.sort_values("total",ascending=False).head(10)[cols].to_string(index=False))
print("\n--- Bottom 8 by t-stat (>=40 trades) ---"); print(R30.sort_values("tstat").head(8)[cols].to_string(index=False))
print("\n--- trend filter effect: mean of avg-net-per-trade across all configs with hold>=1 ---")
print(R30[R30.hold>=1].groupby("trend",dropna=False)[["avg","win","mdd","per_yr"]].mean().round(2).to_string())
print("\n--- exit_at effect (hold>=1) ---"); print(R30[R30.hold>=1].groupby("exit_at")[["avg","win","mdd"]].mean().round(2).to_string())
print("\n--- stop effect (hold>=1) ---"); print(R30[R30.hold>=1].groupby("stop",dropna=False)[["avg","win","mdd","worst"]].mean().round(2).to_string())
print("\n--- target effect (hold>=1) ---"); print(R30[R30.hold>=1].groupby("target",dropna=False)[["avg","win","mdd"]].mean().round(2).to_string())

# ---------- S2 grid ----------
res=[]
for th,hd,ea,lb,tr in itertools.product([0.03,0.05,0.08,0.10,0.15],[1,2,3,5],["close","open"],[1,2],[None,"above","below"]):
    res.append(summarize(mr(th,hold=hd,exit_at=ea,lookback=lb,trend=tr,tf=20),"mr",dict(thresh=th,hold=hd,exit_at=ea,lookback=lb,trend=tr)))
M=pd.DataFrame(res); M.to_csv(f"{out}/grid_mr.csv",index=False); M30=M[M.trades>=25]
cols2=["thresh","hold","exit_at","lookback","trend","trades","per_yr","win","avg","avgW","avgL","worst","total","cagr","mdd","pf","tstat"]
print(f"\n=== S2 close-drop -> buy next open: {len(M)} configs, {len(M30)} with >=25 trades (SMA warm-up: from 2017-08). Top 12 by t-stat ===")
print(M30.sort_values("tstat",ascending=False).head(12)[cols2].to_string(index=False))
print("\n--- S2 bottom 6 ---"); print(M30.sort_values("tstat").head(6)[cols2].to_string(index=False))
print("\n--- S2 trend filter effect ---"); print(M30.groupby("trend",dropna=False)[["avg","win","mdd","per_yr"]].mean().round(2).to_string())

# ---------- S4 breakout ----------
print("\n=== S4 breakout (buy next open after close > prior N-day high; exit next open after close < prior M-day low) ===")
B=pd.DataFrame([summarize(breakout(a,b),"brk",dict(w_in=a,w_out=b)) for a,b in [(20,10),(10,5),(50,20),(20,5),(55,20)]])
print(B.to_string(index=False))

# ---------- fee sensitivity on a few representative configs ----------
print("\n=== fee sensitivity (per-side fee; 0.0025 = user's 0.5% round trip) ===")
reps=[dict(disc=0.03,hold=1),dict(disc=0.05,hold=1),dict(disc=0.05,hold=3,trend="above"),dict(disc=0.07,hold=2),dict(disc=0.03,hold=1,trend="above")]
rows=[]
for p in reps:
    for f in [0.0,0.001,0.0025,0.005]:
        s=summarize(dip_limit(fee=f,**p),"dip",dict(**p,fee_side=f)); rows.append(s)
F=pd.DataFrame(rows); print(F[["disc","hold","trend","fee_side","trades","win","avg","total","cagr","mdd","tstat"]].to_string(index=False))

# ---------- per-year robustness for a few configs ----------
print("\n=== per-year results, selected dip configs (avg net %/trade | trades | win%) ===")
sel=[dict(disc=0.03,hold=1),dict(disc=0.05,hold=1),dict(disc=0.05,hold=1,trend="above"),dict(disc=0.07,hold=1),dict(disc=0.05,hold=3,trend="above"),dict(disc=0.10,hold=1)]
tab={}
for p in sel:
    t=pd.DataFrame(dip_limit(**p)); t["yr"]=t.entry_date.dt.year
    g=t.groupby("yr").agg(avg=("ret","mean"),nt=("ret","size"),win=("ret",lambda x:(x>0).mean()))
    tab[str(p)]=g.apply(lambda r:f"{r.avg*100:+.1f}|{int(r.nt)}|{r.win*100:.0f}",axis=1)
print(pd.DataFrame(tab).to_string())

# ---------- Oct 2026 replay of the user's style ----------
print("\n=== Oct 2026 replay: dip-limit fills (hold=1 exit next close, no stop) ===")
for dsc in [0.03,0.05,0.07]:
    t=pd.DataFrame(dip_limit(dsc,hold=1,start=n-20))
    if len(t): print(f"disc {dsc*100:.0f}%:"); print(t.assign(ret=lambda x:(x.ret*100).round(2)).to_string(index=False))
    else: print(f"disc {dsc*100:.0f}%: no fills")
print(f"\nelapsed {time.time()-t0:.0f}s")
