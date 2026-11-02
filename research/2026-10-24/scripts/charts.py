import sys, site; sys.path.insert(0, site.getusersitepackages())
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.font_manager as fm
from matplotlib.ticker import FuncFormatter
out, charts, btpath = sys.argv[1:4]
ko=None
for f in fm.findSystemFonts():
    try: nm=fm.FontProperties(fname=f).get_name()
    except Exception: continue
    if any(k in nm for k in ["Nanum","Noto Sans CJK","Noto Sans KR","Malgun","AppleGothic","UnDotum","Baekmuk","Source Han"]): ko=nm; break
KO = ko is not None
if KO: plt.rcParams["font.family"]=ko
plt.rcParams["axes.unicode_minus"]=False
print("korean font:", ko)
T=lambda k,e: k if KO else e
SURF,INK,INK2,MUTED,GRID,AXIS="#fcfcfb","#0b0b0b","#52514e","#898781","#e1e0d9","#c3c2b7"
S1,S2,S3="#2a78d6","#eb6834","#1baf7a"
def style(ax):
    ax.set_facecolor(SURF)
    for s in ["top","right"]: ax.spines[s].set_visible(False)
    for s in ["left","bottom"]: ax.spines[s].set_color(AXIS); ax.spines[s].set_linewidth(0.8)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
def title(ax, t, sub=None):
    ax.set_title(t, loc="left", fontsize=12, color=INK, pad=18 if sub else 10, fontweight="semibold")
    if sub: ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
def legend(ax, loc="upper left"):
    lg=ax.legend(loc=loc, frameon=False, fontsize=9); [t.set_color(INK2) for t in lg.get_texts()]
# load backtest definitions
src=open(btpath).read().split("t0=time.time()")[0]; ns={}; exec(compile(src,"bt_defs","exec"),ns)
C,O,idx,n,SMA20,dip_limit,mr=[ns[k] for k in ["C","O","idx","n","SMA20","dip_limit","mr"]]
full=pd.read_csv(f"{out}/soxl_daily_nasdaq.csv", parse_dates=["date"]).set_index("date")
full["sma20"]=full.close.rolling(20).mean(); full["sma50"]=full.close.rolling(50).mean()

# ---- chart 1: price + SMAs ----
w=full.iloc[-65:]
fig,ax=plt.subplots(figsize=(9.5,5),dpi=160,facecolor=SURF); style(ax)
ax.plot(w.index,w.close,color=S1,lw=2,solid_capstyle="round",label=T("SOXL 종가","SOXL close"))
ax.plot(w.index,w.sma20,color=S2,lw=2,label=T("20일 이동평균","20-day SMA"))
ax.plot(w.index,w.sma50,color=S3,lw=2,label=T("50일 이동평균","50-day SMA"))
last=w.index[-1]
for col,c,lab,dy in [("close",S1,T("종가","close"),0),("sma20",S2,"SMA20",7),("sma50",S3,"SMA50",-7)]:
    y=w[col].iloc[-1]; ax.scatter([last],[y],s=42,color=c,edgecolor=SURF,linewidth=2,zorder=5)
    ax.annotate(f"{lab} ${y:,.0f}",(last,y),xytext=(10,dy),textcoords="offset points",va="center",fontsize=9,color=INK2,
                arrowprops=dict(arrowstyle="-",color=MUTED,lw=0.6,shrinkA=0,shrinkB=3))
