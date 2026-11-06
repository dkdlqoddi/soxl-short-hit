"""Offline analysis. All conditioning inputs precede each outcome; no live fetches."""
from pathlib import Path
import json, math
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
BASE=pd.Timestamp('2026-11-06 10:42',tz='Asia/Seoul')
def save(name,obj):
    s=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert len(s.encode())<10_000_000
    (ROOT/name).write_text(s,encoding='utf-8')
def daily(sym):
    d=pd.read_csv(ROOT/(sym+'_1d.csv'))
    d.index=pd.to_datetime(d.timestamp.str[:10]);return d.drop(columns='timestamp').sort_index()
def intraday(sym,iv='1m'):
    d=pd.read_csv(ROOT/(sym+'_'+iv+'.csv'),index_col=0)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert('America/New_York')
    return d.sort_index().dropna(subset=['Close'])
def stats(s):
    s=s.replace([np.inf,-np.inf],np.nan).dropna();n=len(s)
    if n==0:return dict(N=0,up_pct=None,mean_pct=None,median_pct=None)
    p=float((s>0).mean());z=1.96;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;err=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    out=dict(N=n,up_pct=p*100,mean_pct=float(s.mean()*100),median_pct=float(s.median()*100),wilson95_pct=[(mid-err)*100,(mid+err)*100])
    out.update({f'q{int(q*100):02d}_pct':float(s.quantile(q)*100) for q in [.05,.1,.25,.75,.9,.95]})
    return out

