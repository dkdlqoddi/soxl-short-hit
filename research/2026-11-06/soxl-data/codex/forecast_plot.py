import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(ROOT/'forecast_matplotlib_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from zoneinfo import ZoneInfo

d=pd.read_csv(ROOT/'forecast_daily_features.csv')
dt=pd.to_datetime(d.timestamp_et,utc=True).dt.tz_convert('Asia/Seoul')
h=pd.read_csv(ROOT/'forecast_sessions_1h.csv')
q=pd.read_csv(ROOT/'forecast_raw/SOXL_5d_1m.csv')
t=pd.to_datetime(q.timestamp_utc,utc=True).dt.tz_convert('Asia/Seoul')
mask=(t>=pd.Timestamp('2026-11-05 23:30',tz='Asia/Seoul'))&(t<=pd.Timestamp('2026-11-06 10:00',tz='Asia/Seoul'))
fig,axes=plt.subplots(1,3,figsize=(16,4.8),layout='constrained')
ax=axes[0];ax.plot(dt.tail(45),d.close.tail(45),label='Regular close',color='#2859a3')
ax.plot(dt.tail(45),d.ma20.tail(45),label='20-session mean',color='#be8522')
ax.axhline(43.59,color='#a74343',ls='--',label='Base $43.59')
ax.set(title='SOXL: price trend',ylabel='USD',xlabel='KST date (daily bar label)');ax.legend(fontsize=8)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d',tz=ZoneInfo('Asia/Seoul')))
ax=axes[1];ax.plot(t[mask],q.close[mask],color='#2859a3',lw=1)
ax.axvspan(pd.Timestamp('2026-11-06 06:00',tz='Asia/Seoul'),pd.Timestamp('2026-11-06 10:00',tz='Asia/Seoul'),color='#d9e9dd',alpha=.5,label='After hours')
for price,color,label in [(40.87,'#333333','Regular close $40.87'),(43.59,'#a74343','Base $43.59')]:ax.axhline(price,color=color,ls='--',lw=1,label=label)
ax.set(title='Latest session: 1-minute closes',ylabel='USD',xlabel='KST');ax.legend(fontsize=8)
ax.xaxis.set_major_locator(mdates.HourLocator(interval=2,tz=ZoneInfo('Asia/Seoul')))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=ZoneInfo('Asia/Seoul')))
ax.set_xlabel('11/05 night to 11/06 morning (KST)')
ax=axes[2];sub=h[h.next_24h&(h.ratio20<1)&(h.ah_ret>=.01)].next_ah_ret.dropna()*100
ax.hist(sub,bins=np.arange(-30,22,2),color='#618ab9',alpha=.9,edgecolor='white')
ax.axvline(0,color='#333333',ls='--');ax.axvline(sub.median(),color='#a74343',label=f'Median {sub.median():.2f}%')
ax.set(title=f'Below MA20 + AH gain >=1% (N={len(sub)})',xlabel='Next after-hours return from AH price (%)',ylabel='Count');ax.legend(fontsize=8)
for ax in axes:ax.grid(alpha=.16)
fig.suptitle('SOXL 24-hour forecast diagnostics | price cutoff 2026-11-06 10:42 KST',fontsize=13)
fig.savefig(ROOT/'forecast_diagnostics.png',dpi=160)
plt.close(fig)
