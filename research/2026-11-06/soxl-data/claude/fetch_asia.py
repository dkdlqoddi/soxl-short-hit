"""아시아 반도체·지수 시세 수집 (11/5 한국·일본장이 SOXL 프리마켓에 준 영향 확인용)."""
import time, json, datetime as dt, urllib.request
import yfinance as yf

KST = dt.timezone(dt.timedelta(hours=9))
# 일본 반도체 4종과 SKHY도 받아 봤지만 쓰지 않아 지웠다 (일본 종가는 review_peers.py의 1개월 일봉으로 확인).
DAILY = {"^KS11", "000660.KS"}                      # 장기 일봉은 4.5절 통계에 쓰는 두 종목만
for s in ["^KS11", "000660.KS", "005930.KS", "^N225"]:
    fn = s.replace("^", "").replace("=", "").replace(".", "_")
    kinds = [("1m", dict(period="5d", interval="1m", prepost=True))]
    if s in DAILY:
        kinds.append(("1d", dict(period="max", interval="1d", auto_adjust=False)))
    for kind, kw in kinds:
        df = None
        for attempt in range(3):
            try:
                df = yf.Ticker(s).history(**kw)
                if len(df):
                    break
            except Exception as e:  # noqa
                print(s, kind, "retry", e)
            time.sleep(2)
        if df is None or not len(df):
            print(s, kind, "EMPTY"); continue
        df.to_csv(f"{fn}_{kind}.csv")
        print(s, kind, len(df), df.index[0], df.index[-1])

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
snap = {"fetched_at_kst": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")}
for name, url in {"KOSPI": "https://m.stock.naver.com/api/index/KOSPI/basic",
                  "samsung": "https://m.stock.naver.com/api/stock/005930/basic",
                  "hynix": "https://m.stock.naver.com/api/stock/000660/basic"}.items():
    try:
        snap[name] = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read())
    except Exception as e:  # noqa
        snap[name] = {"error": str(e)}
json.dump(snap, open("naver_snapshot.json", "w"), ensure_ascii=False, indent=1)
for k in ("KOSPI", "samsung", "hynix"):
    d = snap[k]
    print(k, {x: d.get(x) for x in ("closePrice", "compareToPreviousClosePrice", "fluctuationsRatio", "localTradedAt", "marketStatus")})
print("fetched", snap["fetched_at_kst"])
