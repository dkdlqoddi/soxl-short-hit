"""Offline, one observation per session, information cutoff 2026-11-06 10:42 KST."""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'forecast_raw'
CUTOFF=pd.Timestamp('2026-11-06 10:42',tz='Asia/Seoul')
BASE=43.59

def read(stem):
    d=pd.read_csv(RAW/(stem+'.csv'),index_col='timestamp_utc')
    d.index=pd.to_datetime(d.index,utc=True).tz_convert('America/New_York')
    d.index.name='timestamp_et'
    return d

def meta(stem):
    return json.loads((RAW/(stem+'.json')).read_text())['data']['chart']['result'][0]['meta']

def clean(o):
    if o is pd.NaT:return None
    if isinstance(o,dict):return {k:clean(v) for k,v in o.items()}
    if isinstance(o,list):return [clean(v) for v in o]
    if isinstance(o,(np.integer,)):return int(o)
    if isinstance(o,(float,np.floating)):return float(o) if np.isfinite(o) else None
    if isinstance(o,(pd.Timestamp,)):return str(o)
    if isinstance(o,np.bool_):return bool(o)
    return o

def stat(values,threshold=0):
    v=pd.Series(values).dropna().astype(float)
    n=len(v)
    if not n:return {'N':0,'up_pct':None,'mean_pct':None,'median_pct':None}
    p=(v>threshold).mean(); z=1.96; den=1+z*z/n
    c=(p+z*z/(2*n))/den; h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {'N':n,'up_pct':p*100,'mean_pct':v.mean()*100,'median_pct':v.median()*100,
            'q25_pct':v.quantile(.25)*100,'q75_pct':v.quantile(.75)*100,
            'q10_pct':v.quantile(.1)*100,'q90_pct':v.quantile(.9)*100,
            'min_pct':v.min()*100,'max_pct':v.max()*100,'over_fee_pct':(v>.005).mean()*100,
            'wilson95_pct':[100*(c-h),100*(c+h)]}

def wilder(series,n=14):
    out=pd.Series(np.nan,index=series.index)
    valid=series.dropna()
    if len(valid)<n:return out
    start=series.index.get_loc(valid.index[n-1])
    out.iloc[start]=valid.iloc[:n].mean()
    for i in range(start+1,len(series)):
        out.iloc[i]=(out.iloc[i-1]*(n-1)+series.iloc[i])/n
    return out

def daily():
    d=read('SOXL_2010_2026_1d')
    assert meta('SOXL_2010_2026_1d')['dataGranularity']=='1d'
    assert d.index.is_unique
    d=d[d.index<CUTOFF].copy()
    assert d.index[-1].strftime('%Y-%m-%d')=='2026-11-05'
    # Latest daily Close is null: use explicitly time-stamped regular-session metadata.
    m=meta('SOXL_5d_1m')
    assert pd.Timestamp(m['regularMarketTime'],unit='s',tz='UTC').tz_convert('America/New_York').strftime('%Y-%m-%d %H:%M')=='2026-11-05 16:00'
    assert pd.isna(d.iloc[-1]['close'])
    d.loc[d.index[-1],'close']=m['regularMarketPrice']
    d['ret']=d.close.pct_change(fill_method=None)
    d['next_ret']=d.close.shift(-1)/d.close-1
    d['ma20']=d.close.rolling(20).mean();d['ma50']=d.close.rolling(50).mean();d['ma200']=d.close.rolling(200).mean()
    d['ratio20']=d.close/d.ma20
    d['next_date']=pd.Series(d.index,index=d.index).shift(-1)
    d['next_24h']=(d.next_date-pd.Series(d.index,index=d.index))==pd.Timedelta(hours=24)
    delta=d.close.diff()
    gain=wilder(delta.clip(lower=0));loss=wilder(-delta.clip(upper=0))
    d['rsi14']=100-100/(1+gain/loss)
    tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
    d['atr14']=wilder(tr);d['tr14_sma']=tr.rolling(14).mean()
    d['clv']=(d.close-d.low)/(d.high-d.low)
    d['drawdown20']=d.close/d.close.rolling(20).max()-1
    d['rv20']=d.ret.rolling(20).std()
    d['volume_ratio20']=d.volume/d.volume.shift().rolling(20).mean()
    d.to_csv(ROOT/'forecast_daily_features.csv')
    current=d.iloc[-1]; gap=BASE/current.close-1
    conditions={
      'all_next_trading_day':pd.Series(True,index=d.index),
      'all_exact24h':d.next_24h,
      'recent60_exact24h':d.next_24h&(d.index>=d.index[-61]),
      'drop10_exact24h':d.next_24h&(d.ret<=-.10),
      'drop10_belowma20_exact24h':d.next_24h&(d.ret<=-.10)&(d.ratio20<1),
      'drop20_exact24h':d.next_24h&(d.ret<=-.20),
      'drop30_exact24h':d.next_24h&(d.ret<=-.30),
      'drop_as_severe_as_today':d.next_24h&(d.ret<=current.ret),
      'recent252_drop10_exact24h':d.next_24h&(d.ret<=-.10)&(d.index>=d.index[-253]),
      'drawdown20_below30pct_exact24h':d.next_24h&(d.drawdown20<=-.30),
    }
    stats={}
    for label,mask in conditions.items():
        v=d.loc[mask,'next_ret'];s=stat(v)
        s['nextclose_above_today_ah_gap_pct']=float((v.dropna()>gap).mean()*100) if v.notna().any() else None
        stats[label]=s
    cases=d[d.ret<=-.20][['open','high','low','close','ret','next_ret','next_date','next_24h','ratio20','rsi14']]
    cases.to_csv(ROOT/'forecast_extreme_daily_cases.csv')
    return d,stats,current,gap