pk=w.close.idxmax(); ax.annotate(T(f"고점 ${w.close.max():.0f} (10/5)",f"peak ${w.close.max():.0f} (Oct 5)"),(pk,w.close.max()),xytext=(-70,10),textcoords="offset points",fontsize=9,color=INK2,arrowprops=dict(arrowstyle="-",color=MUTED,lw=0.6))
d22=pd.Timestamp("2026-10-22"); ax.annotate(T("10/22 -20.5%\nLam 공급 경고·유가·금리",f"Oct 22 -20.5%\nLam supply warning, oil, rates"),(d22,full.loc[d22,"close"]),xytext=(-175,28),textcoords="offset points",fontsize=9,color=INK2,va="bottom",arrowprops=dict(arrowstyle="-",color=MUTED,lw=0.6))
d20=pd.Timestamp("2026-10-20"); ax.annotate(T("$97 지정가 매수 (미체결)","$97 limit buy (no fill)"),(d20,97),xytext=(-130,40),textcoords="offset points",fontsize=9,color=INK2,arrowprops=dict(arrowstyle="-",color=MUTED,lw=0.6))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v:.0f}"))
title(ax, T("SOXL 최근 65거래일: 고점 대비 -49%, 20·50일선보다 35% 아래","SOXL last 65 sessions: -49% from peak, 35% below 20/50-day SMAs"), T("2026-10-23 종가 $83.56 · 출처: Nasdaq 일별 시세","Close $83.56 on 2026-10-23 · source: Nasdaq daily data"))
legend(ax); fig.tight_layout(); fig.savefig(f"{charts}/01_price_sma.png",facecolor=SURF); plt.close(fig)

# ---- chart 2: hold period vs avg net per trade ----
holds=[0,1,2,3,5]; fig,ax=plt.subplots(figsize=(8.5,4.8),dpi=160,facecolor=SURF); style(ax)
ax.axhline(0,color=AXIS,lw=1)
vals={}
for dsc,c,lab in [(0.03,S1,T("-3% 지정가","-3% limit"),),(0.05,S2,T("-5% 지정가","-5% limit")),(0.07,S3,T("-7% 지정가","-7% limit"))]:
    ys=[]
    for hd in holds:
        t=pd.DataFrame(dip_limit(dsc,hold=hd)); ys.append(t.ret.mean()*100)
    vals[dsc]=ys; ax.plot(holds,ys,color=c,lw=2,marker="o",ms=7,mec=SURF,mew=1.5,label=lab)
ax.set_xticks(holds); ax.set_xticklabels([T("당일 종가","same close"),T("1일 후","+1"),T("2일 후","+2"),T("3일 후","+3"),T("5일 후","+5")])
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"{v:+.1f}%"))
ax.annotate(T("다음날 종가 매도: 세 설정 모두 -0.5~-0.6%/거래","sell next close: all three -0.5 to -0.6% per trade"),(1,vals[0.05][1]),xytext=(25,-38),textcoords="offset points",fontsize=9,color=INK2,arrowprops=dict(arrowstyle="-",color=MUTED,lw=0.6))
ax.set_ylabel(T("거래당 평균 순수익 (수수료 0.5% 차감)","avg net return per trade (after 0.5% fee)"),fontsize=9,color=INK2)
title(ax, T("지정가 딥 매수 후 보유기간별 거래당 평균 순수익","Dip limit-buy: average net return per trade by holding period"), T("2016-10 ~ 2026-10, 전일 종가 대비 할인 지정가 체결 가정, 매도는 해당일 종가 · 5일 보유도 최대낙폭 -92~-98%","2016-10 to 2026-10, fill when low touches limit, exit at close · 5-day hold still has -92 to -98% max drawdown"))
legend(ax,"lower right"); fig.tight_layout(); fig.savefig(f"{charts}/02_hold_vs_net.png",facecolor=SURF); plt.close(fig)

# ---- chart 3: equity curves (log) ----
start=200; dates=idx[start:]
def eq_curve(trades):
    s=pd.Series(1.0,index=dates); e=1.0
    for t in trades:
        if t["exit_date"]<dates[0]: continue
        e*= (1+t["ret"]); s.loc[t["exit_date"]:]=e
    return s
