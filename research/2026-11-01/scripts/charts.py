import sys, site; sys.path.insert(0, site.getusersitepackages())
sys.path.insert(0, sys.argv[1]+"/scripts")
from grid import *
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.font_manager as fm, os
S=sys.argv[1]
for p in ("/home/dkdlqoddi/.local/share/fonts/malgun.ttf",):
    if os.path.exists(p): fm.fontManager.addfont(p); plt.rcParams["font.family"]="Malgun Gothic"
plt.rcParams.update({"axes.unicode_minus":False,"axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#8a8a85","axes.labelcolor":"#3a3a37",
                     "xtick.color":"#5a5a56","ytick.color":"#5a5a56","grid.color":"#e4e4e0","figure.facecolor":"#fcfcfb","axes.facecolor":"#fcfcfb","font.size":10})
BLUE,ORANGE,AQUA,YELLOW,GRAY="#2a78d6","#eb6834","#1baf7a","#eda100","#9a9a95"
# 1. equity curves 2016-2026
eqc=pd.read_csv(f"{S}/data/D_equity_curves.csv",index_col=0,parse_dates=True)*8200
fig,ax=plt.subplots(figsize=(11,5.6))
series=[("buy&hold","SOXL 그냥 보유",GRAY,1.2),("total +20%","전체 평단 +20%",ORANGE,1.8),("total +7%","전체 평단 +7%",BLUE,1.8),("perlot +15%","로트별 +15%",AQUA,1.8),("perlot +5%","로트별 +5%",YELLOW,1.8)]
for col,lab,c,lw in series:
    ax.plot(eqc.index,eqc[col],color=c,lw=lw,label=lab)
    y=eqc[col].iloc[-1]; ax.annotate(f"{lab}  ${y:,.0f}",(eqc.index[-1],y),xytext=(6,0),textcoords="offset points",va="center",fontsize=9,color="#3a3a37")
ax.set_yscale("log"); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_: f"${v:,.0f}"))
ax.grid(True,axis="y",lw=0.6); ax.set_title("1% 그리드 매수, 매도 규칙별 자산 곡선 (2016-10 → 2026-10, $8,200 시작, 왕복 수수료 0.5%, 로그 눈금)",loc="left",fontsize=11)
ax.set_ylabel("계좌 자산 (달러)"); ax.legend(frameon=False,loc="upper left",ncol=5,fontsize=9)
fig.subplots_adjust(right=0.80); fig.savefig(f"{S}/charts/01_equity_curves.png",dpi=150,bbox_inches="tight"); plt.close(fig)
# 2. rolling 2y distribution
g=pd.read_csv(f"{S}/data/G_rolling2y.csv",index_col=0)
R=pd.read_csv(f"{S}/data/B_rolling1y.csv")  # for p90 we recompute from raw 2y runs below
d=load_yf(f"{S}/data/soxl_1d_yf.csv"); sub=d[d.index>="2016-10-24"]; o,h,l,c=[sub[k].values for k in ["open","high","low","close"]]
CAND=[("buy&hold",None,None),("total",0.03,None),("total",0.05,None),("total",0.07,None),("total",0.10,None),("total",0.20,None),("perlot",0.05,None),("perlot",0.10,None),("perlot",0.15,None)]
W=504; dist={}
for mode,T,_ in CAND:
    key="buy&hold" if mode=="buy&hold" else name(mode,T,{}); vals=[]
    for s0 in range(0,len(c)-W,21):
        cc=c[s0:s0+W]
        if mode=="buy&hold": vals.append((cc[-1]/cc[0]-1)*100)
        else:
            eq,_,_=simulate(o[s0:s0+W],h[s0:s0+W],l[s0:s0+W],cc,T=T,mode=mode,N=100); vals.append((eq[-1]/eq[0]-1)*100)
    dist[key]=np.array(vals)
