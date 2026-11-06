"""Offline calculations. Minute stamps are bar starts, never exact trade times."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import pandas as pd
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
ET='America/New_York'
KST='Asia/Seoul'

def read(symbol,interval='1m'):
    d=pd.read_csv(OUT/f'{symbol}_{interval}.csv',index_col=0)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert(ET)
    return d.dropna(subset=['close']).sort_index()

def stamp(s): return pd.Timestamp(s,tz=ET)
def pct(p,b): return (p/b-1)*100
def times(t):
    return {'et':t.isoformat(),'kst':t.tz_convert(KST).isoformat()}

def main():
    s=read('SOXL');daily=read('SOXL','1d');x=read('SOXX')
    # Copy the original predictions for audit before any own-note amendment.
    specifications=[
      dict(slug='claude',model='Claude Fable Max',source_name='Claude Fable 5.1',
           note='research/2026-11-05/forecast-24h-claude.md',base=70.03,analysis_price=69.8,
           analysis_kst='2026-11-05 00:30',expiry_kst='2026-11-05 23:30',up_prob=0.42,
           center=[67,70],direction='하락 소폭 우세',
           scenarios=[{'prob':.33,'range':[60,67]},{'prob':.25,'range':[67,70]},
                      {'prob':.27,'range':[70,74]},{'prob':.15,'range':[74,80]}]),
      dict(slug='codex',model='Codex Astra Max',source_name='Codex',
           note='research/2026-11-05/forecast-24h-codex.md',base=70,analysis_price=71.75,
           analysis_kst='2026-11-05 00:05:06',expiry_kst='2026-11-06 00:05:06',up_prob=.55,
           center=[71,73],direction='개장가 대비 소폭 상승 우세',
           scenarios=[{'prob':.40,'classification':'66.50 <= p <= 73.50','range':[68,73]},
                      {'prob':.35,'classification':'p > 73.50','range':[75,81]},
                      {'prob':.25,'classification':'p < 66.50','range':[61,66]}]),
      dict(slug='argon',model='Antigravity Argon High',source_name='AGY Argon',
           note='research/2026-11-04/soxl-forecast-24h-argon.md',base=70.03,analysis_price=72.37,
           analysis_kst='2026-11-05 00:17',expiry_kst='2026-11-05 23:30',up_prob=.59,
           center=[71.5,74],direction='완만한 상승 우위 (요약 58~60%, 시나리오 합산 59%)',
           scenarios=[{'prob':.23,'range':[74.5,79]},{'prob':.36,'range':[70.03,74.5]},
                      {'prob':.28,'range':[66.5,70.03]},{'prob':.13,'range':[61,66.5]}]),
    ]
    result={'generated_at_kst':datetime.now(ZoneInfo(KST)).isoformat(),'forecasts':[],
            'bar_convention':'[start, start + 1 minute); use prior completed bar for seconds expiry',
            'prior_close':73.12,'base_time_kst':'2026-11-04 23:30'}
    open_row=s.loc[stamp('2026-11-05 09:30')]
    for f in specifications:
        snapshot=OUT/f"original_forecast_{f['slug']}.md"
        if not snapshot.exists(): snapshot.write_bytes((ROOT/f['note']).read_bytes())
        f['source_sha256']=hashlib.sha256(snapshot.read_bytes()).hexdigest()
        expiry=pd.Timestamp(f['expiry_kst'],tz=KST).tz_convert(ET)
        if f['slug']=='codex':
            # Explicit method already committed in the original Codex note.
            eligible=s[(s.index+pd.Timedelta(minutes=1)<=expiry)&(s.volume>0)]
            t=eligible.index[-1];p=float(eligible.iloc[-1].close)
            f['price_method']='last completed 1m close: 10:04–10:05 EST; exact 10:05:06 trade unavailable'
        else:
            t=stamp('2026-11-05 09:30');p=float(open_row.open)
            f['price_method']='09:30 1m open; corroborated daily open, not 09:30 1m close'
        f.update(expiry_price=p,bar_start=times(t),expiry=times(expiry),
                 change_pct=pct(p,f['base']),prev_close_change_pct=pct(p,73.12),
                 analysis_quote_change_pct=pct(p,f['analysis_price']),
                 approximate_net_long_pct=pct(p,f['base'])-.5,
                 center_miss_below_dollars=f['center'][0]-p,
                 center_miss_below_pct=pct(p,f['center'][0]),
                 direction_verdict='적중' if f['slug']=='claude' else '미적중',
                 center_verdict='미적중',previous_close_verdict='적중',
                 verdict='부분 적중' if f['slug']=='claude' else '미적중',
                 brier_single_observation=f['up_prob']**2)
        result['forecasts'].append(f)
    result['common_open']={'price':float(open_row.open),'bar':times(stamp('2026-11-05 09:30')),
                           'volume':int(open_row.volume),'codex_return_pct':pct(float(open_row.open),70)}
    # Half-open sessions avoid including the next session's first minute.
    phases=[('opening_hour','2026-11-04 09:30','2026-11-04 10:30'),
            ('support_break','2026-11-04 10:30','2026-11-04 11:15'),
            ('afternoon','2026-11-04 11:15','2026-11-04 16:00'),
            ('earnings_afterhours','2026-11-04 16:00','2026-11-04 20:00'),
            ('premarket_before_data','2026-11-05 04:00','2026-11-05 08:30'),
            ('premarket_after_data','2026-11-05 08:30','2026-11-05 09:30'),
            ('opening_to_codex_proxy','2026-11-05 09:30','2026-11-05 10:05'),
            ('after_all_expiries','2026-11-05 10:05','2026-11-05 16:00')]
    result['phases']=[]
    for name,start,end in phases:
        a,b=stamp(start),stamp(end);v=s[(s.index>=a)&(s.index<b)]
        result['phases'].append({'id':name,'start':times(a),'end_exclusive':times(b),
          'bars':len(v),'first':times(v.index[0]),'last':times(v.index[-1]),
          'open':float(v.iloc[0].open),'last_close':float(v.iloc[-1].close),
          'low':float(v.low.min()),'low_bar':times(v.low.idxmin()),
          'high':float(v.high.max()),'high_bar':times(v.high.idxmax()),
          'zero_volume_bars':int((v.volume==0).sum())})
    # 15m bars anchored at wall-clock quarter-hours; report confirmation at bar end.
    reg=s[(s.index>=stamp('2026-11-04 09:30'))&(s.index<stamp('2026-11-04 16:00'))]
    bars=reg.resample('15min',closed='left',label='right').agg(
       {'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
    bars.to_csv(OUT/'SOXL_15m_confirmations.csv')
    below=bars.close<67.26
    confirmed=below&below.shift(1,fill_value=False)
    result['two_15m_below_67_26']={'confirmation':times(bars[confirmed].index[0]),
      'first_close':float(bars.loc[stamp('2026-11-04 10:45'),'close']),
      'second_close':float(bars.loc[stamp('2026-11-04 11:00'),'close'])}
    w=s[(s.index>=stamp('2026-11-04 10:05'))&(s.index<stamp('2026-11-05 10:05'))]
    joined=w.join(x[['close']].rename(columns={'close':'soxx_split_adjusted'}))
    result['thresholds']={}
    conditions={'first_close_below_70':joined.close<70,
      'joint_close_break_67_26_452_46':(joined.close<67.26)&(joined.soxx_split_adjusted<452.46/3),
      'first_close_below_61':joined.close<61}
    for name,mask in conditions.items():
        row=joined[mask].iloc[0]
        result['thresholds'][name]={'bar_start':times(row.name),'close':float(row.close),
          'soxx_split_adjusted_close':float(row.soxx_split_adjusted),
          'available_at_bar_end':times(row.name+pd.Timedelta(minutes=1))}
    up=bars.close>73.12
    result['two_15m_above_73_12_any'] = bool((up&up.shift(1,fill_value=False)).any())
    result['first_hour_audit']={
      'last_included_bar':times(stamp('2026-11-04 10:29')),
      'correct_completed_hour_close':float(s.loc[stamp('2026-11-04 10:29'),'close']),
      'return_vs_70_03_pct':pct(float(s.loc[stamp('2026-11-04 10:29'),'close']),70.03),
      'following_10_30_bar_close':float(s.loc[stamp('2026-11-04 10:30'),'close']),
      'claude_original_hour_close':69.77,
      'interpretation':'Original live snapshot differs; final 1m data do not confirm below-open first-hour bucket.'}
    result['market_close_comparison']=[]
    for sym in ['SOXL','SOXX','SMH','NVDA','AMD','AVGO','MU','TSM','ASML','QCOM','ARM','QQQ','VIX','TNX']:
        d=read(sym,'1d');cl=[float(d.loc[day].iloc[-1].close) for day in ['2026-11-03','2026-11-04','2026-11-05']]
        comparable=[cl[0]/3,cl[1]/3,cl[2]] if sym=='SOXX' else cl
        result['market_close_comparison'].append({'symbol':sym,'raw_closes':cl,
          'comparable_closes':comparable,'nov4_pct':pct(comparable[1],comparable[0]),
          'nov5_pct':pct(comparable[2],comparable[1])})
    result['expiry_context_quotes']=[]
    for sym in ['SOXX','SMH','NVDA','AMD','AVGO','MU','TSM','ASML','QCOM','ARM','QQQ','NQ_F','VIX','TNX']:
        v=read(sym);t=stamp('2026-11-05 09:30');d=read(sym,'1d')
        prev=float(d.loc['2026-11-04'].iloc[-1].close)/(3 if sym=='SOXX' else 1)
        # At open use first bar OPEN for listed equities; otherwise last completed indicator bar.
        if sym not in ['NQ_F','VIX','TNX'] and t in v.index:
            row=v.loc[t];value=float(row.open);method='09:30 minute open'
        else:
            row=v[v.index+pd.Timedelta(minutes=1)<=t].iloc[-1];value=float(row.close);method='last completed minute close'
        result['expiry_context_quotes'].append({'symbol':sym,'bar':times(row.name),
          'value':value,'prev_close_comparable':prev,'change_pct':pct(value,prev),'method':method})
    result['data_quality']={
      'soxl_regular_1m_counts':{day:len(s.loc[f'{day} 09:30':f'{day} 15:59']) for day in ['2026-11-04','2026-11-05']},
      'premarket_missing_interval_et':'2026-11-05 09:15–09:29 (15 rows); no forward fill',
      'extended_hours_volume':'zero in feed; do not treat as proof of no trades',
      'soxx_units':'intraday retrospectively split-adjusted; daily historical quote fields unadjusted before Nov 5',
      'nov5_post_expiry_close_yahoo':float(daily.loc['2026-11-05'].iloc[-1].close),
      'nov5_post_expiry_close_stockanalysis':40.92,
      'nasdaq_historical_latest_returned_date':'2026-11-04; not an independent confirmation of Nov 5 open',
      'exact_seconds_trade_available':False}
    # Compare the second Yahoo host only as transport consistency, not independent source evidence.
    q2=json.loads((OUT/'yahoo_soxl_query2.json').read_text())['chart']['result'][0]
    q=pd.DataFrame(q2['indicators']['quote'][0],index=pd.to_datetime(q2['timestamp'],unit='s',utc=True).tz_convert(ET))
    result['data_quality']['query2_expiry_open']=float(q.loc[stamp('2026-11-05 09:30'),'open'])
    result['data_quality']['query2_codex_proxy']=float(q.loc[stamp('2026-11-05 10:04'),'close'])
    (OUT/'review_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['two_15m_below_67_26','first_hour_audit','expiry_context_quotes']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
