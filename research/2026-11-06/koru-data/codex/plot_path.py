"""Create a standalone KST/EST path figure from the saved minute bars."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(ROOT/'mpl-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
from zoneinfo import ZoneInfo
import pandas as pd

font=FontProperties(fname='/home/dkdlqoddi/.local/share/fonts/NanumGothic.ttf')
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':10})
def t(s):return pd.Timestamp(s,tz='Asia/Seoul')
d=pd.read_csv(ROOT/'KORU_1m.csv',index_col=0)
d.index=pd.to_datetime(d.index,utc=True).tz_convert('Asia/Seoul')
d=d[(d.index>=t('2026-11-05 07:31'))&(d.index<t('2026-11-06 09:44'))&(d.index.second==0)]
fig,ax=plt.subplots(figsize=(13,6),layout='constrained')
groups=d.index.to_series().diff().gt(pd.Timedelta(minutes=1)).cumsum()
for _,part in d.groupby(groups):
 ax.plot(part.index,part.Close,color='#174f89',lw=1.25)
ax.axhspan(10.1,10.7,color='#f5bb60',alpha=.2,label='세 모델 중심 예상가의 합집합 $10.10~10.70')
ax.axhline(10.43,color='#777777',lw=.8,ls=':',label='직전 정규장 종가 $10.43')
ax.axhline(8.8,color='#ad3e3e',lw=1,ls='--',label='제시된 가장 낮은 하방 가격 $8.80')
ax.axvspan(t('2026-11-05 10:00'),t('2026-11-05 18:00'),color='#dedede',alpha=.6)
ax.text(t('2026-11-05 14:00'),7.6,'공급자 관측 공백\n한국장 결과는 다음 프리마켓에서 확인',ha='center',color='#555555')
ax.axvspan(t('2026-11-06 07:40'),t('2026-11-06 09:44'),color='#d6e8f5',alpha=.5,label='마지막 만기 이후: 채점 제외')
events=[('2026-11-05 09:06',10.21,'하방선 이탈\n11/5 09:06 KST\n11/4 19:06 EST',25,-55),
 ('2026-11-05 23:30',8.915,'미국 개장 $8.915\n11/5 23:30 KST\n11/5 09:30 EST',-120,45),
 ('2026-11-06 07:39',6.38,'만기 대용가 $6.34~6.38\n11/6 07:31~07:40 KST\n11/5 17:31~17:40 EST',-115,120)]
for when,price,label,dx,dy in events:
 ax.scatter(t(when),price,s=24,zorder=5,color='#a42d35')
 ax.annotate(label,(t(when),price),xytext=(dx,dy),textcoords='offset points',fontsize=9,
             arrowprops={'arrowstyle':'-','color':'#666666'})
ax.set_ylim(5.75,11.1)
ax.set_xlim(t('2026-11-05 07:00'),t('2026-11-06 10:00'))
ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[8,12,16,20,0,4,8],tz=ZoneInfo('Asia/Seoul')))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M',tz=ZoneInfo('Asia/Seoul')))
ax.set_xlabel('한국시간 KST (UTC+9) · 봉의 시작 시각; 만기 가격은 마지막 완료봉 종가')
ax.set_ylabel('KORU 가격 (USD)')
sec=ax.secondary_xaxis('top')
sec.xaxis.set_major_locator(mdates.HourLocator(byhour=[18,22,2,6,10,14,18],tz=ZoneInfo('America/New_York')))
sec.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M',tz=ZoneInfo('America/New_York')))
sec.set_xlabel('미국 동부시간 EST (UTC-5)')
ax.grid(alpha=.17)
ax.legend(loc='lower left',fontsize=8)
fig.suptitle('KORU 2026-11-05 회차 복기: 방향 적중, 하락폭 과소평가',fontweight='bold')
fig.savefig(ROOT/'koru_path.png',dpi=160)
