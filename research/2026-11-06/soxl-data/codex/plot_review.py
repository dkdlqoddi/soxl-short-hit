from pathlib import Path
import os
OUT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(OUT/'matplotlib-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from zoneinfo import ZoneInfo

s=pd.read_csv(OUT/'SOXL_1m.csv',index_col=0)
s.index=pd.to_datetime(s.index,utc=True).tz_convert('Asia/Seoul')
s=s.loc['2026-11-04 23:30':'2026-11-06 06:00'].dropna(subset=['close'])
fig,ax=plt.subplots(figsize=(13.2,6.3))
fig.patch.set_facecolor('#f6f8fb');ax.set_facecolor('#ffffff')
groups=(s.index.to_series().diff()>pd.Timedelta(minutes=2)).cumsum()
for _,seg in s.groupby(groups.to_numpy()):
    ax.plot(seg.index,seg.close,color='#224f91',linewidth=1.5)
for price,label,color in [(73.12,'Prior regular close 73.12','#6b7280'),
                          (70.03,'Reference open 70.03 (Codex 70.00)','#5a6978'),
                          (67.26,'Invalidation 67.26','#c57526')]:
    ax.axhline(price,color=color,lw=.9,ls='--',alpha=.7)
    ax.text(s.index[-1],price+.15,label,ha='right',fontsize=9,color=color)
points=[('2026-11-05 01:00',64.574997,'Two 15m closes below 67.26\n11/05 01:00 KST / 11/04 11:00 EST',(-5,-48)),
        ('2026-11-05 23:30',56.95,'Claude / Argon expiry: 56.95\n11/05 23:30 KST / 11/05 09:30 EST',(-220,65)),
        ('2026-11-06 00:05',51.169998,'Codex expiry proxy: 51.17\n11/06 00:04–00:05 KST / 11/05 10:04–10:05 EST',(-260,-50))]
for t,p,label,offset in points:
    ts=pd.Timestamp(t,tz='Asia/Seoul')
    ax.scatter([ts],[p],color='#c84040',s=40,zorder=5)
    ax.annotate(label,(ts,p),xytext=offset,textcoords='offset points',fontsize=9,
                arrowprops={'arrowstyle':'-','color':'#7c8795'},color='#26364a')
ax.axvspan(pd.Timestamp('2026-11-05 10:00',tz='Asia/Seoul'),
           pd.Timestamp('2026-11-05 18:00',tz='Asia/Seoul'),color='#eef1f5')
ax.text(pd.Timestamp('2026-11-05 14:00',tz='Asia/Seoul'),46,'U.S. session closed\nNo price interpolation',ha='center',fontsize=9,color='#78818f')
ax.set_title('SOXL: 2026-11-05 forecast review',loc='left',fontsize=17,fontweight='bold',pad=20)
ax.set_ylabel('USD');ax.set_ylim(36,79)
ax.xaxis.set_major_locator(mdates.HourLocator(interval=4,tz=ZoneInfo('Asia/Seoul')))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M',tz=ZoneInfo('Asia/Seoul')))
ax.set_xlabel('KST (EST = KST minus 14 hours)')
ax.spines[['top','right']].set_visible(False)
ax.grid(axis='y',alpha=.15)
fig.text(.08,.015,'Source: archived Yahoo 1m bars, retrieved 2026-11-06 09:44 KST. Line = minute closes; expiry markers follow each note’s rule.',fontsize=8,color='#667085')
fig.tight_layout(rect=(0,.035,1,1))
fig.savefig(OUT/'actual_path.png',dpi=170)
print(OUT/'actual_path.png')
