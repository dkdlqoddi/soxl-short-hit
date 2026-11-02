import sys, site; sys.path.insert(0, site.getusersitepackages())
import pandas as pd, numpy as np, itertools, importlib.util
out = sys.argv[1]
spec = importlib.util.spec_from_file_location("bt", sys.argv[2]); 
# reuse backtest functions without re-running its prints: exec only the definitions
src = open(sys.argv[2]).read().split("t0=time.time()")[0]
ns = {}; exec(compile(src, "bt_defs", "exec"), ns)
C,O,H,L,idx,n,SMA20,SMA50,SMA200,summarize,dip_limit,mr,YEARS = [ns[k] for k in ["C","O","H","L","idx","n","SMA20","SMA50","SMA200","summarize","dip_limit","mr","YEARS"]]
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
print(f"as of {idx[-1].date()}: close {C[-1]:.2f}  SMA20 {SMA20[-1]:.2f} ({(C[-1]/SMA20[-1]-1)*100:+.1f}%)  SMA50 {SMA50[-1]:.2f} ({(C[-1]/SMA50[-1]-1)*100:+.1f}%)  SMA200 {SMA200[-1]:.2f} ({(C[-1]/SMA200[-1]-1)*100:+.1f}%)")
print(f"peak close (last 60d): {C[-60:].max():.2f} on {idx[-60:][C[-60:].argmax()].date()}, drawdown from it: {(C[-1]/C[-60:].max()-1)*100:.1f}%")
rv20 = pd.Series(C).pct_change().rolling(20).std()*np.sqrt(252)*100
print(f"20d realized vol now {rv20.iloc[-1]:.0f}% annualized vs 10y median {rv20.median():.0f}%, 90th pct {rv20.quantile(.9):.0f}%")

# --- S2 neighborhood robustness (incl. longer holds and SMA50 filter) ---
rows=[]
for th,hd,ea,lb,tr,tf in itertools.product([0.03,0.05,0.08],[3,5,7,10],["open","close"],[1,2],["above"],[20,50]):
    rows.append(summarize(mr(th,hold=hd,exit_at=ea,lookback=lb,trend=tr,tf=tf),"mr",dict(thresh=th,hold=hd,exit_at=ea,lookback=lb,tf=tf)))
N=pd.DataFrame(rows)
print("\n=== S2 neighborhood (trend=above, SMA20 vs SMA50) ===")
print(N[["thresh","hold","exit_at","lookback","tf","trades","win","avg","worst","total","cagr","mdd","pf","tstat"]].sort_values(["tf","thresh","hold","lookback","exit_at"]).to_string(index=False))
print("\nmean by hold:"); print(N.groupby("hold")[["avg","win","mdd","pf"]].mean().round(2).to_string())
print("mean by tf:"); print(N.groupby("tf")[["avg","win","mdd","pf"]].mean().round(2).to_string())

# --- walk-forward split for the headline S2 config and the user's style ---
def split_stats(trades, label):
    t=pd.DataFrame(trades); t["half"]=np.where(t.entry_date<pd.Timestamp("2022-01-01"),"2017-2021","2022-2026")
    g=t.groupby("half").agg(trades=("ret","size"),win=("ret",lambda x:(x>0).mean()*100),avg=("ret",lambda x:x.mean()*100),total=("ret",lambda x:((1+x).prod()-1)*100))
    print(f"\n--- {label} ---"); print(g.round(2).to_string())
split_stats(mr(0.03,hold=5,exit_at="open",lookback=2,trend="above",tf=20), "S2: 2-day drop>=3%, above SMA20, buy next open, sell open 5 sessions later")
split_stats(mr(0.05,hold=5,exit_at="open",lookback=1,trend="above",tf=20), "S2: 1-day drop>=5%, above SMA20, hold 5, exit open")
split_stats(mr(0.10,hold=1,exit_at="open",lookback=1,trend=None,tf=20), "S2 crash-bounce: 1-day drop>=10%, no filter, buy next open, sell following open")
split_stats(dip_limit(0.03,hold=1), "user style: limit -3%, sell next close")

