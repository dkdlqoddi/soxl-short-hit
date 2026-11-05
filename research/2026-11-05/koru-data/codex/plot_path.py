from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent
KST = ZoneInfo('Asia/Seoul')
ET = ZoneInfo('America/New_York')
d = pd.read_csv(ROOT/'KORU_1m.csv')
d.index = pd.to_datetime(d.pop('timestamp'),utc=True).dt.tz_convert(KST)
d = d.loc['2026-11-04 08:43':'2026-11-05 09:59']
full = d.Close.reindex(pd.date_range(d.index[0],d.index[-1],freq='min'))
fig,axes = plt.subplots(2,1,figsize=(13,7.8),gridspec_kw={'height_ratios':[1.3,1]})
for ax in axes:
    ax.plot(full.index,full,color='#176b9b',lw=1.25,label='KORU 1-minute close')
    ax.axhline(11.01,color='#6b7280',ls='--',lw=1,label='Previous regular close: 11.01')
    ax.grid(alpha=.16)
    ax.set_ylabel('USD')
    ax.spines[['top','right']].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M',tz=KST))
axes[0].set_title('KORU | 2026-11-04 forecast review (KST; ET = KST - 14 hours)',loc='left',weight='bold')
axes[0].axhspan(11.30,11.41,color='#d97706',alpha=.10,label='Original bases: 11.30-11.41')
axes[0].axvspan(pd.Timestamp('2026-11-04 10:00',tz=KST),pd.Timestamp('2026-11-04 18:00',tz=KST),color='#9ca3af',alpha=.12)
axes[0].text(pd.Timestamp('2026-11-04 14:00',tz=KST),10.55,'No Yahoo US bars\n10:00-18:00 KST',ha='center',color='#6b7280',fontsize=9)
axes[0].legend(loc='lower left',ncol=2,frameon=False,fontsize=8)
axes[0].set_ylim(9.75,11.72)
axes[1].set_xlim(pd.Timestamp('2026-11-05 07:45',tz=KST),pd.Timestamp('2026-11-05 10:00',tz=KST))
axes[1].set_ylim(9.75,10.85)
axes[1].set_title('Expiry detail | Price from the labelled minute; extension does not affect scores',loc='left',fontsize=11)
for name,time,px,color,xy in [
 ('Codex','08:43',10.38,'#b91c1c',(-85,45)),
 ('Argon','08:55',10.3297,'#15803d',(-25,75)),
 ('Claude','09:10',10.3,'#7c3aed',(35,45)),
]:
    t=pd.Timestamp('2026-11-05 '+time,tz=KST)
    axes[1].scatter(t,px,color=color,zorder=5,s=28)
    axes[1].axvline(t,color=color,lw=.7,alpha=.35)
    axes[1].annotate(f'{name} {time}\n${px:.4f}',xy=(t,px),xytext=xy,textcoords='offset points',
                     fontsize=9,color=color,arrowprops={'arrowstyle':'-','color':color,'lw':.8})
axes[1].set_xlabel('KST (Nov 5 08:43 / 08:55 / 09:10 = Nov 4 18:43 / 18:55 / 19:10 EST)')
fig.text(.01,.008,'Yahoo Finance, prepost=True, auto_adjust=False | Retrieved Nov 5 13:22 KST | Missing minutes are not connected.',fontsize=8,color='#6b7280')
fig.tight_layout(rect=[0,.025,1,1])
fig.savefig(ROOT/'koru_path.png',dpi=160)
plt.close(fig)