bh=pd.Series(C[start:]/C[start],index=dates)
s2=eq_curve(mr(0.03,hold=5,exit_at="open",lookback=2,trend="above",tf=20))
us=eq_curve([t for t in dip_limit(0.03,hold=1) if t["entry_date"]>=dates[0]])
fig,ax=plt.subplots(figsize=(9.5,5),dpi=160,facecolor=SURF); style(ax); ax.set_yscale("log")
for s,c,lab in [(bh,S1,T("SOXL 보유만 하기","SOXL buy & hold")),(s2,S2,T("추세 위 눌림목 5일 보유 (S2)","Pullback in uptrend, 5-day hold (S2)")),(us,S3,T("-3% 지정가 → 다음날 종가 매도 (현재 방식)","-3% limit → sell next close (current style)"))]:
    ax.plot(s.index,s.values,color=c,lw=2,label=lab)
    y=s.iloc[-1]; ax.scatter([s.index[-1]],[y],s=42,color=c,edgecolor=SURF,linewidth=2,zorder=5)
    dy={S1:10,S2:-10,S3:0}[c]; nm={S1:T("보유만","hold"),S2:"S2",S3:T("현재 방식","current")}[c]
    txt=(f"{nm} ×{y:.3f} ({(y-1)*100:+.1f}%)" if y<1 else f"{nm} ×{y:.0f}")
    ax.annotate(txt,(s.index[-1],y),xytext=(12,dy),textcoords="offset points",va="center",fontsize=9,color=INK2,arrowprops=dict(arrowstyle="-",color=MUTED,lw=0.6,shrinkA=0,shrinkB=3))
ax.set_ylim(0.0005,300); ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p: f"×{v:g}"))
ax.set_ylabel(T("자본 배수 (로그, 시작=1)","capital multiple (log, start=1)"),fontsize=9,color=INK2)
title(ax, T("세 가지 방식의 자본 곡선, 2017-08 ~ 2026-10 (수수료 0.5% 반영)","Equity curves of three approaches, 2017-08 to 2026-10 (0.5% fee)"), T("전 자본 투입 가정 · 보유만 하기는 최대낙폭 -91%, S2는 -46%, 현재 방식은 -99.8%","full capital each trade · max drawdown: buy&hold -91%, S2 -46%, current style -99.8%"))
legend(ax); fig.tight_layout(); fig.savefig(f"{charts}/03_equity_curves.png",facecolor=SURF); plt.close(fig)

# ---- chart 4: hourly profile (2 panels) ----
hp=pd.read_csv(f"{out}/hourly_profile.csv",index_col=0)
reg=hp.loc[["09:30","10:30","11:30","12:30","13:30","14:30","15:30"]]
labels=[f"{k}\n({et} ET)" for k,et in zip(reg["KST(EDT)"],reg.index)]
fig,axes=plt.subplots(1,2,figsize=(10,4.4),dpi=160,facecolor=SURF)
for ax,col,ttl,fmt in [(axes[0],"vol_share_%",T("정규장 거래량 비중 (중앙값 기준)","share of regular-session volume (median)"),"{:.0f}%"),(axes[1],"mean_range_pct",T("시간대별 평균 고저 변동폭","mean high-low range per hour"),"{:.1f}%")]:
    style(ax); x=np.arange(len(reg)); ax.bar(x,reg[col],width=0.5,color=S1)
    for xi,v in zip(x,reg[col]): ax.text(xi,v,fmt.format(v),ha="center",va="bottom",fontsize=9,color=INK2)
    ax.set_xticks(x); ax.set_xticklabels(labels,fontsize=8); ax.set_title(ttl,loc="left",fontsize=10.5,color=INK,fontweight="semibold")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"{v:.0f}%"))
fig.suptitle(T("SOXL 시간대별 특성, 최근 60거래일 (한국시간 기준, 서머타임)","SOXL by hour, last 60 sessions (KST, daylight time)"),x=0.01,ha="left",fontsize=12,color=INK,fontweight="semibold")
fig.tight_layout(); fig.savefig(f"{charts}/04_hourly_profile.png",facecolor=SURF); plt.close(fig)
print("charts written")
