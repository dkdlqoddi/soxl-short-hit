"""Reproduce as-of scores and path diagnostics from the saved CSV files."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
KST='Asia/Seoul'
ET='America/New_York'

def dump(name,data):
 (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def ts(s): return pd.Timestamp(s,tz=KST)
def load(name,interval='1m'):
 d=pd.read_csv(ROOT/f'{name}_{interval}.csv',index_col=0)
 d.index=pd.to_datetime(d.index,utc=True).tz_convert(KST)
 if interval=='1m':
  # Yahoo may append a live quote with seconds to its minute series.
  d=d[(d.index.second==0)&(d.index.microsecond==0)]
 return d.sort_index()
def quote(d,when):
 # A bar stamped 07:33 may contain information until 07:33:59.
 # Only completed bars are available for an as-of price without tick data.
 s=d[(d.index+pd.Timedelta(minutes=1)<=when)&d.Close.notna()]
 t=s.index[-1]; r=s.iloc[-1]
 return dict(price=float(r.Close),bar_start_kst=str(t),bar_start_est=str(t.tz_convert(ET)),
    bar_end_kst=str(t+pd.Timedelta(minutes=1)),
    age_from_bar_end_seconds=(when-t-pd.Timedelta(minutes=1)).total_seconds(),
    volume=float(r.Volume),ohlc={k:float(r[k]) for k in ['Open','High','Low','Close']})

MODELS=[
 dict(model='Claude Fable Max',slug='claude',base_time='2026-11-05 07:38:00',base_price=10.62,
      expiry='2026-11-06 07:40:00',up_prob=45,center=[10.1,10.7],full_range=[8.8,11.5],
      regular_call='상승 소폭 우세·약 55%',call='하락 소폭 우세 (상승 약 45%)',
      scenarios=[dict(name='A',prob=30,range=[10.8,11.5]),dict(name='B',prob=28,range=[10.4,10.8]),
                 dict(name='C',prob=29,range=[9.6,10.4]),dict(name='D',prob=13,range=[8.8,9.6])],
      downside_levels=[10.225],upside_levels=[10.85],
      other_conditions='코스피 5,570 아래+외국인 순매도 시 하락 강화; 5,620 위+반도체 회복 시 상승 전환. SOXX 첫 1시간 반등 실패.'),
 dict(model='Codex Astra Max',slug='codex',base_time='2026-11-05 07:33:38',base_price=10.60,
      expiry='2026-11-06 07:33:38',up_prob=45,center=[10.30,10.55],full_range=[9.2,11.8],
      regular_call='중립, 중심 -1.25~+1.15%',call='중립에 가까운 약한 하락 우세 (상승 약 45%)',
      scenarios=[dict(name='등락',prob=40,range=[10.2,10.8],classification=[10.07,11.13]),
                 dict(name='하락 재개',prob=35,range=[9.2,10.0],classification='만기 <10.07; 하한 없음'),
                 dict(name='반등 지속',prob=25,range=[11.2,11.8],classification='만기 >11.13')],
      downside_levels=[10.23,10.0],upside_levels=[11.01],
      other_conditions='EWY <151.36 동행, 정규장 15분봉 2개 연속 종가 확인. 상승 철회 KORU >11.01 및 EWY >155.06. USD/KRW >1350 부담, <1335 반등 지지.'),
 dict(model='Antigravity Argon High',slug='argon',base_time='2026-11-05 07:31:00',base_price=10.58,
      expiry='2026-11-06 07:31:00',up_prob=44,center=[10.15,10.60],full_range=[9.10,11.90],
      regular_call='중립~보합 경합, 상승 약 50~52%',call='하락 소폭 우세 (상승 약 44%)',
      scenarios=[dict(name='강한 반등',prob=16,range=[11.1,11.9]),dict(name='저가 방어',prob=28,range=[10.58,11.1]),
                 dict(name='소폭 되밀림',prob=36,range=[9.95,10.58]),dict(name='투매 연장',prob=20,range=[9.1,9.95])],
      downside_levels=[10.23,10.03],upside_levels=[10.85,11.03],
      other_conditions='코스피 5700 회복과 KORU 10.85~11.03 안착 시 상승 전환. 10.23/10.03 이탈 시 하락 가속.')
]

def main():
 frames={s:load(s) for s in ['KORU','EWY','SOXX','MU','KRW_X','_KS11','005930.KS','000660.KS']}
 k=frames['KORU']; scores=[]; inputs=[]
 for m in MODELS:
  file=REPO/f'research/2026-11-05/koru-forecast-24h-{m["slug"]}.md'
  raw=file.read_bytes()
  inp=dict(m,note=str(file.relative_to(REPO)),prev_close=10.43,
           original_sha256=hashlib.sha256(raw).hexdigest())
  inputs.append(inp)
  expiry=ts(m['expiry']); base=ts(m['base_time']); q=quote(k,expiry)
  minute=k.loc[expiry.floor('min')]
  window=k[(k.index>=base.ceil('min'))&(k.index+pd.Timedelta(minutes=1)<=expiry)]
  score=dict(model=m['model'],note=inp['note'],base_time_kst=m['base_time'],base_price=m['base_price'],
      call=m['call'],expiry_kst=m['expiry'],expiry_price=q['price'],
      change_pct=(q['price']/m['base_price']-1)*100,
      prev_close_change_pct=(q['price']/10.43-1)*100,verdict='적중',
      center=m['center'],center_hit=m['center'][0]<=q['price']<=m['center'][1],
      center_lower_shortfall=m['center'][0]-q['price'],
      center_midpoint_error=abs(sum(m['center'])/2-q['price']),
      center_midpoint_error_pct_of_base=abs(sum(m['center'])/2-q['price'])/m['base_price']*100,
      full_range_lower_shortfall=m['full_range'][0]-q['price'],
      long_net_return_approx_pct=(q['price']/m['base_price']-1)*100-0.5,
      expiry_quote=q,elapsed_hours=(expiry-base).total_seconds()/3600,
      strict_24h_quote=quote(k,base+pd.Timedelta(hours=24)),
      expiry_label_bar_close=float(minute.Close),expiry_label_bar_low=float(minute.Low),expiry_label_bar_high=float(minute.High),
      maximum=float(window.High.max()),maximum_at_kst=str(window.High.idxmax()),
      minimum=float(window.Low.min()),minimum_at_kst=str(window.Low.idxmin()),
      regular_close_verdict='미적중',scenario_verdict='부분 적중')
  scores.append(score)
 # Freeze inputs only on the first invocation (own forecast later gets a review update).
 if not (ROOT/'forecast_inputs.json').exists(): dump('forecast_inputs.json',inputs)
 dump('scores.json',scores)
 pd.DataFrame([{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in scores]).to_csv(ROOT/'scores.csv',index=False)
 start=ts('2026-11-05 07:31'); end=ts('2026-11-06 07:40')
 segment=k[(k.index>=start)&(k.index+pd.Timedelta(minutes=1)<=end)]
 triggers={}
 for level in [10.23,10.225,10.03,10.0,9.95,9.6,9.2,9.1,8.8]:
  rec={}
  for col in ['Low','Close']:
   z=segment[segment[col]<level]
   rec[col]=None if z.empty else {'time_kst':str(z.index[0]),'time_est':str(z.index[0].tz_convert(ET)),'price':float(z.iloc[0][col])}
  triggers[str(level)]=rec
 regular_start=ts('2026-11-05 23:30'); regular_end=ts('2026-11-06 06:00')
 confirmations={}
 for sym,level in [('KORU',10.23),('EWY',151.36)]:
  f=frames[sym]; f=f[(f.index>=regular_start)&(f.index<regular_end)]
  r=f.Close.resample('15min',closed='left',label='right').agg(['last','count'])
  r['below']=r['last']<level
  # Require 15 populated one-minute bars in both bars for full regular-session confirmation.
  r['confirmed']=(r.below&r.below.shift(1,fill_value=False)&r['count'].eq(15)&r['count'].shift(1).eq(15))
  z=r[r.confirmed]
  confirmations[sym]=dict(level=level,first_confirmed=str(z.index[0]) if len(z) else None,bars=r.reset_index().astype(str).to_dict('records'))
  r.to_csv(ROOT/f'{sym}_regular_15m.csv',index_label='bar_end_kst')
 checkpoint_times=['2026-11-05 07:31','2026-11-05 08:00','2026-11-05 08:05','2026-11-05 09:00',
 '2026-11-05 10:00','2026-11-05 15:30','2026-11-05 18:01','2026-11-05 20:00','2026-11-05 22:30',
 '2026-11-05 23:30','2026-11-06 00:00','2026-11-06 00:30','2026-11-06 01:00','2026-11-06 02:00',
 '2026-11-06 03:00','2026-11-06 04:00','2026-11-06 05:00','2026-11-06 06:00',
 '2026-11-06 07:00','2026-11-06 07:31','2026-11-06 07:33:38','2026-11-06 07:40','2026-11-06 08:00','2026-11-06 09:00']
 checkpoints=[]
 for t in checkpoint_times:
  row={'asof_kst':t,'asof_est':str(ts(t).tz_convert(ET))}
  for s,f in frames.items():
   q=quote(f,ts(t)); row[s]=q['price'];row[s+'_bar_kst']=q['bar_start_kst'];row[s+'_age_seconds']=q['age_from_bar_end_seconds']
  checkpoints.append(row)
 pd.DataFrame(checkpoints).to_csv(ROOT/'checkpoints.csv',index=False)
 phase_ranges=[('initial_ah','2026-11-05 07:31','2026-11-05 10:00'),
 ('premarket','2026-11-05 18:00','2026-11-05 23:30'),
 ('us_first_hour','2026-11-05 23:30','2026-11-06 00:30'),
 ('us_remaining','2026-11-06 00:30','2026-11-06 06:00'),
 ('expiry_ah','2026-11-06 06:00','2026-11-06 07:40'),
 ('post_expiry','2026-11-06 07:40',str(k.index[-1]+pd.Timedelta(minutes=1)))]
 phases=[]
 for name,a,b in phase_ranges:
  end_time=pd.Timestamp(b) if '+' in b else ts(b)
  f=k[(k.index>=ts(a))&(k.index<end_time)]
  phases.append(dict(name=name,start=a,end=b,rows=len(f),first_bar=str(f.index[0]),open=float(f.iloc[0].Open),
   last_bar=str(f.index[-1]),close=float(f.iloc[-1].Close),low=float(f.Low.min()),low_at=str(f.Low.idxmin()),
   high=float(f.High.max()),high_at=str(f.High.idxmax())))
 daily=[]
 for s in ['KORU','EWY','SOXX','MU','QCOM','ARM','AMD','_GSPC','_IXIC','_VIX','005930.KS','000660.KS','278540.KS']:
  d=pd.read_csv(ROOT/f'{s}_1d.csv');d['date']=d.timestamp.str[:10]
  prev=d[d.date=='2026-11-04'].iloc[0];cur=d[d.date=='2026-11-05'].iloc[0]
  split=3 if s=='SOXX' else 1
  daily.append(dict(symbol=s,prev_close=float(prev.Close),split_factor=split,comparable_prev_close=float(prev.Close)/split,
   close=float(cur.Close),change_pct=(float(cur.Close)/(float(prev.Close)/split)-1)*100,
   open=float(cur.Open),high=float(cur.High),low=float(cur.Low)))
 gaps=[]
 for left,right in zip(segment.index[:-1],segment.index[1:]):
  if right-left>pd.Timedelta(minutes=1):gaps.append(dict(left=str(left),right=str(right),missing_minutes=int((right-left).total_seconds()/60)-1))
 result=dict(analyzed_at_kst=str(datetime.now(ZoneInfo(KST))),scores=scores,triggers=triggers,
    regular_confirmations=confirmations,phases=phases,daily=daily,gaps=gaps,
    source_method='last completed 1-minute bar, no forward fill, original base price frozen')
 dump('analysis.json',result)
 print(json.dumps({k:result[k] for k in ['scores','triggers','phases','daily','gaps']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
