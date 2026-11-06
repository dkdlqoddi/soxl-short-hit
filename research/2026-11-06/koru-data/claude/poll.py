"""만기 이후 경로 기록용 폴러 (Claude Fable Max, KORU 11/5 회차 복기).
네이버 모바일 API(코스피·코스닥·삼성전자·SK하이닉스)와 yfinance 1분봉(KORU·EWY·SOXX·MU, 시간외 포함)의
마지막 값을 3분마다 poll_log.csv에 덧붙인다. 실행: python3 poll.py <반복 횟수>
"""
import sys, json, time, datetime as dt, urllib.request
from pathlib import Path
import yfinance as yf

OUT = Path(__file__).resolve().parent / "poll_log.csv"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
KST = dt.timezone(dt.timedelta(hours=9))

def naver(path):
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://m.stock.naver.com/api/{path}/basic", headers=UA), timeout=10) as r:
            d = json.load(r)
        return d.get("closePrice", ""), d.get("fluctuationsRatio", ""), (d.get("localTradedAt") or "")[11:19]
    except Exception as e:  # noqa
        return "", "", f"ERR {type(e).__name__}"

def last(sym):
    try:
        df = yf.Ticker(sym).history(period="1d", interval="1m", prepost=True, auto_adjust=False)
        t = df.index[-1].tz_convert("Asia/Seoul").strftime("%H:%M")
        return f"{df['Close'].iloc[-1]:.4f}", t
    except Exception as e:  # noqa
        return "", f"ERR {type(e).__name__}"

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
if not OUT.exists():
    OUT.write_text("polled_kst,kospi,kospi_pct,kospi_t,kosdaq,kosdaq_pct,samsung,samsung_pct,hynix,hynix_pct,koru,koru_t,ewy,ewy_t,soxx,soxx_t,mu,mu_t\n", encoding="utf-8")
for i in range(n):
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    ks, kq, ss, hx = naver("index/KOSPI"), naver("index/KOSDAQ"), naver("stock/005930"), naver("stock/000660")
    row = [now, ks[0].replace(",", ""), ks[1], ks[2], kq[0].replace(",", ""), kq[1], ss[0].replace(",", ""), ss[1], hx[0].replace(",", ""), hx[1]]
    for sym in ("KORU", "EWY", "SOXX", "MU"):
        row += list(last(sym))
    with OUT.open("a", encoding="utf-8") as f:
        f.write(",".join(row) + "\n")
    if i < n - 1:
        time.sleep(180)
