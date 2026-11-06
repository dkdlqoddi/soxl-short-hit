"""KORU 24h forecast (2026-11-06, base 10:42 KST) — 분석 중 한국장·선물 경로 기록용 폴러 (Claude Fable Max).
네이버 모바일 API(코스피·코스닥·삼성전자·SK하이닉스·KODEX MSCI Korea TR·투자자별 순매수)와
yfinance 1분봉(원/달러, S&P500·나스닥100 선물)의 마지막 값을 3분마다 fc_poll_log.csv에 덧붙인다.
실행: python3 fc_poll.py <반복 횟수>
"""
import sys, json, time, datetime as dt, urllib.request
from pathlib import Path
import yfinance as yf

OUT = Path(__file__).resolve().parent / "fc_poll_log.csv"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
KST = dt.timezone(dt.timedelta(hours=9))

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10) as r:
        return json.load(r)

def naver(path):
    try:
        d = get(f"https://m.stock.naver.com/api/{path}/basic")
        return d.get("closePrice", "").replace(",", ""), d.get("fluctuationsRatio", ""), (d.get("localTradedAt") or "")[11:19]
    except Exception as e:  # noqa
        return "", "", f"ERR {type(e).__name__}"

def flows():
    try:
        d = get("https://m.stock.naver.com/api/index/KOSPI/trend")
        return [d.get(k, "").replace(",", "") for k in ("personalValue", "foreignValue", "institutionalValue")]
    except Exception as e:  # noqa
        return ["", "", f"ERR {type(e).__name__}"]

def last(sym):
    try:
        df = yf.Ticker(sym).history(period="1d", interval="1m", prepost=True, auto_adjust=False)
        t = df.index[-1].tz_convert("Asia/Seoul").strftime("%H:%M")
        return f"{df['Close'].iloc[-1]:.4f}", t
    except Exception as e:  # noqa
        return "", f"ERR {type(e).__name__}"

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
if not OUT.exists():
    OUT.write_text("polled_kst,kospi,kospi_pct,kospi_t,kosdaq,kosdaq_pct,samsung,samsung_pct,hynix,hynix_pct,msci_tr,msci_tr_pct,indiv_100m,foreign_100m,inst_100m,usdkrw,usdkrw_t,es,es_t,nq,nq_t\n", encoding="utf-8")
for i in range(n):
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    ks, kq, ss, hx, tr = naver("index/KOSPI"), naver("index/KOSDAQ"), naver("stock/005930"), naver("stock/000660"), naver("stock/278540")
    row = [now, ks[0], ks[1], ks[2], kq[0], kq[1], ss[0], ss[1], hx[0], hx[1], tr[0], tr[1]] + flows()
    for sym in ("KRW=X", "ES=F", "NQ=F"):
        row += list(last(sym))
    with OUT.open("a", encoding="utf-8") as f:
        f.write(",".join(row) + "\n")
    if i < n - 1:
        time.sleep(180)
