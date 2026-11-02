import sys, site; sys.path.insert(0, site.getusersitepackages())
import numpy as np, pandas as pd

def load_yf(path):
    df = pd.read_csv(path, header=[0,1], index_col=0)
    df.columns = [c[0].lower() for c in df.columns]
    df.index = pd.to_datetime(df.index, utc=True) if "+" in str(df.index[0]) else pd.to_datetime(df.index)
    return df[["open","high","low","close","volume"]].dropna()

def simulate(O,H,L,C, T=0.03, mode="total", step=0.01, N=100, q=None, lot_usd=None, capital=8200.0, fee=0.0025,
             stop=None, trail=None, max_bars=None):
    """Grid-down buyer, always holding >=1 lot. Limit buy at last_fill*(1-step), repeated.
    Fills: TradingView intrabar assumption (up bar O-L-H-C, down bar O-H-L-C). Targets use raw avg price (fee excluded),
    so T means the same as in the Pine script. After a full exit the first lot is re-bought at the NEXT bar's open.
    Sizing: q shares fixed | lot_usd fixed dollars | else N: at each (re)start lot = cash/(N*price) shares
            (N=100 with 1% step => the infinite grid costs exactly the cash on hand; N=50 => cash runs out at -50%).
    Sell modes: total (all at avg*(1+T)), perlot (each lot at own*(1+T)), trail (arm at avg*(1+T), exit at peak*(1-trail)).
    stop: reset when close <= avg*(1-stop). max_bars: time exit."""
    n=len(C); cash=capital; lots=[]; limit=None; last=None; pending=True; armed=False; peak=0.0; cyc=0; qcur=q
    eq=np.empty(n); expo=np.empty(n); nbuy=nsell=0; maxlots=0; max_inv=0.0; nocash=0; realized=0.0; cycles=[]; fees=0.0; maxfills=0; fills_bar=0
    def shares_for(p): return (lot_usd/p) if lot_usd else qcur
    def avg():
        s=sum(x[1] for x in lots); return (sum(x[0]*x[1] for x in lots)/s if s>0 else 0.0, s)
    def sell_all(i,px):
        nonlocal cash,lots,realized,nsell,pending,armed,peak,fees
        a,s=avg(); pr=px*s*(1-fee); fees+=px*s*fee; pnl=pr-a*s*(1+fee); cash+=pr; realized+=pnl; nsell+=1
        cycles.append(dict(start=cyc,end=i,lots=len(lots),pnl=pnl,ret=pnl/(a*s*(1+fee)))); lots=[]; pending=True; armed=False; peak=0.0
    def buy(i,px):
        nonlocal cash,nbuy,last,limit,max_inv,maxlots,fees,fills_bar
        s=shares_for(px); cost=px*s*(1+fee)
        if s<=0 or cost>cash+1e-9: return False
        cash-=cost; fees+=px*s*fee; fills_bar+=1; lots.append([px,s]); nbuy+=1; last=px; limit=px*(1-step)
        inv=sum(x[0]*x[1] for x in lots); max_inv=max(max_inv,inv); maxlots=max(maxlots,len(lots)); return True
    for i in range(n):
        o,h,l,c=O[i],H[i],L[i],C[i]; fills_bar=0
        if pending:
            if q is None and lot_usd is None: qcur=cash/(N*o)
            buy(i,o); pending=False; cyc=i
        for ph in (("buy","sell") if c>=o else ("sell","buy")):
            if ph=="buy":
                if not lots or limit is None: continue
                first=True
                while limit>=l*(1-1e-12):
                    px=o if (first and o<limit) else limit; first=False
                    if not buy(i,px): break
            else:
                if not lots: continue
                a,s=avg()
                if mode=="total":
                    tgt=a*(1+T)
                    if o>=tgt: sell_all(i,o)
                    elif h>=tgt: sell_all(i,tgt)
                elif mode=="perlot":
                    keep=[]
                    for p,s_ in lots:
                        tgt=p*(1+T)
                        if o>=tgt or h>=tgt:
                            px=o if o>=tgt else tgt; pr=px*s_*(1-fee); fees+=px*s_*fee; pnl=pr-p*s_*(1+fee); cash+=pr; realized+=pnl
                            cycles.append(dict(start=cyc,end=i,lots=1,pnl=pnl,ret=pnl/(p*s_*(1+fee))))
                        else: keep.append([p,s_])
                    if len(keep)<len(lots): nsell+=1
                    lots=keep
                    if not lots: pending=True; limit=None
                elif mode=="trail":
                    tgt=a*(1+T)
                    if not armed and h>=tgt: armed=True; peak=h
                    if armed:
                        peak=max(peak,h); stp=peak*(1-trail)
                        if o<=stp: sell_all(i,o)
                        elif l<=stp: sell_all(i,stp)
        if lots and stop is not None:
            a,s=avg()
            if c<=a*(1-stop): sell_all(i,c)
        if lots and max_bars is not None and i-cyc>=max_bars: sell_all(i,c)
        s=sum(x[1] for x in lots); eq[i]=cash+s*c; expo[i]=s*c/eq[i]; maxfills=max(maxfills,fills_bar)
        if lots and cash < (lot_usd or qcur*c)*(1+fee): nocash+=1
    st=dict(nbuy=nbuy,nsell=nsell,maxlots=maxlots,max_inv=round(max_inv),nocash_pct=round(100*nocash/n,1),realized=round(realized),
            end_lots=len(lots),end_unreal=round(sum(x[1] for x in lots)*C[-1]-sum(x[0]*x[1] for x in lots)),expo=round(100*expo.mean(),1),fees=round(fees),maxfills=maxfills)
    return eq,st,cycles

def metrics(eq, years):
    eq=np.asarray(eq); ret=eq[-1]/eq[0]-1; dd=(eq/np.maximum.accumulate(eq)-1).min()
    cagr=(eq[-1]/eq[0])**(1/years)-1 if years>0 else np.nan
    peak=np.maximum.accumulate(eq); uw=eq<peak*0.999; longest=cur=0
    for u in uw: cur=cur+1 if u else 0; longest=max(longest,cur)
    return dict(total=round(ret*100,1),cagr=round(cagr*100,1),mdd=round(dd*100,1),uw_bars=longest)

RULES = [("total",t,{}) for t in (0.01,0.02,0.03,0.05,0.07,0.10,0.15,0.20,0.30)] + \
        [("perlot",t,{}) for t in (0.01,0.02,0.03,0.05,0.07,0.10,0.15,0.20)] + \
        [("trail",t,dict(trail=tr)) for t in (0.05,0.10) for tr in (0.03,0.05)] + \
        [("total",t,dict(stop=s)) for t in (0.05,0.10) for s in (0.20,0.30)] + \
        [("total",t,dict(max_bars=mb)) for t in (0.05,0.10) for mb in (20,60)]
def name(mode,T,extra):
    s=f"{mode} +{T*100:g}%"
    for k,v in extra.items(): s+=f" {k}={v*100:g}%" if k!="max_bars" else f" {k}={v}"
    return s