labels={"buy&hold":"SOXL 그냥 보유","total +3%":"전체 평단 +3%","total +5%":"전체 평단 +5%","total +7%":"전체 평단 +7%","total +10%":"전체 평단 +10%","total +20%":"전체 평단 +20%","perlot +5%":"로트별 +5%","perlot +10%":"로트별 +10%","perlot +15%":"로트별 +15%"}
fig,ax=plt.subplots(figsize=(10,5.2)); keys=list(dist.keys())[::-1]; XMAX=160
for yi,k in enumerate(keys):
    v=dist[k]; p10,p50,p90,lo=np.percentile(v,10),np.median(v),np.percentile(v,90),v.min()
    col=GRAY if k=="buy&hold" else (BLUE if k.startswith("total") else AQUA)
    ax.barh(yi,min(p90,XMAX)-p10,left=p10,height=0.5,color=col,alpha=0.35,edgecolor="none")
    ax.plot([p50],[yi],marker="o",ms=8,color=col,mec="#fcfcfb",mew=1.5); ax.plot([lo],[yi],marker="|",ms=14,color=col,mew=2)
    ax.annotate(f"중앙값 {p50:+.0f}%   최악 {lo:+.0f}%",(XMAX+3,yi),va="center",fontsize=9,color="#3a3a37",annotation_clip=False)
    if p90>XMAX: ax.annotate(f"▶ 상위10% {p90:+.0f}%",(XMAX-2,yi+0.33),fontsize=8,color="#5a5a56",ha="right")
ax.set_yticks(range(len(keys))); ax.set_yticklabels([labels[k] for k in keys]); ax.set_xlim(-100,XMAX); ax.axvline(0,color="#8a8a85",lw=0.8)
ax.grid(True,axis="x",lw=0.6); ax.set_xlabel("2년 수익률 (%) — 막대: 하위10%~상위10%, 점: 중앙값, 세로선: 최악의 시작 시점")
ax.set_title("시작 시점을 21거래일씩 옮긴 96개의 2년 구간에서 본 수익률 분포 (2016-10 → 2026-10, N=100 완전 자금)",loc="left",fontsize=11)
fig.subplots_adjust(right=0.78); fig.savefig(f"{S}/charts/02_rolling_2y.png",dpi=150,bbox_inches="tight"); plt.close(fig)
# 3. crash zoom 2024-07-10 -> 2025-12-31 (two panels, no dual axis)
m=(d.index>="2024-07-10")&(d.index<="2025-12-31"); w=d[m]; o,h,l,c=[w[k].values for k in ["open","high","low","close"]]
fig,(a1,a2)=plt.subplots(2,1,figsize=(11,7),sharex=True,gridspec_kw=dict(height_ratios=[1,1.3],hspace=0.12))
a1.plot(w.index,c,color=GRAY,lw=1.4); a1.set_yscale("log"); a1.set_ylabel("SOXL 종가 (달러, 로그)"); a1.grid(True,axis="y",lw=0.6)
a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_: f"${v:,.0f}")); a1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
a1.set_title("2024-07 고점 → 2025-04 저점(-88%) → 회복 구간: 그리드는 바닥에서 로트가 가장 많다",loc="left",fontsize=11)
a1.set_yticks([8,10,20,30,50,80]); a1.set_ylim(7,90)
ends=[]
for mode,T,lab,col in [("total",0.07,"전체 평단 +7%",BLUE),("total",0.03,"전체 평단 +3%",ORANGE),("perlot",0.15,"로트별 +15%",AQUA),("perlot",0.05,"로트별 +5%",YELLOW)]:
    eq,st,_=simulate(o,h,l,c,T=T,mode=mode,N=100); a2.plot(w.index,eq,color=col,lw=1.8,label=lab); ends.append((eq[-1],lab))
ends.sort(); ymin,ymax=a2.get_ylim(); gap=(ymax-ymin)*0.045; ys=[]
for y,lab in ends:
    yy=y if not ys else max(y,ys[-1]+gap); ys.append(yy)
    a2.annotate(f"{lab} ${y:,.0f}",(w.index[-1],yy),xytext=(6,0),textcoords="offset points",va="center",fontsize=9,color="#3a3a37")
a2.axhline(8200,color="#8a8a85",lw=0.8,ls="--"); a2.set_ylabel("계좌 자산 (달러)"); a2.grid(True,axis="y",lw=0.6); a2.legend(frameon=False,ncol=4,fontsize=9,loc="lower left")
a2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_: f"${v:,.0f}"))
fig.subplots_adjust(right=0.82); fig.savefig(f"{S}/charts/03_crash_2024_25.png",dpi=150,bbox_inches="tight"); plt.close(fig)
print("charts done")
