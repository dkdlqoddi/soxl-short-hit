import sys, site; sys.path.insert(0, site.getusersitepackages())
sys.path.insert(0, sys.argv[1]+"/scripts")
from grid import *
S=sys.argv[1]; pd.set_option("display.width",250); pd.set_option("display.max_columns",40); pd.set_option("display.max_rows",500)
d=load_yf(f"{S}/data/soxl_1d_yf.csv"); h=load_yf(f"{S}/data/soxl_1h_yf.csv"); m5=load_yf(f"{S}/data/soxl_5m_yf.csv")
h.index=h.index.tz_convert("America/New_York"); m5.index=m5.index.tz_convert("America/New_York")
def arr(df): return [df[c].values for c in ["open","high","low","close"]]
CAND=[("total",0.03,{}),("total",0.05,{}),("total",0.07,{}),("total",0.10,{}),("total",0.20,{}),("perlot",0.05,{}),("perlot",0.10,{}),("perlot",0.15,{})]
# ---- C. timeframe check
print("===== C. same window, different bar sizes (N=100) =====")
for (a,b,lab,frames) in [("2024-10-31","2026-10-30","2y",[("1d",d),("1h",h)]),("2026-08-07","2026-10-30","60d",[("1d",d),("1h",h),("5m",m5)])]:
    rows=[]
    for tf,df in frames:
        ix=df.index.tz_localize(None) if df.index.tz is not None else df.index
        msk=(ix>=a)&(ix<=b+" 23:59"); sub=df[msk]; o,hh,l,c=arr(sub); yrs=max((ix[msk][-1]-ix[msk][0]).days/365.25,1/365)
        for mode,T,ex in CAND:
            eq,st,_=simulate(o,hh,l,c,T=T,mode=mode,N=100)
            rows.append(dict(window=lab,tf=tf,rule=name(mode,T,ex),total=round((eq[-1]/eq[0]-1)*100,1),mdd=round((eq/np.maximum.accumulate(eq)-1).min()*100,1),nbuy=st["nbuy"],nsell=st["nsell"],maxlots=st["maxlots"],expo=st["expo"]))
    R=pd.DataFrame(rows); print(R.pivot_table(index="rule",columns="tf",values=["total","mdd","nbuy","nsell","maxlots"],sort=False).to_string()); R.to_csv(f"{S}/data/C_timeframes_{lab}.csv",index=False)
# ---- D. calendar-year breakdown, continuous 2016-10-24 run, N=100
print("\n===== D. calendar-year returns of a continuous run from 2016-10-24 (N=100) =====")
msk=d.index>="2016-10-24"; sub=d[msk]; o,hh,l,c=arr(sub)
yr=pd.DataFrame(index=sub.index)
yr["buy&hold"]=c/c[0]
for mode,T,ex in CAND:
    eq,st,_=simulate(o,hh,l,c,T=T,mode=mode,N=100); yr[name(mode,T,ex)]=eq/eq[0]
ye=yr.groupby(yr.index.year).last(); yr_ret=(ye/ye.shift(1).fillna(1.0)-1)*100
yr_ret.index.name="year"; print(yr_ret.round(1).to_string()); yr_ret.round(2).to_csv(f"{S}/data/D_yearly.csv")
yr.to_csv(f"{S}/data/D_equity_curves.csv")
# ---- E. sizing depth N and step sensitivity, 10y
print("\n===== E. lot size (N) sensitivity, 10y 2016-26 =====")
rows=[]
for N in (25,33,50,70,100,150):
    for mode,T,ex in CAND:
        eq,st,_=simulate(o,hh,l,c,T=T,mode=mode,N=N); yrs=(sub.index[-1]-sub.index[0]).days/365.25
        rows.append(dict(N=N,rule=name(mode,T,ex),**metrics(eq,yrs),nocash=st["nocash_pct"],expo=st["expo"],maxlots=st["maxlots"]))
E=pd.DataFrame(rows); print(E.pivot_table(index="rule",columns="N",values=["total","mdd","nocash"],sort=False).to_string()); E.to_csv(f"{S}/data/E_sizing.csv",index=False)
print("\n===== F. step sensitivity (N scaled so the infinite grid costs the cash: N=100*step/1%), 10y =====")
rows=[]
for step in (0.005,0.01,0.02,0.03,0.05):
    for mode,T,ex in CAND:
        eq,st,_=simulate(o,hh,l,c,T=T,mode=mode,N=int(round(1/step)),step=step)
        rows.append(dict(step=step,rule=name(mode,T,ex),**metrics(eq,yrs),nocash=st["nocash_pct"],expo=st["expo"],nbuy=st["nbuy"],maxlots=st["maxlots"]))
F=pd.DataFrame(rows); print(F.pivot_table(index="rule",columns="step",values=["total","mdd","nbuy"],sort=False).to_string()); F.to_csv(f"{S}/data/F_step.csv",index=False)
# ---- G. rolling 2y windows
print("\n===== G. rolling 2-year windows (start every 21 bars), N=100 =====")
W=504; rr=[]
for s0 in range(0,len(c)-W,21):
    oo,h2,ll,cc=o[s0:s0+W],hh[s0:s0+W],l[s0:s0+W],c[s0:s0+W]
    rr.append(dict(rule="buy&hold",total=(cc[-1]/cc[0]-1)*100,mdd=((cc/np.maximum.accumulate(cc)-1).min())*100))
    for mode,T,ex in CAND:
        eq,st,_=simulate(oo,h2,ll,cc,T=T,mode=mode,N=100); rr.append(dict(rule=name(mode,T,ex),total=(eq[-1]/eq[0]-1)*100,mdd=(eq/np.maximum.accumulate(eq)-1).min()*100))
R=pd.DataFrame(rr); g=R.groupby("rule",sort=False).agg(n=("total","size"),median=("total","median"),p10=("total",lambda x:x.quantile(.1)),worst=("total","min"),pos_pct=("total",lambda x:100*(x>0).mean()),mdd_med=("mdd","median"),mdd_worst=("mdd","min")).round(1)
print(g.to_string()); g.to_csv(f"{S}/data/G_rolling2y.csv")