def main():
    k=daily('KORU').loc[:'2026-11-05'].copy()
    # Raw daily close is null. Yahoo quote metadata and Stock Analysis both report 6.53.
    patch=json.loads((ROOT/'yahoo_KORU_raw.json').read_text())['chart']['result'][0]['meta']['regularMarketPrice']
    assert patch==6.53
    k.loc['2026-11-05',['Close','Adj Close']]=patch
    k['r']=k['Adj Close'].pct_change(fill_method=None)
    k['price_r']=k.Close.pct_change(fill_method=None)
    k['fwd']=k.r.shift(-1)
    k['fwd_price']=k.price_r.shift(-1)
    k['ma20']=k.Close.rolling(20).mean()
    k['ma5']=k.Close.rolling(5).mean()
    k['ma60']=k.Close.rolling(60).mean()
    k['clv']=(k.Close-k.Low)/(k.High-k.Low)
    k['vol20']=k.r.rolling(20).std()
    tr=pd.concat([k.High-k.Low,(k.High-k.Close.shift()).abs(),(k.Low-k.Close.shift()).abs()],axis=1).max(axis=1)
    k['atr14_sma']=tr.rolling(14).mean()
    delta=k.Close.diff();up=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();down=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    k['rsi14']=100-100/(1+up/down)
    k['dd60']=k.Close/k.Close.rolling(60).max()-1
    masks={
      'all':pd.Series(True,index=k.index),
      'last60':pd.Series(k.index>=k.index[-61],index=k.index),
      'drop10':k.r<=-.10,
      'drop20':k.r<=-.20,
      'drop30':k.r<=-.30,
      'drop10_below20':(k.r<=-.10)&(k.Close<k.ma20),
      'drop10_below20_low20':(k.r<=-.10)&(k.Close<k.ma20)&(k.clv<=.20),
      '2026_drop10':(k.r<=-.10)&(k.index>='2026-01-01'),
      '2026_drop20':(k.r<=-.20)&(k.index>='2026-01-01'),
    }
    tab={};threshold=6.46/6.53-1
    for label,m in masks.items():
        cohort=k[m&k.fwd.notna()].copy()
        tab[label]=stats(cohort.fwd)
        tab[label]['up_vs_current_discount_pct']=float((cohort.fwd>threshold).mean()*100) if len(cohort) else None
        tab[label]['price_return_sensitivity']=stats(cohort.fwd_price)
        cohort.to_csv(ROOT/('cohort_'+label+'.csv'),index_label='signal_date')
    k.to_csv(ROOT/'daily_context.csv',index_label='date')
    # Closed-session mark at each KST 10:42: last completed US post-market bar.
    ah_tables={};contexts={}
    for iv,minutes in [('5m',5),('1h',60)]:
        f=intraday('KORU',iv);f=f[(f.index.hour>=19)&(f.index.hour<20)]
        rows=[]
        minute=intraday('KORU','1m')
        minute=minute[(minute.index.hour==19)]
        groups={date:(g,minutes,iv) for date,g in f.groupby(f.index.date)}
        # 5m/1h responses omit 19:00-20:00 ET on Nov 2-4. Use directly
        # observed 1m closes for those dates; never forward-fill a stale mark.
        for date,g in minute.groupby(minute.index.date):
            if date not in groups:groups[date]=(g,1,'1m_fallback')
        for date,(g,bar_minutes,source) in sorted(groups.items()):
            ts=g.index[-1];end=ts+pd.Timedelta(minutes=bar_minutes)
            evaltime=end.tz_convert('Asia/Seoul').normalize()+pd.Timedelta(hours=10,minutes=42)
            if evaltime>BASE or not 0<=(evaltime-end).total_seconds()<=7200:continue
            day=pd.Timestamp(date)
            if day not in k.index:continue
            rows.append(dict(eval_kst=evaltime,bar_start=ts,bar_end=end,source_interval=source,et_date=str(date),price=float(g.iloc[-1].Close),close=float(k.loc[day,'Close']),day_return=float(k.loc[day,'r']),lag_min=(evaltime-end).total_seconds()/60))
        t=pd.DataFrame(rows).set_index('eval_kst').sort_index()
        t['next_eval']=t.index.to_series().shift(-1);t['next_price']=t.price.shift(-1)
        t['elapsed_hours']=(t.next_eval-t.index.to_series()).dt.total_seconds()/3600
        t['fwd']=t.next_price/t.price-1;t['ah_gap']=t.price/t.close-1
        valid=t[t.elapsed_hours==24].copy()
        contexts[iv]=valid
        valid.to_csv(ROOT/('afterhours_'+iv+'_pairs.csv'),index_label='eval_kst')
        masks2={'all':pd.Series(True,index=valid.index),'drop10':valid.day_return<=-.10,'drop10_ah_negative':(valid.day_return<=-.10)&(valid.ah_gap<0),'drop20':valid.day_return<=-.20,'recent2026':valid.index>='2026-01-01'}
        ah_tables[iv]={label:stats(valid.loc[m,'fwd']) for label,m in masks2.items()}
        ah_tables[iv]['first_eval']=str(valid.index.min());ah_tables[iv]['last_eval']=str(valid.index.max())
        ah_tables[iv]['max_lag_min']=float(valid.lag_min.max());ah_tables[iv]['latest']=t.tail(4).reset_index().astype(str).to_dict('records')
    # Last-hour post-market marks are price proxies, not executable bid/ask quotes.
    snapshots=[];q={x['symbol']:x['meta'] for x in json.loads((ROOT/'quote_manifest.json').read_text())}
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for rec in manifest['history']:
        if rec['interval']!='1m':continue
        sym=rec['symbol'];stem=rec['file'][:-7];f=intraday(stem)
        before=f[f.index+pd.Timedelta(minutes=1)<=BASE];row=before.iloc[-1]
        d=daily(stem);prev=d[d.index<'2026-11-05'].dropna(subset=['Close']).iloc[-1].Close
        regular=q.get(sym,{}).get('regularMarketPrice')
        if sym=='KORU':regular=patch
        if sym=='^VIX':regular=28.18
        if sym=='SOXX':prev/=3
        if sym=='^KS11':prev=5383.8;regular=None
        if sym in ['005930.KS','000660.KS']:prev=d.loc['2026-11-05','Close'];regular=None
        item=dict(symbol=sym,asof_bar_kst=str(before.index[-1].tz_convert('Asia/Seoul')),asof_price=float(row.Close),checked_at_kst=rec['retrieved_at_kst'],latest_bar_kst=str(f.index[-1].tz_convert('Asia/Seoul')),latest_price=float(f.iloc[-1].Close),prior_reference=float(prev))
        if regular is not None and sym not in ['KRW=X']:
            item.update(regular_close=float(regular),regular_return_pct=(regular/prev-1)*100,ah_vs_close_pct=(row.Close/regular-1)*100)
        if sym in ['^KS11','005930.KS','000660.KS']:item['vs_prior_pct']=(row.Close/prev-1)*100
        if sym in ['ES=F','NQ=F']:
            ref=f[(f.index.strftime('%Y-%m-%d %H:%M')=='2026-11-05 15:59')].iloc[-1].Close
            item['us1559_reference']=float(ref);item['since_us1559_pct']=(row.Close/ref-1)*100
        snapshots.append(item)
    # Regression is diagnostic: US date D-1 versus Korean date D, only observed full days.
    e=daily('EWY').loc[:'2026-11-05'];e.loc['2026-11-05',['Close','Adj Close']]=q['EWY']['regularMarketPrice'];e['r']=e['Adj Close'].pct_change(fill_method=None)
    kr=daily('_KS11').loc[:'2026-11-05'];kr.loc[pd.Timestamp('2026-11-05'),'Close']=5383.8;kr=kr.sort_index();kr['r']=kr.Close.pct_change(fill_method=None)
    rows=[]
    for date,row in kr.iterrows():
        us=date-pd.Timedelta(days=1)
        if us in e.index and pd.notna(row.r) and pd.notna(e.loc[us,'r']):rows.append(dict(korea_date=date,us_date=us,x=float(e.loc[us,'r']),y=float(row.r)))
    reg=pd.DataFrame(rows).tail(252)
    X=np.column_stack([np.ones(len(reg)),reg.x]);coef=np.linalg.lstsq(X,reg.y,rcond=None)[0];resid=reg.y-X@coef
    reg.to_csv(ROOT/'lead_lag_regression.csv',index=False)
    regression=dict(N=len(reg),start=str(reg.korea_date.iloc[0].date()),end=str(reg.korea_date.iloc[-1].date()),alpha_pct=float(coef[0]*100),beta=float(coef[1]),r_squared=float(1-(resid**2).sum()/((reg.y-reg.y.mean())**2).sum()),rmse_pct=float(np.sqrt(np.mean(resid**2))*100),korean_return_stats=stats(reg.y),current_ewy_return_pct=float(e.loc['2026-11-05','r']*100),implied_korea_full_day_pct=float((coef[0]+coef[1]*e.loc['2026-11-05','r'])*100))
    latest={c:float(k.iloc[-1][c]) for c in ['Close','r','ma5','ma20','ma60','clv','vol20','atr14_sma','rsi14','dd60']}
    latest['daily_start']=str(k.index[0].date());latest['daily_end']=str(k.index[-1].date());latest['rows']=len(k)
    latest['volume_vs20prior']=float(k.Volume.iloc[-1]/k.Volume.iloc[-21:-1].mean())
    result=dict(base_price=6.46,raw_last_minute=6.4585,prev_close=patch,base_vs_prev_pct=(6.46/patch-1)*100,daily_stats=tab,technical=latest,afterhours_stats=ah_tables,snapshots=snapshots,regression=regression,recent_extreme_cases=k[(k.r<=-.10)&(k.index>='2026-06-01')][['Close','r','fwd','clv']].reset_index().astype(str).to_dict('records'))
    save('analysis.json',result)
    print(json.dumps({x:result[x] for x in ['technical','daily_stats','afterhours_stats','regression','recent_extreme_cases']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
