"""Reproduce minute-label expiry scores; also report strict :00 sensitivity.

Forecast times have minute precision. Primary score uses Close of the labelled
expiry minute, matching the prior review's convention. Secondary score uses the
last fully completed minute, preventing any within-minute look-ahead. Yahoo
after-hours Volume=0 is treated as unavailable, not as proof of no executions.
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
KST = 'Asia/Seoul'
ET = 'America/New_York'

def read(symbol, interval='1m'):
    d = pd.read_csv(ROOT / f'{symbol}_{interval}.csv')
    d.index = pd.to_datetime(d.pop('timestamp'), utc=True).dt.tz_convert(KST)
    return d.sort_index()

def stamp(t):
    return {'kst': str(t), 'et': str(t.tz_convert(ET))}

def snapshot(d, t, strict=False):
    ts = pd.Timestamp(t, tz=KST)
    valid = d[(d.index < ts) if strict else (d.index <= ts)].dropna(subset=['Close'])
    row = valid.iloc[-1]
    return {**stamp(valid.index[-1]), **{k: float(row[k]) for k in ['Open','High','Low','Close','Volume']},
            'lag_minutes': (ts-valid.index[-1]).total_seconds()/60}

def segment(d, start, end):
    a,b = pd.Timestamp(start,tz=KST), pd.Timestamp(end,tz=KST)
    q=d[(d.index >= a)&(d.index < b)].dropna(subset=['Close'])
    if q.empty:
        return {'start':stamp(a),'end_exclusive':stamp(b),'rows':0}
    return {'start':stamp(a),'end_exclusive':stamp(b),'rows':len(q),
            'first':stamp(q.index[0]), 'last':stamp(q.index[-1]),
            'open':float(q.Open.iloc[0]),'close':float(q.Close.iloc[-1]),
            'high':float(q.High.max()),'high_at':stamp(q.High.idxmax()),
            'low':float(q.Low.min()),'low_at':stamp(q.Low.idxmin())}

def main():
    k = read('KORU')
    forecasts = [
      {'model':'Claude Fable Max','slug':'claude','base_time':'2026-11-04 09:10','base_price':11.39,
       'expiry':'2026-11-05 09:10','up_probability':0.45,'center':[11.0,11.4],'direction':'down'},
      {'model':'Codex Astra Max','slug':'astra','base_time':'2026-11-04 08:43','base_price':11.41,
       'expiry':'2026-11-05 08:43','up_probability':None,'center':None,'direction':'up'},
      {'model':'Antigravity Argon High','slug':'argon','base_time':'2026-11-04 08:55','base_price':11.30,
       'expiry':'2026-11-05 08:55','up_probability':0.37,'center':[10.8,11.1],'direction':'down'},
    ]
    for f in forecasts:
        f['expiry_bar'] = snapshot(k,f['expiry'])
        f['strict_completed_bar'] = snapshot(k,f['expiry'],strict=True)
        f['base_bar_crosscheck'] = snapshot(k,f['base_time'])
        f['base_strict_crosscheck'] = snapshot(k,f['base_time'],strict=True)
        px=f['expiry_bar']['Close']
        f['expiry_price']=px
        f['change_pct']=(px/f['base_price']-1)*100
        f['prev_close']=11.01
        f['prev_close_change_pct']=(px/11.01-1)*100
        f['long_return_after_fee_pp']=f['change_pct']-0.5
        f['verdict']='적중' if f['direction']=='down' else '미적중'
        f['center_hit']=None if f['center'] is None else f['center'][0]<=px<=f['center'][1]
        if f['center']:
            f['center_lower_gap']=px-f['center'][0]
            f['center_midpoint_error_pct']=(px/(sum(f['center'])/2)-1)*100
        f['path']=segment(k,f['base_time'],str(pd.Timestamp(f['expiry'])+pd.Timedelta(minutes=1)))
        f['mfe_pct']=(f['path']['high']/f['base_price']-1)*100
        f['mae_pct']=(f['path']['low']/f['base_price']-1)*100
    bounds=[
       ('01_initial_ah','2026-11-04 08:43','2026-11-04 10:00'),
       ('02_us_data_gap','2026-11-04 10:00','2026-11-04 18:00'),
       ('03_premarket','2026-11-04 18:00','2026-11-04 23:30'),
       ('04_opening_hour','2026-11-04 23:30','2026-11-05 00:30'),
       ('05_regular_rest','2026-11-05 00:30','2026-11-05 06:00'),
       ('06_afterhours_early','2026-11-05 06:00','2026-11-05 08:00'),
       ('07_korea_open_expiries','2026-11-05 08:00','2026-11-05 09:11'),
       ('08_extension','2026-11-05 09:11','2026-11-05 10:00'),
    ]
    phases={label:segment(k,a,b) for label,a,b in bounds}
    crosses={}
    q=k.loc['2026-11-04 08:43':'2026-11-05 09:10']
    for level,kind in [(10.83,'down'),(10.37,'down'),(11.56,'up'),(11.59,'up')]:
        cond=(q.Close < level) if kind=='down' else (q.Close > level)
        touch=(q.Low < level) if kind=='down' else (q.High >= level)
        matches=q[cond]
        touches=q[touch]
        crosses[str(level)]={'direction':kind,'close_count':len(matches),
           'first_close':None if matches.empty else snapshot(q,str(matches.index[0].tz_localize(None))),
           'first_touch':None if touches.empty else snapshot(q,str(touches.index[0].tz_localize(None)))}
    daily={}
    symbols=['KORU','EWY','SOXX','MU','AMD','QCOM','ARM','_GSPC','_IXIC','_VIX','_KS11','005930.KS','000660.KS']
    for s in symbols:
        d=read(s,'1d')
        a=d[d.index.date==pd.Timestamp('2026-11-03').date()].iloc[-1]
        b=d[d.index.date==pd.Timestamp('2026-11-04').date()].iloc[-1]
        daily[s]={'prev_close':float(a.Close),**{x.lower():float(b[x]) for x in ['Open','High','Low','Close','Volume']},
                  'change_pct':float((b.Close/a.Close-1)*100),
                  'open_to_close_pct':float((b.Close/b.Open-1)*100)}
    observations={}
    for s in ['KORU','EWY','SOXX','MU','QCOM','ARM','KRW_X','_KS11','005930.KS','000660.KS']:
        d=read(s)
        times=['2026-11-04 09:10','2026-11-04 13:30','2026-11-04 15:30','2026-11-04 18:00',
               '2026-11-05 06:00','2026-11-05 08:00','2026-11-05 08:43','2026-11-05 08:55',
               '2026-11-05 09:10','2026-11-05 09:59']
        observations[s]={t:snapshot(d,t) for t in times}
    korean_segments={s:segment(read(s),'2026-11-04 09:00','2026-11-04 15:31') for s in ['_KS11','005930.KS','000660.KS']}
    ss=read('005930.KS').loc['2026-11-04 09:00':'2026-11-04 15:30'].Close
    hh=read('000660.KS').loc['2026-11-04 09:00':'2026-11-04 15:30'].Close
    pair=pd.concat([ss.rename('samsung'),hh.rename('hynix')],axis=1)
    failed=pair[(pair.samsung<219500)&(pair.hynix<1398000)]
    regular=k.loc['2026-11-04 23:30':'2026-11-05 05:59']
    quality={'first_both_korean_stocks_below_prev_close':{
                 **stamp(failed.index[0]),**{x:float(failed[x].iloc[0]) for x in failed.columns}},
             'first_regular_close_below_10_83':snapshot(regular,str(regular[regular.Close<10.83].index[0].tz_localize(None))),
             'missing_us_premarket_minutes_kst':[str(t) for t in pd.date_range('2026-11-04 18:00','2026-11-04 23:29',freq='min',tz=KST) if t not in k.index],
             'afterhours_volume_note':'Yahoo supplies zero for extended-hours volume; do not infer no trades',
             'korean_intraday_tail_note':'2026-11-04 1m data ends at 14:59 KST; official close uses daily data',
             'nasdaq_crosscheck_note':'Nasdaq 11/4 low 10.225 and volume 58,880,840; Yahoo daily low 10.23, volume 55,775,900; open and close agree'}
    out={'method':'expiry-labelled minute Close; previous completed minute sensitivity included',
         'forecasts':forecasts,'phases':phases,'crosses':crosses,'daily':daily,
         'observations':observations,'korean_segments':korean_segments,'quality_checks':quality}
    (ROOT/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    pd.DataFrame([{key:f[key] for key in ['model','base_time','base_price','expiry','expiry_price','change_pct',
                  'prev_close_change_pct','long_return_after_fee_pp','verdict','center_hit','mfe_pct','mae_pct']} for f in forecasts]).to_csv(ROOT/'scores.csv',index=False)
    print(json.dumps({key:out[key] for key in ['forecasts','phases','crosses','daily','korean_segments']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