def sessions(stem,interval):
    q=read(stem)
    # Drop live synthetic quote appendices (seconds != 0), but do not invent trades for missing rows.
    q=q[(q.index<CUTOFF)&(q.index.second==0)].dropna(subset=['close']).copy()
    records=[]
    for day,g in q.groupby(q.index.date):
        g=g.sort_index(); minute=g.index.hour*60+g.index.minute
        reg=g[(minute>=570)&(minute<960)]
        ah=g[(minute>=1140)&(minute<1200)]
        # Require a late after-hours bar and a regular-session final bar.
        if len(reg)==0 or len(ah)==0:continue
        if reg.index[-1].hour!=15:continue
        if interval=='5m' and ah.index[-1].minute<50:continue
        if interval=='1m' and ah.index[-1].minute<58:continue
        if interval=='1h' and ah.index[-1].strftime('%H:%M')!='19:00':continue
        end=pd.Timestamp(str(day)+' 20:00',tz='America/New_York')
        if end>CUTOFF:continue
        records.append({'date':str(day),'regular_bar_close':reg.close.iloc[-1],
                        'regular_bar_time':str(reg.index[-1]),'after_close':ah.close.iloc[-1],
                        'after_bar_time':str(ah.index[-1]),'endpoint':end,'rows':len(g),
                        'regular_rows':len(reg),'after_last_hour_rows':len(ah)})
    s=pd.DataFrame(records).set_index('date').sort_index()
    assert s.index.is_unique
    s['next_after']=s.after_close.shift(-1);s['next_endpoint']=s.endpoint.shift(-1)
    s['next_24h']=(s.next_endpoint-s.endpoint)==pd.Timedelta(hours=24)
    return s

def intraday(d,stem,interval):
    s=sessions(stem,interval)
    original_dates=set(s.index)
    minute=sessions('SOXL_5d_1m','1m')
    corrections=[]
    for day,row in minute.iterrows():
        old=s.loc[day,'after_close'] if day in s.index else None
        corrections.append({'date':day,'old_after_close':old,'one_min_after_close':row.after_close,
                            'one_min_bar':row.after_bar_time,'added_missing_session':day not in original_dates})
    # Use independently observed 19:59 one-minute endpoints where historical 5m/1h feeds omit the last EST hour.
    s=pd.concat([s.loc[~s.index.isin(minute.index)],minute]).sort_index()
    s['next_after']=s.after_close.shift(-1);s['next_endpoint']=s.endpoint.shift(-1)
    s['next_24h']=(s.next_endpoint-s.endpoint)==pd.Timedelta(hours=24)
    (ROOT/f'forecast_endpoint_repairs_{interval}.json').write_text(json.dumps(clean(corrections),ensure_ascii=False,indent=2))
    dm=d.copy();dm.index=dm.index.strftime('%Y-%m-%d')
    s=s.join(dm[['close','ret','ratio20','drawdown20']])
    s['ah_ret']=s.after_close/s.close-1
    s['next_ah_ret']=s.next_after/s.after_close-1
    s['next_ah_vs_close']=s.next_after/s.close-1
    s['next_close']=s.index.to_series().map(dm.close.shift(-1))
    s['next_close_vs_ah']=s.next_close/s.after_close-1
    conditions={
      'all_exact24h':s.next_24h,
      'recent60_exact24h':s.next_24h&(s.index>=dm.index[-61]),
      'thursday_to_friday':s.next_24h&(s.endpoint.dt.dayofweek==3),
      'regular_drop10':s.next_24h&(s.ret<=-.1),
      'ah_gain3':s.next_24h&(s.ah_ret>=.03),
      'regular_drop5_ah_gain1':s.next_24h&(s.ret<=-.05)&(s.ah_ret>=.01),
      'regular_drop10_ah_gain3':s.next_24h&(s.ret<=-.1)&(s.ah_ret>=.03),
      'below20ma_ah_gain1':s.next_24h&(s.ratio20<1)&(s.ah_ret>=.01),
      'regular_drop20':s.next_24h&(s.ret<=-.2),
    }
    stats={}
    for label,mask in conditions.items():
        vals=s.loc[mask];stats[label]=stat(vals.next_ah_ret)
        stats[label]['vs_close']=stat(vals.next_ah_vs_close)
        stats[label]['next_close_vs_ah']=stat(vals.next_close_vs_ah)
    valid=s[s.next_24h].dropna(subset=['ah_ret','next_ah_ret','ret'])
    x=np.column_stack([np.ones(len(valid)),valid.ah_ret.values*100,valid.ret.values*100])
    y=valid.next_ah_ret.values*100
    beta=np.linalg.lstsq(x,y,rcond=None)[0];fit=x@beta
    r2=1-np.sum((y-fit)**2)/np.sum((y-y.mean())**2)
    regression={'N':len(valid),'intercept_pp':beta[0],'after_hours_slope':beta[1],
                'regular_day_slope':beta[2],'r_squared':r2,'residual_sd_pp':np.std(y-fit,ddof=3),
                'x_ah_range_pct':[valid.ah_ret.min()*100,valid.ah_ret.max()*100],
                'x_regular_range_pct':[valid.ret.min()*100,valid.ret.max()*100]}
    s.to_csv(ROOT/f'forecast_sessions_{interval}.csv')
    return s,stats,regression

