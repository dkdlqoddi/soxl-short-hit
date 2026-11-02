import sys, site; sys.path.insert(0, site.getusersitepackages())
sys.path.insert(0, sys.argv[1]+"/scripts")
from grid import *
S=sys.argv[1]; pd.set_option("display.width",250); pd.set_option("display.max_columns",40); pd.set_option("display.max_rows",500)
d=load_yf(f"{S}/data/soxl_1d_yf.csv"); O,H,L,C=[d[c].values for c in ["open","high","low","close"]]
def window(a,b): 
    m=(d.index>=a)&(d.index<=b); return O[m],H[m],L[m],C[m],(d.index[m][-1]-d.index[m][0]).days/365.25
def bh(c,yrs): r=c[-1]/c[0]*(1-0.0025)/(1+0.0025); return dict(total=round((r-1)*100,1),cagr=round((r**(1/yrs)-1)*100,1))
# ---- A. fixed windows, sizing N=100 (fully funded) and N=50 (funded to -50%)
wins=[("2016-10-24","2026-10-30","10y 2016-26"),("2022-01-03","2022-12-30","2022 crash"),("2023-01-03","2024-07-10","2023-24 rally"),
      ("2024-07-10","2025-04-08","2024H2-25Q1 crash"),("2025-04-08","2026-10-30","2025-26 rally"),("2026-01-02","2026-10-30","2026 YTD"),("2020-01-02","2020-12-31","2020")]
rows=[]
for a,b,lab in wins:
    o,h,l,c,yrs=window(a,b); B=bh(c,yrs)
    for N in (100,50):
        for mode,T,extra in RULES:
            eq,st,cy=simulate(o,h,l,c,T=T,mode=mode,N=N,**extra)
            cy=pd.DataFrame(cy)
            rows.append(dict(window=lab,N=N,rule=name(mode,T,extra),**metrics(eq,yrs),**st,
                             cyc_win=round(100*(cy.pnl>0).mean(),0) if len(cy) else np.nan, cyc_med=round(100*cy.ret.median(),2) if len(cy) else np.nan,
                             bh_total=B["total"],bh_cagr=B["cagr"]))
A=pd.DataFrame(rows); A.to_csv(f"{S}/data/A_windows.csv",index=False)
for lab in A.window.unique():
    sub=A[(A.window==lab)&(A.N==100)]
    print(f"\n===== {lab} | N=100 fully funded | B&H net {sub.bh_total.iloc[0]}% =====")
    print(sub.drop(columns=["window","N","bh_total","bh_cagr"]).to_string(index=False))
print("\n===== 10y, N=50 (cash runs out at -50%) =====")
print(A[(A.window=="10y 2016-26")&(A.N==50)].drop(columns=["window","N","bh_total","bh_cagr"]).to_string(index=False))
# ---- B. rolling 1y windows every 21 bars, 2016-10 .. 2025-10, N=100
m=(d.index>="2016-10-24"); o,h,l,c=O[m],H[m],L[m],C[m]; idx=d.index[m]; W=252; starts=range(0,len(c)-W,21)
rr=[]
for s0 in starts:
    oo,hh,ll,cc=o[s0:s0+W],h[s0:s0+W],l[s0:s0+W],c[s0:s0+W]
    rr.append(dict(start=idx[s0].date(),rule="buy&hold",total=(cc[-1]/cc[0]*(1-0.0025)/(1+0.0025)-1)*100,mdd=((cc/np.maximum.accumulate(cc)-1).min())*100))
    for mode,T,extra in RULES:
        if extra: continue
        eq,st,_=simulate(oo,hh,ll,cc,T=T,mode=mode,N=100,**extra)
        rr.append(dict(start=idx[s0].date(),rule=name(mode,T,extra),total=(eq[-1]/eq[0]-1)*100,mdd=(eq/np.maximum.accumulate(eq)-1).min()*100))
R=pd.DataFrame(rr); R.to_csv(f"{S}/data/B_rolling1y.csv",index=False)
g=R.groupby("rule",sort=False).agg(windows=("total","size"),median=("total","median"),p10=("total",lambda x:x.quantile(.1)),p90=("total",lambda x:x.quantile(.9)),
    worst=("total","min"),best=("total","max"),pos_pct=("total",lambda x:100*(x>0).mean()),mdd_med=("mdd","median"),mdd_worst=("mdd","min")).round(1)
print(f"\n===== rolling 1-year windows (start every 21 bars, {len(list(starts))} windows), N=100 =====")
print(g.to_string())