# --- 2026 trades for headline configs ---
for label, tr in [("S2 2d>=3% above SMA20 hold5 exit open", mr(0.03,hold=5,exit_at="open",lookback=2,trend="above",tf=20)),
                  ("S2 crash-bounce 1d>=10% hold1 exit open", mr(0.10,hold=1,exit_at="open",lookback=1,trend=None,tf=20))]:
    t=pd.DataFrame(tr); t=t[t.entry_date>="2026-01-01"].copy(); t["ret%"]=(t.ret*100).round(2)
    print(f"\n=== 2026 trades: {label} (n={len(t)}, avg {t.ret.mean()*100:+.2f}%, total {((1+t.ret).prod()-1)*100:+.1f}%) ==="); print(t[["entry_date","exit_date","entry","exit","ret%","hold"]].to_string(index=False))
# per-year for headline S2
t=pd.DataFrame(mr(0.03,hold=5,exit_at="open",lookback=2,trend="above",tf=20)); t["yr"]=t.entry_date.dt.year
print("\n=== per-year S2 headline ==="); print(t.groupby("yr").agg(trades=("ret","size"),win=("ret",lambda x:(x>0).mean()*100),avg=("ret",lambda x:x.mean()*100),total=("ret",lambda x:((1+x).prod()-1)*100)).round(1).to_string())

# --- time to reclaim SMA20 after a <=-20% day ---
r1=pd.Series(C).pct_change().values
print("\n=== after each <= -20% day: sessions until first close back above SMA20, and SOXL return over that wait ===")
for i in np.where(r1<=-0.20)[0]:
    j=i+1
    while j<n and not (C[j]>SMA20[j]): j+=1
    if j<n: print(f"{idx[i].date()} ({r1[i]*100:.1f}%): reclaimed SMA20 after {j-i} sessions on {idx[j].date()}, price change over wait {(C[j]/C[i]-1)*100:+.1f}%, lowest close in between {(C[i+1:j+1].min()/C[i]-1)*100:+.1f}%")
    else: print(f"{idx[i].date()} ({r1[i]*100:.1f}%): not yet reclaimed ({n-1-i} sessions so far)")

# --- sizing table ---
eq=8218.70; px=C[-1]
print(f"\n=== position sizing at ${px:.2f}, equity ${eq:,.2f} (max {int(eq//px)} shares all-in) ===")
for frac in [0.2,0.25,0.33,0.5,0.75,1.0]:
    sh=int(eq*frac//px); notional=sh*px
    print(f"{frac*100:3.0f}% -> {sh:3d} sh  ${notional:8,.0f} | fee per round trip ${notional*0.005:6.2f} | loss on -10% day ${notional*0.10:7,.0f} ({notional*0.10/eq*100:4.1f}% of equity), -20% day ${notional*0.20:7,.0f} ({notional*0.20/eq*100:4.1f}%), -30% ${notional*0.30:7,.0f} ({notional*0.30/eq*100:4.1f}%)")
print("\n=== break-even win rate with 0.5% round-trip fee: w* = (L+0.5)/(G+L), G=avg gross win %, L=avg gross loss % ===")
for G,Lx in [(2,2),(3,3),(5,5),(8,8),(4,2),(6,3),(8,4),(10,5)]:
    print(f"G={G}% L={Lx}%: need win rate >= {(Lx+0.5)/(G+Lx)*100:.1f}%  (no-fee break-even {Lx/(G+Lx)*100:.1f}%)")
print("\n=== annual fee drag by frequency (0.5% of traded notional per round trip, full-position trades) ===")
for lab,k in [("1 round trip/day",250),("3/week",156),("1/week",52),("2/month",24),("1/month",12)]:
    print(f"{lab:18s}: {k*0.5:6.1f}% of position size per year")