def snapshot():
    syms=['SOXL','SOXX','SMH','NVDA','AMD','AVGO','MU','TSM','ASML','QCOM','ARM','QQQ','NQ_F','VIX','TNX','KRW_X','DX-Y_NYB','KS11','005930_KS','000660_KS']
    out={}
    for sym in syms:
        stem=f'{sym}_5d_1m';m=meta(stem);q=read(stem)
        q=q[q.index<CUTOFF].dropna(subset=['close'])
        last=q.iloc[-1]
        mt=pd.Timestamp(m['regularMarketTime'],unit='s',tz='UTC')
        out[sym]={'last':last.close,'last_et':str(q.index[-1]),'last_kst':str(q.index[-1].tz_convert('Asia/Seoul')),
                  'last_volume':last.volume,'meta_regular_price':m.get('regularMarketPrice'),
                  'meta_regular_time':str(mt.tz_convert('Asia/Seoul')),'meta_previous_close':m.get('previousClose'),
                  'regular_change_pct':(m['regularMarketPrice']/m['previousClose']-1)*100 if m.get('previousClose') else None,
                  'last_vs_regular_pct':(last.close/m['regularMarketPrice']-1)*100,
                  'meta_time_after_cutoff':mt>CUTOFF}
    return out

def main():
    d,ds,current,gap=daily()
    h,hs,hr=intraday(d,'SOXL_730d_1h','1h')
    f,fs,fr=intraday(d,'SOXL_60d_5m','5m')
    q=read('SOXL_5d_1m');reg=q[(q.index.strftime('%Y-%m-%d')=='2026-11-05')&(q.index.hour*60+q.index.minute>=570)&(q.index.hour*60+q.index.minute<960)]
    typ=(reg.high+reg.low+reg.close)/3
    overlap=h.join(f[['after_close']],rsuffix='_5m').dropna(subset=['after_close_5m'])
    comparison=(overlap.after_close-overlap.after_close_5m).abs()
    result={'contract':{'base_price':BASE,'prev_close':current.close,'information_cutoff':str(CUTOFF),
                        'expiry_kst':'2026-11-07 10:42','base_session':'closed','ah_gap_pct':gap*100},
            'daily_range':[str(d.index.min()),str(d.index.max())],'daily_rows':len(d),
            'current':current.to_dict(),'regular_vwap_1m':float((typ*reg.volume).sum()/reg.volume.sum()),
            'daily_stats':ds,'hourly_stats':hs,'five_min_stats':fs,'hourly_regression':hr,
            'hourly_sessions':len(h),'hourly_dates':[h.index.min(),h.index.max()],
            'five_min_sessions':len(f),'five_min_dates':[f.index.min(),f.index.max()],
            'endpoint_comparison':{'N':len(comparison),'max_difference':comparison.max(),'mismatched_above_1cent':int((comparison>.01).sum())},
            'prices':snapshot()}
    (ROOT/'forecast_metrics.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(clean({k:v for k,v in result.items() if k!='prices'}),ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':main()
