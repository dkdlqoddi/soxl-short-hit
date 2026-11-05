#!/usr/bin/env python3
"""SOXL·KORU 24시간 예측·복기 — 3모델 tmux 자동 실행기.

Claude Fable Max(claude), Codex Astra Max(codex), Antigravity Argon High(agy)에
같은 프롬프트(automation/prompts/)로 네 작업을 시킵니다.

  soxl-review    직전 회차 SOXL 24시간 예측 복기
  soxl-forecast  오늘 SOXL 24시간 방향 예측
  koru-review    직전 회차 KORU 24시간 예측 복기
  koru-forecast  오늘 KORU 24시간 방향 예측

흐름
  1단계 복기  3모델 × (SOXL, KORU)를 tmux 창(모델별)·칸(종목별)에서 동시에 실행
  2단계 예측  1단계가 모두 끝난 시각을 세 모델 공통 기준 시각으로 정하고 동시에 실행
  마무리      산출물 확인 → 볼트 누락분 업로드 → 통합 비교 노트(저장소·볼트) →
              직전 통합 비교 노트에 채점 결과 기록 → 볼트 README 아카이브·저장소 README 목록 →
              git commit → git push origin main

모델은 저장소 노트·볼트 노트(obsidian MCP)·메타 JSON을 직접 만듭니다.
README·통합 비교 노트·git은 동시 편집 충돌을 막기 위해 이 스크립트만 다룹니다.

사용 예
  python3 automation/daily_forecast.py                  # tmux 세션을 띄우고 바로 돌아옴
  python3 automation/daily_forecast.py --attach         # 띄운 뒤 세션에 붙음
  python3 automation/daily_forecast.py --dry-run        # 계획과 프롬프트만 만들어 봄
  python3 automation/daily_forecast.py --tasks koru-review,koru-forecast --models claude,codex
  python3 automation/daily_forecast.py --no-push        # 커밋까지만
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

# ───────────────────────────── 설정 ─────────────────────────────

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")

SCRIPT = Path(__file__).resolve()
AUTOMATION_DIR = SCRIPT.parent
REPO = AUTOMATION_DIR.parent
PROMPTS_DIR = AUTOMATION_DIR / "prompts"
RUNS_DIR = AUTOMATION_DIR / "runs"

GIT_REMOTE = "origin"
GIT_BRANCH = "main"
VAULT_STOCK = "PERSONAL/STOCK"
OBSIDIAN_BASES = ("http://127.0.0.1:27123", "https://127.0.0.1:27124")
OBSIDIAN_MCP_URL = "http://127.0.0.1:27123/mcp/"

# 모델별 CLI 설정 — 모델 이름이나 추론 강도를 바꿀 때는 여기만 고칩니다.
CLAUDE_MODEL = "fable"              # claude --model (fable = Claude Fable 5.1)
CLAUDE_EFFORT = "max"
CODEX_MODEL = "gpt-6-astra"         # codex exec -m
CODEX_EFFORT = "max"                # -c model_reasoning_effort
AGY_MODEL = "gemini-4-argon-high"   # agy --model (Gemini 4 Argon High)

TASKS = ("soxl-review", "soxl-forecast", "koru-review", "koru-forecast")
PROMPT_TOKEN = "@@PROMPT@@"
POLL_SECONDS = 5
MAX_COMMIT_FILE_MB = 20
WATCH_PATHS = ("research", "README.md")
JUNK_RE = re.compile(r"(^|/)(__pycache__|\.ipynb_checkpoints)(/|$)|\.pyc$|(^|/)\.DS_Store$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# 부모 Claude Code 세션 표시 변수. 남아 있으면 자식 claude가 중첩 세션으로 동작할 수 있습니다.
STRIP_ENV = (
    "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_EXECPATH", "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_PID",
    "CLAUDE_EFFORT",
)


@dataclass(frozen=True)
class Model:
    key: str                  # --models 에 쓰는 이름
    name: str                 # 볼트 가이드의 표준 모델 명칭
    short: str                # README·커밋 메시지용 짧은 이름
    repo_slug: str            # research/<날짜>/<ticker>-forecast-24h-<repo_slug>.md
    vault_slug: str           # PERSONAL/STOCK/<TICKER>/<날짜>-<vault_slug>.md
    aliases: tuple[str, ...]  # 예전 노트 파일명에 쓰인 슬러그
    binary: str
    stream: str               # 출력 형식: claude-json | agy-json | text


MODELS: dict[str, Model] = {
    "claude": Model("claude", "Claude Fable Max", "Claude Fable", "claude", "claude-fable-max",
                    ("claude", "claude-fable", "fable"), "claude", "claude-json"),
    "codex": Model("codex", "Codex Astra Max", "Codex Astra", "codex", "codex-astra-max",
                   ("codex", "astra", "codex-astra"), "codex", "text"),
    "argon": Model("argon", "Antigravity Argon High", "AGY Argon", "argon", "antigravity-argon-high",
                   ("argon", "antigravity", "agy"), "agy", "agy-json"),
}


def build_argv(model: Model, last_message: Path, claude_mcp: Path | None) -> list[str]:
    """모델 CLI 명령. 프롬프트 자리는 PROMPT_TOKEN (작업 창에서 실제 프롬프트로 바뀜)."""
    exe = shutil.which(model.binary) or model.binary
    if model.key == "claude":
        argv = [exe, "-p", "--model", CLAUDE_MODEL, "--effort", CLAUDE_EFFORT,
                "--permission-mode", "bypassPermissions", "--output-format", "stream-json", "--verbose"]
        if claude_mcp:  # ~/.claude.json의 HTTPS 주소 대신 HTTP 포트로 obsidian MCP 연결
            argv += ["--mcp-config", str(claude_mcp), "--strict-mcp-config"]
        return argv + [PROMPT_TOKEN]
    if model.key == "codex":
        return [exe, "exec", "-m", CODEX_MODEL, "-c", f'model_reasoning_effort="{CODEX_EFFORT}"',
                "--dangerously-bypass-approvals-and-sandbox", "--color", "never",
                "-C", str(REPO), "-o", str(last_message), PROMPT_TOKEN]
    if model.key == "argon":
        return [exe, "--model", AGY_MODEL, "--dangerously-skip-permissions",
                "--output-format", "stream-json", "-p", PROMPT_TOKEN]
    raise ValueError(model.key)


@dataclass(frozen=True)
class Ticker:
    symbol: str
    desc: str
    prev_patterns: tuple[str, ...]  # 직전 예측 노트 파일명 (slug 그룹 = 모델)

    @property
    def lower(self) -> str:
        return self.symbol.lower()


TICKERS: dict[str, Ticker] = {
    "SOXL": Ticker(
        "SOXL",
        "**SOXL** (Direxion Daily Semiconductor Bull 3X Shares) — ICE 반도체 지수 일간 수익률의 3배를 "
        "추적합니다. 함께 볼 것: SOXX·SMH, NVDA·AMD·AVGO·MU·TSM·ASML, 나스닥100 선물(NQ=F), VIX, "
        "미 국채 10년물, 반도체 실적·수출 규제 뉴스.",
        (r"soxl-forecast-24h-(?P<slug>[a-z]+)\.md", r"forecast-24h-(?P<slug>[a-z]+)\.md"),
    ),
    "KORU": Ticker(
        "KORU",
        "**KORU** (Direxion Daily MSCI South Korea Bull 3X Shares) — EWY(iShares MSCI South Korea) "
        "일간 수익률의 3배를 추적하며 미국 시간에만 거래됩니다. 함께 볼 것: EWY, 코스피·코스피200 "
        "야간선물, 삼성전자·SK하이닉스(넥스트레이드 포함), 원/달러 환율, 미국 반도체(SOXX·MU), 외국인 수급.",
        (r"koru-forecast-24h-(?P<slug>[a-z]+)\.md",),
    ),
}

SESSION_KO = {
    "premarket": "미국 프리마켓",
    "regular": "미국 정규장",
    "aftermarket": "미국 애프터마켓",
    "closed": "미국 장 닫힘 (체결 없음)",
}

# ───────────────────────────── 공용 도우미 ─────────────────────────────


class _Log:
    file: Path | None = None


LOG = _Log()


def log(msg: str) -> None:
    line = f"[{now_kst():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if LOG.file:
        with open(LOG.file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def now_kst() -> dt.datetime:
    return dt.datetime.now(KST)


def fmt_kst(t: dt.datetime) -> str:
    return t.astimezone(KST).strftime("%Y-%m-%d %H:%M")


def fmt_et(t: dt.datetime) -> str:
    e = t.astimezone(ET)
    return e.strftime("%m/%d %H:%M ") + (e.tzname() or "ET")


def rel(p: Path | str) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(p)


def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def write_json(p: Path, obj: object) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, p)


def read_json_loose(p: Path) -> object | None:
    """JSON 파일 읽기. 앞뒤에 다른 글이 붙어 있으면 가장 바깥 {...}만 다시 시도."""
    try:
        text = Path(p).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group())
            except ValueError:
                return None
    return None


def num(v: object) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:\.\d+)?", v.replace(",", "").replace("−", "-"))
        return float(m.group()) if m else None
    return None


def money(v: object) -> str:
    x = num(v)
    return f"${x:,.2f}" if x is not None else "—"


def pct(v: object, signed: bool = False) -> str:
    x = num(v)
    if x is None:
        return "—"
    return f"{x:+.2f}%" if signed else f"{x:.0f}%"


def cell(v: object) -> str:
    s = "—" if v in (None, "", [], {}) else str(v)
    return s.replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def clip(s: object, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def yaml_str(s: str) -> str:
    return json.dumps(str(s), ensure_ascii=False)


def model_from_text(text: str) -> str | None:
    t = (text or "").lower()
    if "claude" in t or "fable" in t:
        return "claude"
    if "codex" in t or "astra" in t or "gpt" in t:
        return "codex"
    if "argon" in t or "antigravity" in t or "agy" in t or "gemini" in t:
        return "argon"
    return None


def slug_to_model(slug: str) -> str | None:
    for key, m in MODELS.items():
        if slug in m.aliases:
            return key
    return None


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    # 무인 실행 중 자격 증명 입력을 기다리며 멈추지 않도록 프롬프트를 끔 (실패하면 로그에 남김)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", "-C", str(REPO), *args], text=True, capture_output=True, check=check, env=env)


# ───────────────────────────── 시장 시간 ─────────────────────────────


def us_session(t: dt.datetime) -> str:
    e = t.astimezone(ET)
    if e.weekday() >= 5:
        return "closed"
    hm = e.hour * 60 + e.minute
    if 240 <= hm < 570:
        return "premarket"
    if 570 <= hm < 960:
        return "regular"
    if 960 <= hm < 1200:
        return "aftermarket"
    return "closed"


def us_sessions_text(date_str: str) -> str:
    """한국 날짜 D 저녁에 열리는 미국 거래일(미국 날짜 D)의 세션을 KST로."""
    d = dt.date.fromisoformat(date_str)

    def k(h: int, m: int) -> str:
        return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ET).astimezone(KST).strftime("%H:%M")

    tz = dt.datetime(d.year, d.month, d.day, 12, tzinfo=ET).tzname()
    return (f"프리마켓 {k(4, 0)}~{k(9, 30)} · 정규장 {k(9, 30)}~{k(16, 0)} · 애프터마켓 {k(16, 0)}~{k(20, 0)} KST "
            f"(미국 동부 04:00~20:00 {tz})")


def us_trading_overlap(start: dt.datetime, end: dt.datetime) -> bool:
    """[start, end] 안에 미국 주중 04:00~20:00 ET가 조금이라도 있는지 (공휴일은 무시)."""
    d = start.astimezone(ET).date() - dt.timedelta(days=1)
    last = end.astimezone(ET).date()
    while d <= last:
        if d.weekday() < 5:
            s = dt.datetime(d.year, d.month, d.day, 4, 0, tzinfo=ET)
            e = dt.datetime(d.year, d.month, d.day, 20, 0, tzinfo=ET)
            if s < end and e > start:
                return True
        d += dt.timedelta(days=1)
    return False


def quote_snapshot(symbol: str, at: dt.datetime) -> dict:
    """기준 시각의 1분봉 종가(시간외 포함)와 직전 정규장 종가. 실패하면 error만 담아 돌려줌."""
    try:
        import pandas as pd
        import yfinance as yf

        tk = yf.Ticker(symbol)
        m1 = tk.history(period="5d", interval="1m", prepost=True)
        if m1.empty:
            return {"symbol": symbol, "error": "1분봉 없음"}
        m1 = m1[m1.index <= pd.Timestamp(at).tz_convert(m1.index.tz)]
        if m1.empty:
            return {"symbol": symbol, "error": "기준 시각 이전 1분봉 없음"}
        bar_t = m1.index[-1].to_pydatetime()
        price = float(m1["Close"].iloc[-1])
        d1 = tk.history(period="15d", interval="1d")
        e = at.astimezone(ET)
        after_close = (e.hour, e.minute) >= (16, 0)
        closes = [(idx.date(), float(c)) for idx, c in d1["Close"].items()
                  if idx.date() < e.date() or (after_close and idx.date() == e.date())]
        prev_date, prev_close = closes[-1] if closes else (None, None)
        out = {
            "symbol": symbol, "price": round(price, 4),
            "bar_time_kst": fmt_kst(bar_t), "bar_time_et": fmt_et(bar_t), "session": us_session(bar_t),
            "prev_close": round(prev_close, 4) if prev_close else None,
            "prev_close_date": prev_date.isoformat() if prev_date else None,
        }
        if prev_close:
            out["vs_prev_close_pct"] = round((price / prev_close - 1) * 100, 2)
        return out
    except Exception as exc:  # 네트워크·패키지 문제는 모델이 직접 확인하도록 넘김
        return {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}


def snapshot_text(s: dict | None) -> str:
    if not s or s.get("error"):
        reason = (s or {}).get("error", "미실행")
        return f"스냅샷 실패({clip(reason, 80)}) — 기준 시각 가격을 직접 확인하세요"
    txt = (f"**{s['symbol']} {money(s['price'])}** — 1분봉 {s['bar_time_kst']} KST ({s['bar_time_et']}), "
           f"{SESSION_KO.get(s['session'], s['session'])}")
    if s.get("prev_close"):
        txt += (f" · 직전 정규장 종가 {money(s['prev_close'])} ({s['prev_close_date']}, "
                f"기준가는 이 종가 대비 {pct(s.get('vs_prev_close_pct'), signed=True)})")
    return txt


# ───────────────────────────── Obsidian REST ─────────────────────────────


def find_obsidian_token() -> str | None:
    if os.environ.get("OBSIDIAN_API_KEY"):
        return os.environ["OBSIDIAN_API_KEY"]
    for cfg in ("~/.claude.json", "~/.gemini/config/mcp_config.json"):
        try:
            data = json.loads(Path(cfg).expanduser().read_text(encoding="utf-8"))
            auth = data["mcpServers"]["obsidian"]["headers"]["Authorization"]
            return auth.split()[-1]
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            continue
    return None


class Vault:
    """Obsidian Local REST API 클라이언트 (HTTP 27123 → HTTPS 27124 순서로 시도)."""

    def __init__(self, token: str):
        self.token = token
        self.base: str | None = None
        self._tls = ssl._create_unverified_context()  # 플러그인의 자체 서명 인증서

    def _request(self, method: str, path: str, data: bytes | None = None,
                 headers: dict | None = None) -> tuple[int, bytes]:
        last: Exception | None = None
        for base in ([self.base] if self.base else list(OBSIDIAN_BASES)):
            req = urllib.request.Request(base + path, data=data, method=method,
                                         headers={"Authorization": f"Bearer {self.token}", **(headers or {})})
            try:
                ctx = self._tls if base.startswith("https") else None
                with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                    self.base = base
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                self.base = base
                return e.code, e.read()
            except (urllib.error.URLError, OSError) as e:
                last = e
        raise ConnectionError(f"Obsidian REST API 연결 실패: {last}")

    @staticmethod
    def _path(vpath: str) -> str:
        return "/vault/" + urllib.parse.quote(vpath.lstrip("/"))

    def ping(self) -> bool:
        try:
            return self._request("GET", self._path(VAULT_STOCK + "/"))[0] == 200
        except ConnectionError:
            return False

    def list_dir(self, vdir: str) -> list[str]:
        code, body = self._request("GET", self._path(vdir.rstrip("/") + "/"))
        if code != 200:
            return []
        try:
            return list(json.loads(body).get("files", []))
        except ValueError:
            return []

    def read(self, vpath: str) -> str | None:
        code, body = self._request("GET", self._path(vpath), headers={"Accept": "text/markdown"})
        return body.decode("utf-8") if code == 200 else None

    def exists(self, vpath: str) -> bool:
        return self.read(vpath) is not None

    def write(self, vpath: str, content: str) -> None:
        code, body = self._request("PUT", self._path(vpath), data=content.encode("utf-8"),
                                   headers={"Content-Type": "text/markdown; charset=utf-8"})
        if code not in (200, 201, 204):
            raise RuntimeError(f"볼트 쓰기 실패 {vpath}: HTTP {code} {body[:200]!r}")


def write_claude_mcp_config(path: Path, token: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {"obsidian": {"type": "http", "url": OBSIDIAN_MCP_URL,
                                               "headers": {"Authorization": f"Bearer {token}"}}}}, f)
    return path


# ───────────────────────────── 작업 정의 ─────────────────────────────


def note_filename(t: Ticker, kind: str, m: Model) -> str:
    return f"{t.lower}-forecast-24h-{m.repo_slug}.md" if kind == "forecast" else f"{t.lower}-review-{m.repo_slug}.md"


@dataclass
class Job:
    model: Model
    ticker: Ticker
    kind: str                   # review | forecast
    date: str
    reviewed_date: str | None = None
    attempt: int = 0
    state: str = "pending"      # pending → running → done | failed | skipped
    pane: str | None = None
    started: float | None = None
    ended: float | None = None
    status: dict = field(default_factory=dict)
    note_ok: bool = False
    meta_ok: bool = False
    vault_result: str = ""
    message: str = ""

    @property
    def id(self) -> str:
        return f"{self.ticker.lower}-{self.kind}-{self.model.repo_slug}"

    @property
    def label(self) -> str:
        if self.kind == "review":
            return f"{self.ticker.symbol} 직전 회차({self.reviewed_date}) 24시간 예측 복기"
        return f"{self.ticker.symbol} 24시간 주가 방향 예측"

    @property
    def repo_note(self) -> str:
        return f"research/{self.date}/{note_filename(self.ticker, self.kind, self.model)}"

    @property
    def vault_note(self) -> str:
        if self.kind == "forecast":
            return f"{VAULT_STOCK}/{self.ticker.symbol}/{self.date}-{self.model.vault_slug}.md"
        return f"{VAULT_STOCK}/{self.ticker.symbol}/{self.reviewed_date}-review-{self.model.vault_slug}.md"

    @property
    def meta_path(self) -> str:
        return f"research/{self.date}/meta/{self.id}.json"

    @property
    def work_dir(self) -> str:
        return f"research/{self.date}/{self.ticker.lower}-data/{self.model.repo_slug}"


@dataclass
class PrevNote:
    model: Model
    date: str
    repo_path: str
    vault_path: str | None
    base: dt.datetime | None = None


@dataclass
class PrevRound:
    ticker: Ticker
    date: str                  # 회차 날짜 (가장 최근 노트 날짜)
    notes: list[PrevNote]
    summaries: list[str]       # 볼트 통합 비교 노트


@dataclass
class Run:
    args: argparse.Namespace
    run_id: str
    date: str
    run_dir: Path
    session: str
    vault: Vault | None = None
    claude_mcp: Path | None = None
    prev: dict = field(default_factory=dict)
    jobs: list = field(default_factory=list)
    base: dict | None = None
    panes: dict = field(default_factory=dict)   # 모델 키 → [pane id]
    busy: dict = field(default_factory=dict)    # pane id → job id
    groups: list = field(default_factory=list)  # 종목별 마무리 정보
    commit: str | None = None
    pushed: bool = False

    def fallback_path(self, job: Job) -> Path:
        return self.run_dir / "vault-fallback" / f"{job.id}.md"

    def status_path(self, job: Job) -> Path:
        return self.run_dir / "status" / f"{job.id}.json"

    @property
    def vault_on(self) -> bool:
        return self.vault is not None and not self.args.no_vault


BASE_RE = re.compile(r"(?:base_time_kst|기준 시각)[^0-9\n]{0,20}(\d{4}-\d{2}-\d{2})(?:\([^)\n]{1,3}\))?[ T]*(\d{1,2}):(\d{2})")
ROUND_GAP = dt.timedelta(hours=12)  # 기준 시각이 이보다 벌어지면 다른 회차


def note_base_time(*texts: str | None) -> dt.datetime | None:
    """메타·볼트 프론트매터·노트 본문에서 첫 '기준 시각'(KST)을 읽음."""
    for text in texts:
        m = BASE_RE.search(text or "")
        if m:
            try:
                return dt.datetime.fromisoformat(f"{m[1]} {int(m[2]):02d}:{m[3]}").replace(tzinfo=KST)
            except ValueError:
                continue
    return None


def find_prev_round(t: Ticker, today: str, vault: Vault | None, pin: str | None) -> PrevRound | None:
    """모델별 최신 예측 노트를 찾아, 가장 늦은 기준 시각에서 12시간 안의 노트를 한 회차로 묶음.

    폴더 날짜만으로는 부족합니다. 예전 노트는 Argon이 미국 날짜, 나머지가 한국 날짜로 폴더를 잡아
    같은 회차가 이틀에 걸치기도 하고, 다른 회차가 하루 차이로 붙어 있기도 합니다.
    """
    limit = pin or (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
    latest: dict[str, tuple[str, str]] = {}  # 모델 → (폴더 날짜, 파일 이름)
    for d in sorted(p for p in (REPO / "research").iterdir() if p.is_dir() and DATE_RE.fullmatch(p.name)):
        if d.name > limit:
            continue
        for f in sorted(d.iterdir()):
            for pat in t.prev_patterns:
                m = re.fullmatch(pat, f.name)
                key = slug_to_model(m["slug"]) if m else None
                if key and (d.name, f.name) >= latest.get(key, ("", "")):
                    latest[key] = (d.name, f.name)
    if not latest:
        return None
    names: list[str] = []
    if vault:
        try:
            names = vault.list_dir(f"{VAULT_STOCK}/{t.symbol}")
        except ConnectionError:
            vault = None
    notes = []
    for key in (k for k in MODELS if k in latest):
        d, fname = latest[key]
        m = MODELS[key]
        repo_path = f"research/{d}/{fname}"
        vpath = next((f"{VAULT_STOCK}/{t.symbol}/{d}-{s}.md" for s in (m.vault_slug, *m.aliases)
                      if f"{d}-{s}.md" in names), None)
        meta_file = REPO / f"research/{d}/meta/{t.lower}-forecast-{m.repo_slug}.json"
        vault_text = None
        if vault and vpath:
            try:
                vault_text = vault.read(vpath)
            except ConnectionError:
                vault_text = None
        base = note_base_time(meta_file.read_text(encoding="utf-8") if meta_file.exists() else None,
                              vault_text, (REPO / repo_path).read_text(encoding="utf-8", errors="replace"))
        notes.append(PrevNote(m, d, repo_path, vpath, base))
    timed = [n for n in notes if n.base]
    if timed:
        top = max(timed, key=lambda n: n.base)
        floor = (dt.date.fromisoformat(top.date) - dt.timedelta(days=1)).isoformat()
        notes = [n for n in notes if (n.base and n.base >= top.base - ROUND_GAP) or (not n.base and n.date >= floor)]
    else:
        floor = (dt.date.fromisoformat(max(n.date for n in notes)) - dt.timedelta(days=1)).isoformat()
        notes = [n for n in notes if n.date >= floor]
    round_date = max(n.date for n in notes)
    summaries = [f"{VAULT_STOCK}/{t.symbol}/{d}.md" for d in sorted({n.date for n in notes}) if f"{d}.md" in names]
    return PrevRound(t, round_date, notes, summaries)


def plan(run: Run) -> None:
    for sym, t in TICKERS.items():
        want_review = f"{t.lower}-review" in run.args.tasks
        want_forecast = f"{t.lower}-forecast" in run.args.tasks
        if not (want_review or want_forecast):
            continue
        prev = find_prev_round(t, run.date, run.vault, run.args.prev_date)
        run.prev[sym] = prev
        if want_review and not prev:
            log(f"{sym}: {run.date} 이전 예측 노트가 없어 복기를 건너뜁니다")
        for key in run.args.models:
            if want_review and prev:
                run.jobs.append(Job(MODELS[key], t, "review", run.date, reviewed_date=prev.date))
            if want_forecast:
                run.jobs.append(Job(MODELS[key], t, "forecast", run.date))


# ───────────────────────────── 프롬프트 ─────────────────────────────


def render_template(name: str, values: dict) -> str:
    text = (PROMPTS_DIR / name).read_text(encoding="utf-8")
    missing: set[str] = set()

    def sub(m: re.Match) -> str:
        if m.group(1) not in values:
            missing.add(m.group(1))
            return m.group(0)
        return str(values[m.group(1)])

    out = re.sub(r"\{\{(\w+)\}\}", sub, text)
    if missing:
        raise KeyError(f"{name}: 값이 없는 자리표시자 {sorted(missing)}")
    return out


def prev_notes_table(prev: PrevRound) -> str:
    rows = ["| 모델 | 기준 시각 (KST, 노트에서 읽음) | 저장소 노트 | 볼트 노트 |", "| --- | --- | --- | --- |"]
    for n in prev.notes:
        rows.append(f"| {n.model.name} | {fmt_kst(n.base) if n.base else '(노트에서 확인)'} | `{n.repo_path}` | "
                    f"{f'`{n.vault_path}`' if n.vault_path else '(볼트 사본 미확인 — vault_list로 찾기)'} |")
    return "\n".join(rows)


def prompt_values(run: Run, job: Job, start: dt.datetime) -> dict:
    t, m = job.ticker, job.model
    prev: PrevRound | None = run.prev.get(t.symbol)
    own_prev = next((n for n in (prev.notes if prev else []) if n.model.key == m.key), None)
    review_note = REPO / f"research/{run.date}/{note_filename(t, 'review', m)}"
    v = {
        "model_name": m.name, "repo_slug": m.repo_slug, "vault_slug": m.vault_slug,
        "run_id": run.run_id, "job_id": job.id, "task_label": job.label,
        "task_start_kst": fmt_kst(start), "task_start_et": fmt_et(start),
        "date": run.date, "repo_dir": str(REPO), "us_sessions": us_sessions_text(run.date),
        "ticker": t.symbol, "ticker_desc": t.desc,
        "repo_note": job.repo_note, "vault_note": job.vault_note, "meta_path": job.meta_path,
        "work_dir": job.work_dir, "vault_fallback": rel(run.fallback_path(job)),
        "reviewed_date": job.reviewed_date or (prev.date if prev else "—"),
        "prev_notes": prev_notes_table(prev) if prev else "(직전 회차 노트 없음)",
        "prev_summaries": ("같은 회차 통합 비교 노트: " + ", ".join(f"`{s}`" for s in prev.summaries))
                          if prev and prev.summaries else "",
        "own_prev_note": f"`{own_prev.repo_path}` ({own_prev.date})" if own_prev else "(없음)",
        "own_review": f"`{rel(review_note)}`" if review_note.exists() else "(오늘 본인 복기 노트 없음)",
        "base_kst": "—", "base_et": "—", "expiry_kst": "—", "expiry_et": "—",
        "base_session_desc": "—", "snapshot": "—",
    }
    if job.kind == "forecast" and run.base:
        b, e = run.base["base"], run.base["expiry"]
        v.update({
            "base_kst": fmt_kst(b), "base_et": fmt_et(b), "expiry_kst": fmt_kst(e), "expiry_et": fmt_et(e),
            "base_session_desc": SESSION_KO[us_session(b)],
            "snapshot": snapshot_text(run.base["snapshots"].get(t.symbol)),
        })
    return v


def render_prompt(run: Run, job: Job, start: dt.datetime) -> Path:
    values = prompt_values(run, job, start)
    task = "review.md" if job.kind == "review" else "forecast.md"
    text = render_template("common.md", values) + "\n\n---\n\n" + render_template(task, values)
    path = run.run_dir / "prompts" / f"{job.id}.md"
    write_text(path, text)
    return path


# ───────────────────────────── tmux ─────────────────────────────


class Tmux:
    def __init__(self, session: str):
        self.session = session

    def __call__(self, *args: str, check: bool = True) -> str:
        r = subprocess.run(["tmux", *args], capture_output=True, text=True)
        if check and r.returncode != 0:
            raise RuntimeError(f"tmux {' '.join(args[:3])} 실패: {r.stderr.strip()}")
        return r.stdout.strip()

    def has_session(self) -> bool:
        return subprocess.run(["tmux", "has-session", "-t", f"={self.session}"],
                              capture_output=True).returncode == 0

    def window_options(self, target: str) -> None:
        self("set-option", "-w", "-t", target, "remain-on-exit", "on")
        self("set-option", "-w", "-t", target, "pane-border-status", "top")
        self("set-option", "-w", "-t", target, "pane-border-format", " #{pane_index}: #{pane_title} ")

    def new_window(self, name: str, command: str) -> str:
        if self.has_session():
            pane = self("new-window", "-d", "-t", f"{self.session}:", "-n", name, "-c", str(REPO),
                        "-P", "-F", "#{pane_id}", command)
        else:
            pane = self("new-session", "-d", "-s", self.session, "-n", name, "-x", "240", "-y", "60",
                        "-c", str(REPO), "-P", "-F", "#{pane_id}", command)
            self("set-option", "-t", self.session, "history-limit", "100000")
        self.window_options(f"{self.session}:{name}")
        return pane

    def split(self, pane: str, command: str) -> str:
        return self("split-window", "-d", "-v", "-t", pane, "-c", str(REPO), "-P", "-F", "#{pane_id}", command)

    def respawn(self, pane: str, command: str) -> None:
        self("respawn-pane", "-k", "-t", pane, command)

    def title(self, pane: str, text: str) -> None:
        self("select-pane", "-t", pane, "-T", text, check=False)

    def pane_dead(self, pane: str) -> bool:
        return self("display-message", "-p", "-t", pane, "#{pane_dead}", check=False) == "1"


def idle_command(label: str) -> str:
    return f"printf '%s\\n' {shlex.quote(f'[{label}] 작업 대기 중…')}; exec sleep infinity"


def setup_tmux(run: Run) -> Tmux:
    tm = Tmux(run.session)
    for key in dict.fromkeys(j.model.key for j in run.jobs):
        first = tm.new_window(key, idle_command(key))
        panes = [first]
        for _ in range(max(1, run.args.max_parallel) - 1):
            panes.append(tm.split(first, idle_command(key)))
        tm("select-layout", "-t", f"{run.session}:{key}", "even-vertical", check=False)
        run.panes[key] = panes
        for p in panes:
            run.busy[p] = None
    return tm


# ───────────────────────────── 작업 실행 ─────────────────────────────


def launch_job(run: Run, tm: Tmux, job: Job, pane: str) -> None:
    job.attempt += 1
    tag = f"{job.id}.a{job.attempt}"
    logs = run.run_dir / "logs"
    spec = {
        "title": f"{job.model.name} · {job.label}",
        "job_id": job.id,
        "attempt": job.attempt,
        "argv": build_argv(job.model, logs / f"{tag}.last.txt", run.claude_mcp),
        "prompt": str(run.run_dir / "prompts" / f"{job.id}.md"),
        "cwd": str(REPO),
        "env": {"PATH": os.environ.get("PATH", "")},
        "stream": job.model.stream,
        "timeout_s": run.args.timeout_min * 60,
        "raw_log": str(logs / f"{tag}.log"),
        "pretty_log": str(logs / f"{tag}.pretty.log"),
        "final": str(logs / f"{tag}.final.md"),
        "last_message": str(logs / f"{tag}.last.txt"),
        "status": str(run.status_path(job)),
        "repo_note": job.repo_note,
    }
    spec_path = run.run_dir / "jobs" / f"{tag}.json"
    write_json(spec_path, spec)
    run.status_path(job).unlink(missing_ok=True)
    cmd = shlex.join(["env", f"PATH={os.environ.get('PATH', '')}", sys.executable, str(SCRIPT),
                      "_worker", str(spec_path)])
    tm.respawn(pane, cmd)
    tm.title(pane, f"{job.model.key} · {job.id} #{job.attempt}")
    job.state, job.pane, job.started, job.ended = "running", pane, time.time(), None
    run.busy[pane] = job.id
    log(f"▶ {job.id} 시작 (시도 {job.attempt}, 창 {run.session}:{job.model.key} {pane})")


def check_outputs(job: Job) -> None:
    note = REPO / job.repo_note
    job.note_ok = note.exists() and note.stat().st_size >= 500
    job.meta_ok = isinstance(read_json_loose(REPO / job.meta_path), dict)
    rc = job.status.get("exit_code")
    if job.note_ok:
        job.state = "done"
        notes = [] if rc == 0 else [f"종료 코드 {rc}"]
        if not job.meta_ok:
            notes.append("메타 JSON 없음 → 노트에서 추출")
        job.message = ", ".join(notes)
    else:
        job.state = "failed"
        reason = ("시간 초과" if job.status.get("timed_out") else
                  "중단됨" if job.status.get("interrupted") else
                  job.status.get("error") or f"종료 코드 {rc}")
        job.message = f"저장소 노트 없음 ({reason})"


def run_queue(run: Run, tm: Tmux, jobs: list[Job], title: str) -> None:
    queue = {k: [j for j in jobs if j.model.key == k] for k in dict.fromkeys(j.model.key for j in jobs)}
    running: list[Job] = []
    dead_since: dict[str, float] = {}
    last_progress = 0.0
    log(f"── {title}: {len(jobs)}개 작업 (tmux attach -t {run.session})")
    while any(queue.values()) or running:
        for key, q in queue.items():
            for pane in run.panes[key]:
                if q and run.busy.get(pane) is None:
                    job = q.pop(0)
                    launch_job(run, tm, job, pane)
                    running.append(job)
        time.sleep(POLL_SECONDS)
        for job in list(running):
            st = read_json_loose(run.status_path(job))
            if not isinstance(st, dict):
                if tm.pane_dead(job.pane):
                    dead_since.setdefault(job.id, time.time())
                    if time.time() - dead_since[job.id] < 15:
                        continue
                    st = {"exit_code": None, "error": "작업 창이 상태 기록 없이 종료됨"}
                else:
                    continue
            dead_since.pop(job.id, None)
            running.remove(job)
            run.busy[job.pane] = None
            job.status, job.ended = st, time.time()
            check_outputs(job)
            mins = (job.ended - (job.started or job.ended)) / 60
            log(f"{'✔' if job.state == 'done' else '✖'} {job.id} {job.state} ({mins:.0f}분)"
                f"{' — ' + job.message if job.message else ''}")
            if (job.state == "failed" and job.attempt <= run.args.retries
                    and not st.get("timed_out") and not st.get("interrupted")):
                log(f"↻ {job.id} 다시 시도합니다")
                job.state = "pending"
                queue[job.model.key].insert(0, job)
        if time.time() - last_progress >= 60 and running:
            last_progress = time.time()
            now = time.time()
            log("   실행 중: " + ", ".join(f"{j.id} {(now - (j.started or now)) / 60:.0f}분" for j in running)
                + (f" · 대기 {sum(len(q) for q in queue.values())}" if any(queue.values()) else ""))


def stop_running(run: Run, tm: Tmux) -> None:
    running = [j for j in run.jobs if j.state == "running"]
    for job in running:
        tm("send-keys", "-t", job.pane, "C-c", check=False)
    deadline = time.time() + 40
    while time.time() < deadline and any(not run.status_path(j).exists() for j in running):
        time.sleep(2)
    for job in running:
        job.status = read_json_loose(run.status_path(job)) or {"interrupted": True}
        job.state, job.message = "failed", "사용자 중단"


def run_phases(run: Run, tm: Tmux) -> None:
    reviews = [j for j in run.jobs if j.kind == "review"]
    forecasts = [j for j in run.jobs if j.kind == "forecast"]
    if reviews:
        start = now_kst()
        for j in reviews:
            render_prompt(run, j, start)
        run_queue(run, tm, reviews, "1단계 복기")
    if not forecasts:
        return
    base = now_kst().replace(second=0, microsecond=0)
    expiry = base + dt.timedelta(hours=24)
    if not us_trading_overlap(base, expiry) and not run.args.force_forecast:
        log(f"{fmt_kst(base)}부터 24시간 동안 미국장 거래가 없어 예측을 건너뜁니다 (--force-forecast로 강제)")
        for j in forecasts:
            j.state, j.message = "skipped", "24시간 동안 미국장 거래 없음"
        return
    symbols = list(dict.fromkeys(j.ticker.symbol for j in forecasts))
    run.base = {"base": base, "expiry": expiry, "snapshots": {s: quote_snapshot(s, base) for s in symbols}}
    for s in symbols:
        snap = run.base["snapshots"][s]
        log(f"기준 스냅샷 {s}: {snapshot_text(snap)}")
        write_json(REPO / f"research/{run.date}/meta/{s.lower()}-base.json",
                   {"ticker": s, "base_time_kst": fmt_kst(base), "expiry_kst": fmt_kst(expiry),
                    "base_session": us_session(base), "snapshot": snap, "run_id": run.run_id})
    for j in forecasts:
        render_prompt(run, j, base)
    run_queue(run, tm, forecasts, f"2단계 예측 (공통 기준 {fmt_kst(base)} KST)")


# ───────────────────────────── 작업 창 (worker) ─────────────────────────────


def short(obj: object, n: int = 220) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return clip(s, n)


class TextFormatter:
    def __init__(self, emit):
        self.emit = emit
        self.final: str | None = None

    def feed(self, line: str) -> None:
        self.emit(line if line.endswith("\n") else line + "\n")


class ClaudeFormatter(TextFormatter):
    """claude -p --output-format stream-json 이벤트를 사람이 읽기 좋게."""

    def feed(self, line: str) -> None:
        try:
            ev = json.loads(line)
        except ValueError:
            return super().feed(line)
        kind = ev.get("type")
        sub = "  │ " if ev.get("parent_tool_use_id") else ""
        if kind == "system" and ev.get("subtype") == "init":
            mcp = ", ".join(f"{s.get('name')}:{s.get('status')}" for s in ev.get("mcp_servers") or [])
            self.emit(f"[init] model={ev.get('model')} mcp=[{mcp}]\n")
        elif kind == "assistant":
            for b in (ev.get("message") or {}).get("content") or []:
                if b.get("type") == "text" and b.get("text", "").strip():
                    self.emit(sub + b["text"].rstrip() + "\n")
                elif b.get("type") == "tool_use":
                    self.emit(f"{sub}▶ {b.get('name')} {short(b.get('input'))}\n")
        elif kind == "user":
            content = (ev.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    flag = " (오류)" if b.get("is_error") else ""
                    self.emit(f"{sub}  ↳ 결과{flag} {short(b.get('content'), 140)}\n")
        elif kind == "result":
            self.final = ev.get("result")
            cost = ev.get("total_cost_usd") or 0
            self.emit(f"[result] {ev.get('subtype')} turns={ev.get('num_turns')} "
                      f"cost=${cost:.2f} {(ev.get('duration_ms') or 0) / 60000:.1f}분\n")


class AgyFormatter(TextFormatter):
    """agy -p --output-format stream-json 이벤트를 사람이 읽기 좋게."""

    def __init__(self, emit):
        super().__init__(emit)
        self.mid_line = False

    def _line(self, text: str) -> None:
        if self.mid_line:
            self.emit("\n")
            self.mid_line = False
        self.emit(text + "\n")

    def feed(self, line: str) -> None:
        try:
            ev = json.loads(line)
        except ValueError:
            return self._line(line.rstrip("\n"))
        kind = ev.get("event")
        if kind == "init":
            self._line(f"[init] model={(ev.get('init') or {}).get('model')}")
        elif kind == "step_update":
            s = ev.get("step_update") or {}
            info = s.get("tool_info") or {}
            if s.get("step_type") == "tool":
                if s.get("state") == "ACTIVE":
                    self._line(f"▶ {s.get('tool_name')} {short(info.get('parameters'))}")
                elif s.get("state") == "DONE":
                    self._line(f"  ↳ 결과 {short(info.get('output'), 140)}")
            elif s.get("step_type") == "agent_response" and s.get("text_delta"):
                self.emit(s["text_delta"])
                self.mid_line = not s["text_delta"].endswith("\n")
        elif kind == "result":
            r = ev.get("result") or {}
            self.final = r.get("response")
            self._line(f"[result] {r.get('status')} {(r.get('duration_seconds') or 0) / 60:.1f}분 "
                       f"turns={r.get('num_turns')}")


FORMATTERS = {"claude-json": ClaudeFormatter, "agy-json": AgyFormatter, "text": TextFormatter}


def child_env(extra: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    env.update(extra)
    return env


def kill_group(proc: subprocess.Popen, grace: float = 15) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def worker_main(spec_path: str) -> int:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except AttributeError:
        pass
    bar = "=" * 72  # 한국어 터미널에서 두 칸으로 그려지는 상자 문자 대신 ASCII
    print(f"{bar}\n {spec['title']}  (시도 {spec['attempt']})\n 시작 {now_kst():%Y-%m-%d %H:%M:%S} KST · "
          f"제한 {spec['timeout_s'] // 60}분 · 노트 {spec['repo_note']}\n 로그 {rel(spec['raw_log'])}\n{bar}",
          flush=True)
    Path(spec["raw_log"]).parent.mkdir(parents=True, exist_ok=True)
    prompt = Path(spec["prompt"]).read_text(encoding="utf-8")
    argv = [prompt if a == PROMPT_TOKEN else a for a in spec["argv"]]
    started = time.time()
    rc, err, timed_out, interrupted = None, None, threading.Event(), False
    proc: subprocess.Popen | None = None
    with open(spec["raw_log"], "w", encoding="utf-8") as raw, \
            open(spec["pretty_log"], "w", encoding="utf-8") as pretty:
        def emit(s: str) -> None:
            sys.stdout.write(s)
            sys.stdout.flush()
            pretty.write(s)
            pretty.flush()

        fmt = FORMATTERS.get(spec["stream"], TextFormatter)(emit)
        try:
            proc = subprocess.Popen(argv, cwd=spec["cwd"], env=child_env(spec.get("env") or {}),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                                    start_new_session=True)

            def on_timeout() -> None:
                timed_out.set()
                emit(f"\n[시간 초과] {spec['timeout_s'] // 60}분 — 작업을 멈춥니다\n")
                kill_group(proc)

            timer = threading.Timer(spec["timeout_s"], on_timeout)
            timer.daemon = True
            timer.start()
            assert proc.stdout is not None
            for line in proc.stdout:
                raw.write(line)
                raw.flush()
                fmt.feed(line)
            rc = proc.wait()
            timer.cancel()
        except KeyboardInterrupt:
            interrupted = True
            emit("\n[중단] Ctrl-C — 작업을 멈춥니다\n")
            if proc:
                kill_group(proc)
                rc = proc.returncode
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            emit(f"\n[오류] {err}\n")
    final = fmt.final
    if not final and Path(spec["last_message"]).exists():
        final = Path(spec["last_message"]).read_text(encoding="utf-8", errors="replace")
    if final:
        write_text(Path(spec["final"]), final)
    status = {
        "job_id": spec["job_id"], "attempt": spec["attempt"], "exit_code": rc, "error": err,
        "timed_out": timed_out.is_set(), "interrupted": interrupted,
        "started_kst": dt.datetime.fromtimestamp(started, KST).isoformat(timespec="seconds"),
        "ended_kst": now_kst().isoformat(timespec="seconds"),
        "duration_min": round((time.time() - started) / 60, 1),
        "note_exists": (REPO / spec["repo_note"]).exists(),
    }
    write_json(Path(spec["status"]), status)
    print(f"{bar}\n 끝 {now_kst():%H:%M:%S} KST · 종료 코드 {rc} · {status['duration_min']}분 · "
          f"노트 {'있음' if status['note_exists'] else '없음'}\n{bar}", flush=True)
    return 0


# ───────────────────────────── 마무리: 메타·통합 비교 ─────────────────────────────


def meta_from_note(note: Path) -> dict:
    text = note.read_text(encoding="utf-8", errors="replace")
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), note.stem)
    body = text.split("\n## 1", 1)[1] if "\n## 1" in text else text
    paras = [p.strip() for p in body.split("\n\n")[1:] if p.strip() and not p.lstrip().startswith(("|", "#", ">"))]
    summary = clip(re.sub(r"[*`]", "", paras[0]) if paras else "", 300)
    return {"title": title, "summary": summary}


def load_metas(date: str, t: Ticker, reviewed_date: str | None) -> dict[str, dict[str, dict]]:
    """오늘 날짜 폴더의 모델별 메타. 메타가 없으면 노트 제목·첫 문단으로 채움.

    경로는 프롬프트로 지정한 값으로 고정합니다 (볼트 누락분은 그 경로로 보완 업로드됨).
    """
    out: dict[str, dict[str, dict]] = {"forecast": {}, "review": {}}
    for kind in out:
        for key, m in MODELS.items():
            note = REPO / f"research/{date}/{note_filename(t, kind, m)}"
            if not note.exists():
                continue
            meta = read_json_loose(REPO / f"research/{date}/meta/{t.lower}-{kind}-{m.repo_slug}.json")
            meta = meta if isinstance(meta, dict) else meta_from_note(note)
            meta["repo_path"] = rel(note)
            if kind == "forecast":
                meta["vault_path"] = f"{VAULT_STOCK}/{t.symbol}/{date}-{m.vault_slug}.md"
            else:
                meta["reviewed_date"] = reviewed_date or meta.get("reviewed_date")
                if meta["reviewed_date"]:
                    meta["vault_path"] = f"{VAULT_STOCK}/{t.symbol}/{meta['reviewed_date']}-review-{m.vault_slug}.md"
            out[kind][key] = meta
    return out


def strip_md(p: str) -> str:
    return p[:-3] if p.endswith(".md") else p


def direction(meta: dict) -> str:
    s = str(meta.get("stance") or "")
    if "상승" in s and "하락" not in s:
        return "up"
    if "하락" in s and "상승" not in s:
        return "down"
    p = num(meta.get("up_prob_pct"))
    if p is None:
        return "flat"
    return "up" if p > 50 else "down" if p < 50 else "flat"


def consensus(fc: dict[str, dict]) -> dict:
    dirs = {k: direction(m) for k, m in fc.items()}
    counts = Counter(dirs.values())
    probs = [p for p in (num(m.get("up_prob_pct")) for m in fc.values()) if p is not None]
    avg = sum(probs) / len(probs) if probs else None
    ko = {"up": "상승 쪽", "down": "하락 쪽", "flat": "중립"}
    n = len(fc)
    if not n:
        text = "—"
    elif len(counts) == 1:
        text = f"만장일치 {ko[next(iter(counts))]} ({n}:0)"
    else:
        parts = " : ".join(f"{ko[d]} {counts[d]}" for d in ("up", "flat", "down") if counts[d])
        top, cnt = counts.most_common(1)[0]
        text = f"{ko[top]} 우세 ({parts})" if cnt > n / 2 else f"판단 분기 ({parts})"
    if avg is not None:
        text += f", 상승 확률 평균 {avg:.0f}%"
    return {"text": text, "dirs": dirs, "avg": avg}


def mklink(for_vault: bool, repo_path: str | None, vault_path: str | None, label: str, from_dir: str) -> str:
    if for_vault and vault_path:
        return f"[[{vault_path[:-3] if vault_path.endswith('.md') else vault_path}|{label}]]"
    if repo_path:
        return f"[{label}]({os.path.relpath(repo_path, from_dir)})"
    return label


def review_rows(rv: dict[str, dict]) -> dict[str, dict]:
    """복기 메타들의 채점을 대상 모델별로 모음: {대상: {"verdicts": {채점자: 판정}, "samples": [...]}}"""
    rows: dict[str, dict] = {}
    for reviewer, meta in rv.items():
        for s in meta.get("scores") or []:
            if not isinstance(s, dict):
                continue
            target = model_from_text(str(s.get("model", "")))
            if not target:
                continue
            row = rows.setdefault(target, {"verdicts": {}, "samples": []})
            row["verdicts"][reviewer] = str(s.get("verdict") or "—")
            row["samples"].append(s)
    return {k: rows[k] for k in MODELS if k in rows}


def first_of(samples: list[dict], key: str) -> object:
    return next((s.get(key) for s in samples if s.get(key) not in (None, "")), None)


def spread(samples: list[dict], key: str, fmt) -> str:
    vals = sorted({round(x, 2) for x in (num(s.get(key)) for s in samples) if x is not None})
    if not vals:
        return "—"
    return fmt(vals[0]) if len(vals) == 1 or vals[-1] - vals[0] < 0.01 else f"{fmt(vals[0])}~{fmt(vals[-1])}"


def majority(verdicts: dict[str, str]) -> str:
    if not verdicts:
        return "—"
    v, c = Counter(verdicts.values()).most_common(1)[0]
    return v if c > len(verdicts) / 2 else "판정 분기"


def review_table(rv: dict[str, dict]) -> list[str]:
    rows = review_rows(rv)
    reviewers = [k for k in MODELS if k in rv]
    head = "채점 (" + " · ".join(MODELS[k].short for k in reviewers) + ")"
    out = [f"| 대상 모델 | 기준 시각 → 만기 (KST) | 기준가 | 예측 | 만기 실제가 | 실제 등락률 | {head} |",
           "| --- | --- | ---: | --- | ---: | ---: | --- |"]
    for target, row in rows.items():
        sm = row["samples"]
        verdicts = " · ".join(row["verdicts"].get(r, "—") for r in reviewers)
        out.append("| " + " | ".join(cell(x) for x in (
            MODELS[target].name,
            f"{first_of(sm, 'base_time_kst') or '—'} → {first_of(sm, 'expiry_kst') or '—'}",
            spread(sm, "base_price", money), first_of(sm, "call"),
            spread(sm, "expiry_price", money),
            spread(sm, "change_pct", lambda x: f"{x:+.2f}%"), verdicts)) + " |")
    if not rows:
        out.append("| (채점 데이터 없음) | — | — | — | — | — | — |")
    return out


def all_final(rv: dict[str, dict]) -> bool:
    verdicts = [v for row in review_rows(rv).values() for v in row["verdicts"].values()]
    return bool(verdicts) and not any("잠정" in v for v in verdicts)


def base_info(date: str, t: Ticker, fc: dict[str, dict]) -> dict:
    """공통 기준(스냅샷)이 있으면 그것, 없으면 첫 예측 메타의 기준가."""
    b = read_json_loose(REPO / f"research/{date}/meta/{t.lower}-base.json")
    b = b if isinstance(b, dict) else {}
    snap = b.get("snapshot") if isinstance(b.get("snapshot"), dict) else {}
    first = next(iter(fc.values()), {})
    price = snap.get("price") if not snap.get("error") else None
    return {
        "base_time_kst": b.get("base_time_kst") or first.get("base_time_kst"),
        "expiry_kst": b.get("expiry_kst") or first.get("expiry_kst"),
        "session": snap.get("session") or b.get("base_session") or first.get("base_session"),
        "price": price if price is not None else first.get("base_price"),
        "prev_close": snap.get("prev_close") or first.get("prev_close"),
        "snapshot": snap,
    }


def base_phrase(b: dict) -> str:
    if not b.get("base_time_kst"):
        return ""
    sess = SESSION_KO.get(str(b.get("session")), str(b.get("session") or ""))
    s = f"{b['base_time_kst']} KST {money(b.get('price'))}"
    extra = ", ".join(x for x in (sess, f"직전 정규장 종가 {money(b['prev_close'])}" if b.get("prev_close") else "") if x)
    return s + (f"({extra})" if extra else "") + (f" → 만기 {b['expiry_kst']} KST" if b.get("expiry_kst") else "")


def results_block(rv: dict[str, dict], date: str, for_vault: bool, from_dir: str) -> str:
    links = " · ".join(mklink(for_vault, m.get("repo_path"), m.get("vault_path"), MODELS[k].short, from_dir)
                       for k, m in rv.items())
    return "\n".join(["<!-- auto:results:start -->",
                      f"> {date} 복기 노트 기준 자동 기록 — 복기 노트: {links}", "",
                      *review_table(rv), "<!-- auto:results:end -->"])


def summary_markdown(run: Run, t: Ticker, metas: dict, for_vault: bool) -> tuple[str, dict]:
    date = run.date
    fc, rv = metas["forecast"], metas["review"]
    from_dir = f"research/{date}"
    cons = consensus(fc)
    b = base_info(date, t, fc)
    reviewed = next((m.get("reviewed_date") for m in rv.values() if m.get("reviewed_date")), None)
    models_used = [MODELS[k].name for k in MODELS if k in fc or k in rv]
    L: list[str] = []
    if for_vault:
        L += ["---", "type: stock-forecast-summary", f"ticker: {t.symbol}", f"date: {date}", "horizon: 24h",
              "models:", *[f"  - {n}" for n in models_used], f"consensus: {yaml_str(cons['text'])}",
              "status: pending", f"generated_by: {yaml_str('automation/daily_forecast.py ' + run.run_id)}",
              "tags:", "  - stock", "  - forecast-24h", "  - ensemble-summary", f"  - {t.symbol}", "---", ""]
    title = (f"# [{t.symbol}] 24시간 주가 방향 3모델 통합 비교 ({date})" if fc
             else f"# [{t.symbol}] {reviewed} 회차 24시간 예측 복기 비교 ({date})")
    L += [title, "",
          f"> 자동 생성: `automation/daily_forecast.py` (실행 `{run.run_id}`). 모델별 메타데이터로 만든 비교표이며, "
          "근거와 해설은 각 모델 노트에 있습니다."]
    if for_vault:
        L.append("> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]]")
    if fc:
        L.append("> 모델별 상세 노트: " + " · ".join(
            mklink(for_vault, m.get("repo_path"), m.get("vault_path"), MODELS[k].name, from_dir) for k, m in fc.items()))
    if rv:
        L.append(f"> 직전 회차({reviewed}) 복기: " + " · ".join(
            mklink(for_vault, m.get("repo_path"), m.get("vault_path"), MODELS[k].name, from_dir) for k, m in rv.items()))
    missing = [MODELS[k].name for k in run.args.models if k not in fc and any(
        j.model.key == k and j.kind == "forecast" and j.ticker == t for j in run.jobs)]
    if missing:
        L.append(f"> 이번 실행에서 예측 노트를 만들지 못한 모델: {', '.join(missing)}")
    L.append("")
    sec = 0
    if fc:
        keys = list(fc)
        sec += 1
        L += [f"## {sec}. 3모델 결론 한눈에 비교", "",
              "| 구분 | " + " | ".join(MODELS[k].name for k in keys) + " |",
              "| --- |" + " --- |" * len(keys)]
        rows = [
            ("기준 시각 (KST)", lambda m: m.get("base_time_kst")),
            ("기준 세션", lambda m: SESSION_KO.get(str(m.get("base_session")), m.get("base_session"))),
            ("기준가", lambda m: money(m.get("base_price"))),
            ("직전 정규장 종가", lambda m: money(m.get("prev_close"))),
            ("만기 (KST)", lambda m: m.get("expiry_kst")),
            ("기준가 대비 판단", lambda m: m.get("stance")),
            ("상승 확률 (기준가 대비)", lambda m: pct(m.get("up_prob_pct"))),
            ("상승 확률 (직전 종가 대비)", lambda m: pct(m.get("up_prob_vs_prev_close_pct"))),
            ("중심 예상가", lambda m: m.get("center_range")),
            ("확신도", lambda m: m.get("confidence")),
            ("데이터·방법론", lambda m: m.get("methods")),
        ]
        for label, fn in rows:
            L.append(f"| **{label}** | " + " | ".join(cell(fn(fc[k])) for k in keys) + " |")
        L.append("| **상세 노트** | " + " | ".join(
            cell(mklink(for_vault, fc[k].get("repo_path"), fc[k].get("vault_path"), "보기", from_dir)) for k in keys) + " |")
        L += ["", f"- **컨센서스:** {cons['text']}"]
        if base_phrase(b):
            L.append(f"- **공통 기준:** {base_phrase(b)}")
        if b["snapshot"]:
            L.append(f"- **기준 스냅샷 (오케스트레이터):** {snapshot_text(b['snapshot'])}")
        L.append("")
        sec += 1
        L += [f"## {sec}. 시황 및 기술적·구조적 진단 비교", ""]
        L += [f"- **{MODELS[k].name}:** {clip(fc[k].get('market_view') or fc[k].get('summary'), 400)}" for k in keys]
        L.append("")
        sec += 1
        L += [f"## {sec}. 정량 근거 대조", ""]
        for k in keys:
            stats = fc[k].get("key_stats") or []
            L.append(f"- **{MODELS[k].name}:**" + ("" if stats else " (메타에 없음 — 상세 노트 참고)"))
            L += [f"  - {clip(s, 300)}" for s in stats if s]
        L.append("")
        sec += 1
        L += [f"## {sec}. 향후 24시간 주요 일정 및 재검토 기준", "", f"### {sec}.1 모델별 핵심 일정", ""]
        L += [f"- **{MODELS[k].name}:** " + (" · ".join(clip(e, 120) for e in fc[k].get("key_events") or []) or "—")
              for k in keys]
        L += ["", f"### {sec}.2 재검토(무효화) 기준", "", "| 모델 | 재검토 기준 |", "| --- | --- |"]
        L += [f"| {MODELS[k].name} | {cell(fc[k].get('invalidation'))} |" for k in keys]
        L.append("")
        sec += 1
        L += [f"## {sec}. 사후 결과 복기 (24시간 후 검증)", "", "<!-- auto:results:start -->",
              "> 만기 후 다음 실행의 복기 결과로 자동 채워집니다.", "",
              "| 모델 | 기준 시각 (KST) | 기준가 | 예측 | 만기 (KST) | 만기 실제가 | 실제 등락률 | 적중 여부 |",
              "| --- | --- | ---: | --- | --- | ---: | ---: | --- |"]
        for k in keys:
            m = fc[k]
            call = f"{m.get('stance') or '—'} (상승 {pct(m.get('up_prob_pct'))})"
            L.append("| " + " | ".join(cell(x) for x in (
                MODELS[k].name, m.get("base_time_kst"), money(m.get("base_price")), call, m.get("expiry_kst"),
                "*만기 후 기입*", "*만기 후 기입*", "진행 중")) + " |")
        L += ["<!-- auto:results:end -->", ""]
    if rv:
        sec += 1
        L += [f"## {sec}. 직전 회차 복기 요약 ({reviewed} 회차)", "", *review_table(rv), "",
              f"### {sec}.1 복기 노트별 교훈", ""]
        for k, m in rv.items():
            lessons = [clip(x, 200) for x in (m.get("lessons") or [])[:3] if x]
            L.append(f"- **{MODELS[k].name}:** " + (" / ".join(lessons) if lessons else clip(m.get("summary"), 300)))
        L.append("")
    info = {"ticker": t, "metas": metas, "consensus": cons, "base": b, "reviewed": reviewed,
            "repo": f"research/{date}/{t.lower}-summary.md", "vault": f"{VAULT_STOCK}/{t.symbol}/{date}.md"}
    return "\n".join(L).rstrip() + "\n", info


def splice_results(text: str, block: str, date: str) -> str:
    start, end = "<!-- auto:results:start -->", "<!-- auto:results:end -->"
    if start in text and end in text and text.index(start) < text.index(end):
        i, j = text.index(start), text.index(end) + len(end)
        return text[:i] + block + text[j:]
    return text.rstrip() + f"\n\n## 사후 결과 복기 — 자동 추가 ({date})\n\n" + block + "\n"


def set_frontmatter(text: str, key: str, value: str) -> str:
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return text
    end = text.index("\n---", 4)
    head, rest = text[4:end], text[end:]
    pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
    head = pat.sub(f"{key}: {value}", head, count=1) if pat.search(head) else head + f"\n{key}: {value}"
    return "---\n" + head + rest


def update_prev_summaries(run: Run, t: Ticker, prev_date: str, rv: dict[str, dict]) -> list[str]:
    done: list[str] = []
    repo_p = REPO / f"research/{prev_date}/{t.lower}-summary.md"
    if repo_p.exists():
        block = results_block(rv, run.date, False, f"research/{prev_date}")
        write_text(repo_p, splice_results(repo_p.read_text(encoding="utf-8"), block, run.date))
        done.append(rel(repo_p))
    if run.vault_on:
        vpath = f"{VAULT_STOCK}/{t.symbol}/{prev_date}.md"
        try:
            content = run.vault.read(vpath)
            if content:
                new = splice_results(content, results_block(rv, run.date, True, f"research/{prev_date}"), run.date)
                if all_final(rv):
                    new = set_frontmatter(new, "status", "completed")
                run.vault.write(vpath, new)
                done.append(vpath)
        except (ConnectionError, RuntimeError) as e:
            log(f"직전 통합 비교 노트 갱신 실패 {vpath}: {e}")
    return done


def vault_copy_from_repo(run: Run, job: Job) -> str:
    body = (REPO / job.repo_note).read_text(encoding="utf-8")
    if body.startswith("---\n"):
        return body
    meta = read_json_loose(REPO / job.meta_path)
    meta = meta if isinstance(meta, dict) else {}
    kind = "stock-forecast-model" if job.kind == "forecast" else "stock-forecast-review"
    fm = ["---", f"type: {kind}", f"ticker: {job.ticker.symbol}",
          f"date: {job.date if job.kind == 'forecast' else job.reviewed_date}", "horizon: 24h",
          f"model: {job.model.name}"]
    for k in ("base_time_kst", "base_session", "base_price", "prev_close", "expiry_kst", "stance", "confidence"):
        if meta.get(k) not in (None, ""):
            fm.append(f"{k}: {yaml_str(meta[k]) if isinstance(meta[k], str) else meta[k]}")
    fm += [f"status: {'pending' if job.kind == 'forecast' else 'completed'}",
           f"tags: [stock, forecast-24h, {job.ticker.symbol}, {job.model.vault_slug}]", "---", ""]
    note = (f"> 자동 업로드: 모델이 볼트에 직접 쓰지 못해 저장소 노트를 옮겼습니다. "
            f"저장소 원본: `{job.repo_note}` · 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]]\n\n")
    return "\n".join(fm) + note + body


def ensure_vault_notes(run: Run) -> None:
    for job in (j for j in run.jobs if j.state == "done"):
        try:
            if run.vault.exists(job.vault_note):
                job.vault_result = "모델이 저장"
                continue
            fb = run.fallback_path(job)
            if fb.exists() and fb.stat().st_size > 200:
                content, how = fb.read_text(encoding="utf-8"), "대체 파일 업로드"
            else:
                content, how = vault_copy_from_repo(run, job), "저장소 노트 변환 업로드"
            run.vault.write(job.vault_note, content)
            job.vault_result = how
            log(f"볼트 노트 보완 {job.vault_note} ({how})")
        except (ConnectionError, RuntimeError, OSError) as e:
            job.vault_result = f"실패: {e}"
            log(f"볼트 노트 확인 실패 {job.vault_note}: {e}")


# ───────────────────────────── 마무리: README ─────────────────────────────


def item_label(t: Ticker, kind: str, key: str, meta: dict) -> str:
    if kind == "forecast":
        return f"{t.symbol} 24시간 주가 방향 예상 ({MODELS[key].name})"
    return f"{t.symbol} {meta.get('reviewed_date') or ''} 회차 예측 복기 ({MODELS[key].name})".replace("  ", " ")


def group_sentence(g: dict) -> str:
    fc, rv = g["metas"]["forecast"], g["metas"]["review"]
    parts = []
    if fc:
        if base_phrase(g["base"]):
            parts.append("공통 기준 " + base_phrase(g["base"]))
        parts.append(f"컨센서스 {g['consensus']['text']}")
        parts.append("모델별 상승 확률 " + " · ".join(
            f"{MODELS[k].short} {pct(m.get('up_prob_pct'))}" for k, m in fc.items()))
    if rv:
        verdicts = " · ".join(f"{MODELS[k].short} {majority(r['verdicts'])}" for k, r in review_rows(rv).items())
        parts.append(f"직전({g['reviewed']}) 회차 채점(다수결) {verdicts or '—'}")
    return ". ".join(parts) + "." if parts else ""


def readme_group_lines(run: Run, g: dict) -> list[str]:
    t = g["ticker"]
    kinds = "예측·복기" if g["metas"]["forecast"] and g["metas"]["review"] else (
        "예측" if g["metas"]["forecast"] else "복기")
    out = [f"- [{t.symbol} 24시간 {kinds} 3모델 통합 비교, {run.date}]({g['repo']}): {group_sentence(g)}"]
    for kind in ("forecast", "review"):
        for key, meta in g["metas"][kind].items():
            out.append(f"  - [{item_label(t, kind, key, meta)}]({meta['repo_path']}): {clip(meta.get('summary'), 400)}")
    return out


def update_repo_readme(run: Run) -> None:
    path = REPO / "README.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    for g in run.groups:  # 같은 날짜·종목을 다시 돌린 경우 예전 묶음을 지움
        i = next((n for n, ln in enumerate(lines) if ln.startswith("- [") and f"]({g['repo']})" in ln), None)
        if i is not None:
            j = i + 1
            while j < len(lines) and lines[j].startswith("  "):
                j += 1
            del lines[i:j]
    head = next((n for n, ln in enumerate(lines) if ln.strip() == "## 연구 노트"), None)
    if head is None:
        lines += ["", "## 연구 노트", ""]
        head = len(lines) - 2
    ins = head + 1
    while ins < len(lines) and not lines[ins].startswith(("- ", "## ")):
        ins += 1
    new = [ln for g in run.groups for ln in readme_group_lines(run, g)]
    if ins >= len(lines) or lines[ins].startswith("## "):
        new = new + [""]
    lines[ins:ins] = new
    write_text(path, "\n".join(lines))


def vault_archive_bullet(run: Run, g: dict) -> str:
    t = g["ticker"]
    fc, rv = g["metas"]["forecast"], g["metas"]["review"]
    label = "24시간 3모델 통합 비교" if fc else f"{g['reviewed']} 회차 예측 복기 비교"
    s = f"  - [[{strip_md(g['vault'])}|{run.date} — {t.symbol} {label} (자동 실행)]]"
    detail = []
    if fc:
        b = g["base"]
        if b.get("base_time_kst"):
            detail.append(f"`{b['base_time_kst'][11:]} KST {SESSION_KO.get(str(b.get('session')), '')} "
                          f"{money(b.get('price'))} 기준`".replace("  ", " "))
        detail.append(g["consensus"]["text"])
    if detail:
        s += f" ({', '.join(detail)})"
    if fc:
        s += " · 상세: " + " · ".join(f"[[{strip_md(m['vault_path'])}|{MODELS[k].short}]]" for k, m in fc.items())
    if rv:
        s += f" · {g['reviewed']} 회차 복기: " + " · ".join(
            f"[[{strip_md(m['vault_path'])}|{MODELS[k].short}]]" for k, m in rv.items() if m.get("vault_path"))
    return s


def update_vault_readme(run: Run) -> None:
    vpath = f"{VAULT_STOCK}/README.md"
    text = run.vault.read(vpath)
    if not text:
        log(f"볼트 {vpath}를 읽지 못해 아카이브 목록을 건너뜁니다")
        return
    lines = text.split("\n")
    sec = next((i for i, ln in enumerate(lines) if ln.startswith("## ") and "아카이브" in ln), None)
    if sec is None:
        lines += ["", "## 5. 아카이브 현황", ""]
        sec = len(lines) - 2

    def section_end() -> int:
        return next((i for i in range(sec + 1, len(lines)) if lines[i].startswith("## ")), len(lines))

    for g in run.groups:
        t = g["ticker"]
        prefix = f"  - [[{strip_md(g['vault'])}|"
        lines = [ln for i, ln in enumerate(lines) if not (sec < i < section_end() and ln.startswith(prefix))]
        end = section_end()
        h = next((i for i in range(sec + 1, end) if lines[i].startswith(f"- **{t.symbol}")), None)
        bullet = vault_archive_bullet(run, g)
        if h is None:
            while end > sec + 1 and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = [f"- **{t.symbol}**", bullet]
        else:
            lines.insert(h + 1, bullet)
    new = set_frontmatter("\n".join(lines), "updated", yaml_str(run.date))
    run.vault.write(vpath, new)


def post_process(run: Run) -> None:
    if run.vault_on:
        ensure_vault_notes(run)
    for sym, t in TICKERS.items():
        if not any(j.ticker.symbol == sym and j.state == "done" for j in run.jobs):
            continue
        prev = run.prev.get(sym)
        metas = load_metas(run.date, t, prev.date if prev else None)
        if not (metas["forecast"] or metas["review"]):
            continue
        repo_md, info = summary_markdown(run, t, metas, for_vault=False)
        write_text(REPO / info["repo"], repo_md)
        if run.vault_on:
            try:
                run.vault.write(info["vault"], summary_markdown(run, t, metas, for_vault=True)[0])
            except (ConnectionError, RuntimeError) as e:
                log(f"볼트 통합 비교 노트 쓰기 실패 {info['vault']}: {e}")
        if metas["review"] and prev:
            for p in update_prev_summaries(run, t, prev.date, metas["review"]):
                log(f"직전 통합 비교 노트에 채점 기록: {p}")
        run.groups.append(info)
        log(f"{sym} 통합 비교: {info['repo']} — {info['consensus']['text']}")
    if not run.groups:
        return
    update_repo_readme(run)
    if run.vault_on:
        try:
            update_vault_readme(run)
        except (ConnectionError, RuntimeError) as e:
            log(f"볼트 README 아카이브 갱신 실패: {e}")


# ───────────────────────────── git ─────────────────────────────


def worktree_snapshot() -> dict[str, str | None]:
    out = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *WATCH_PATHS).stdout
    entries, paths, i = out.split("\0"), [], 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC":  # 이름 바꾸기: 다음 항목이 원래 경로
            i += 1
        paths.append(e[3:])
    snap = {}
    for p in paths:
        f = REPO / p
        snap[p] = hashlib.sha1(f.read_bytes()).hexdigest() if f.is_file() else None
    return snap


def commit_message(run: Run, changed: list[str]) -> str:
    order = list(TICKERS)
    done = sorted((j for j in run.jobs if j.state == "done"),
                  key=lambda j: (order.index(j.ticker.symbol), j.kind != "forecast", list(MODELS).index(j.model.key)))
    n_fc = sum(j.kind == "forecast" for j in done)
    n_rv = len(done) - n_fc
    tickers = "·".join(dict.fromkeys(j.ticker.symbol for j in done)) or "SOXL·KORU"
    models = "·".join(MODELS[k].short for k in MODELS if any(j.model.key == k for j in done))
    kinds = "예측·복기" if n_fc and n_rv else "예측" if n_fc else "복기"
    lines = [f"docs: {tickers} 24시간 {kinds} 노트 {len(done)}건 추가 ({models}, {run.date})", ""]
    for j in done:
        meta = read_json_loose(REPO / j.meta_path)
        summary = clip(meta.get("summary"), 200) if isinstance(meta, dict) else ""
        lines.append(f"- {j.repo_note}: {summary}" if summary else f"- {j.repo_note}")
    for g in run.groups:
        lines.append(f"- {g['repo']}: 3모델 통합 비교 자동 생성 ({g['consensus']['text']})")
    known = {j.repo_note for j in done} | {g["repo"] for g in run.groups} | {"README.md"}
    others = [p for p in changed if p not in known]
    today = f"research/{run.date}/"
    data = sorted({p[len(today):].split("/")[0] + "/" for p in others if p.startswith(today) and "/" in p[len(today):]})
    if data:
        lines.append(f"- {today}{{{', '.join(data)}}}: 모델별 시세·분석 데이터와 메타데이터")
    prev = [p for p in others if not p.startswith(today)]
    if prev:
        lines.append("- 직전 노트 사후 복기 갱신: " + ", ".join(prev))
    if "README.md" in changed:
        lines.append("- README 연구 노트 목록 갱신")
    failed = [j for j in run.jobs if j.state in ("failed", "skipped")]
    if failed:
        lines += ["", "미완료: " + ", ".join(f"{j.id}({j.message or j.state})" for j in failed)]
    lines += ["", f"자동 실행: automation/daily_forecast.py (실행 ID {run.run_id})"]
    return "\n".join(lines) + "\n"


def commit_and_push(run: Run, before: dict[str, str | None]) -> None:
    if run.args.no_commit:
        log("--no-commit: 커밋을 건너뜁니다")
        return
    after = worktree_snapshot()
    changed, skipped = [], []
    for p, h in after.items():
        if before.get(p, "∅") == h or JUNK_RE.search(p):
            continue
        if h is None:
            skipped.append(f"{p} (삭제됨)")
            continue
        size = (REPO / p).stat().st_size
        if size > MAX_COMMIT_FILE_MB * 1_000_000:
            skipped.append(f"{p} ({size / 1e6:.1f}MB)")
            continue
        changed.append(p)
    for s in skipped:
        log(f"커밋 제외: {s}")
    if not changed:
        log("커밋할 변경이 없습니다")
        return
    for i in range(0, len(changed), 200):
        git("add", "--", *changed[i:i + 200])
    msg_file = run.run_dir / "commit-message.txt"
    write_text(msg_file, commit_message(run, changed))
    r = git("commit", "-F", str(msg_file), "--only", "--", *changed, check=False)
    if r.returncode != 0:
        log(f"커밋 실패: {(r.stderr or r.stdout).strip()[-400:]}")
        return
    run.commit = git("rev-parse", "--short", "HEAD").stdout.strip()
    log(f"커밋 {run.commit}: 파일 {len(changed)}개")
    if run.args.no_push:
        log("--no-push: push를 건너뜁니다")
        return
    for attempt in range(1, 4):
        r = git("push", GIT_REMOTE, f"HEAD:{GIT_BRANCH}", check=False)
        if r.returncode == 0:
            run.pushed = True
            log(f"push 완료 → {GIT_REMOTE}/{GIT_BRANCH}")
            return
        log(f"push 실패 ({attempt}/3): {r.stderr.strip()[-300:]}")
        pr = git("pull", "--rebase", "--autostash", GIT_REMOTE, GIT_BRANCH, check=False)
        if pr.returncode != 0:
            git("rebase", "--abort", check=False)
            log("원격 변경과 충돌해 커밋을 로컬에만 남겼습니다. 직접 정리한 뒤 push 하세요.")
            return
        run.commit = git("rev-parse", "--short", "HEAD").stdout.strip()
        time.sleep(3)


# ───────────────────────────── 실행 준비·보고 ─────────────────────────────


def check_environment(args: argparse.Namespace) -> list[str]:
    problems = []
    if not args.dry_run and not shutil.which("tmux"):
        problems.append("tmux가 없습니다")
    for key in args.models:
        if not shutil.which(MODELS[key].binary):
            problems.append(f"{MODELS[key].binary} CLI를 PATH에서 찾지 못했습니다 ({key})")
    for name in ("common.md", "review.md", "forecast.md"):
        if not (PROMPTS_DIR / name).exists():
            problems.append(f"프롬프트 파일 없음: {rel(PROMPTS_DIR / name)}")
    if not args.no_commit and not args.dry_run:
        branch = git("rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
        if branch != GIT_BRANCH:
            problems.append(f"현재 브랜치가 {branch}입니다 — {GIT_BRANCH}에서 실행하거나 --no-commit을 쓰세요")
        if (REPO / ".git" / "rebase-merge").exists() or (REPO / ".git" / "rebase-apply").exists():
            problems.append("진행 중인 rebase가 있습니다")
    return problems


def git_pull() -> None:
    r = git("pull", "--rebase", "--autostash", GIT_REMOTE, GIT_BRANCH, check=False)
    if r.returncode == 0:
        log(f"git pull: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '최신'}")
    else:
        git("rebase", "--abort", check=False)
        log(f"git pull 실패(계속 진행, 마지막에 다시 시도): {r.stderr.strip()[-300:]}")


def connect_vault(run: Run) -> None:
    token = find_obsidian_token()
    if not token:
        log("Obsidian API 토큰을 찾지 못했습니다 — 볼트 확인·보완은 건너뜁니다")
        return
    vault = Vault(token)
    if vault.ping():
        run.vault = vault
        log(f"Obsidian REST 연결: {vault.base}")
    else:
        log("Obsidian REST에 연결하지 못했습니다 — Obsidian이 켜져 있는지 확인하세요 (볼트 보완 건너뜀)")
    if "claude" in run.args.models and not run.args.dry_run:
        run.claude_mcp = write_claude_mcp_config(run.run_dir / "claude-mcp.json", token)


def print_plan(run: Run) -> None:
    log(f"실행 {run.run_id} · 노트 날짜 {run.date} · 모델 {', '.join(run.args.models)} · 작업 {', '.join(run.args.tasks)}")
    for sym, prev in run.prev.items():
        if prev:
            log(f"{sym} 복기 대상 {prev.date} 회차: " + ", ".join(f"{n.model.short}={n.repo_path}" for n in prev.notes))
    for j in run.jobs:
        log(f"  · {j.id:<22} → {j.repo_note} | 볼트 {j.vault_note}")


def write_report(run: Run) -> None:
    jobs = [{
        "id": j.id, "state": j.state, "attempts": j.attempt, "message": j.message,
        "minutes": round(((j.ended or time.time()) - j.started) / 60, 1) if j.started else None,
        "repo_note": j.repo_note, "vault_note": j.vault_note, "note_ok": j.note_ok, "meta_ok": j.meta_ok,
        "vault": j.vault_result, "status": j.status,
    } for j in run.jobs]
    report = {"run_id": run.run_id, "date": run.date, "session": run.session, "commit": run.commit,
              "pushed": run.pushed, "base": run.base, "jobs": jobs}
    write_json(run.run_dir / "report.json", report)
    log("── 결과")
    for j in jobs:
        mins = f"{j['minutes']:.0f}분" if j["minutes"] is not None else "-"
        log(f"  {j['state']:<8} {j['id']:<22} {mins:>5}  볼트:{j['vault'] or '-'}"
            f"{'  ' + j['message'] if j['message'] else ''}")
    log(f"커밋 {run.commit or '없음'} · push {'완료' if run.pushed else '안 함'} · 기록 {rel(run.run_dir)}")


def orchestrate(args: argparse.Namespace) -> int:
    run_dir = RUNS_DIR / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    LOG.file = run_dir / "orchestrator.log"
    run = Run(args=args, run_id=args.run_id, date=args.date, run_dir=run_dir, session=args.session)
    problems = check_environment(args)
    if problems:
        for p in problems:
            log(f"✖ {p}")
        return 2
    if not args.no_pull and not args.dry_run and not args.no_commit:
        git_pull()
    connect_vault(run)
    plan(run)
    print_plan(run)
    if not run.jobs:
        log("실행할 작업이 없습니다")
        return 1
    existing = [j.repo_note for j in run.jobs if (REPO / j.repo_note).exists()]
    if existing and not args.overwrite and not args.dry_run:
        log("이미 있는 노트: " + ", ".join(existing) + " — 덮어쓰려면 --overwrite")
        return 2
    if args.dry_run:
        start = now_kst().replace(second=0, microsecond=0)
        run.base = {"base": start, "expiry": start + dt.timedelta(hours=24), "snapshots": {}}
        for j in run.jobs:
            render_prompt(run, j, start)
            argv = build_argv(j.model, run.run_dir / "logs" / f"{j.id}.last.txt", run_dir / "claude-mcp.json")
            log(f"  {j.id}: {shlex.join(argv)[:160]}…")
        log(f"--dry-run: 프롬프트를 {rel(run_dir / 'prompts')}/ 에 만들었습니다 (예측 기준 시각은 실행 시 정해짐)")
        return 0
    tm = setup_tmux(run)
    before = worktree_snapshot()
    try:
        run_phases(run, tm)
    except KeyboardInterrupt:
        log("중단 요청 — 실행 중인 작업을 멈추고 커밋하지 않습니다")
        stop_running(run, tm)
        write_report(run)
        return 130
    finally:
        if run.claude_mcp:
            run.claude_mcp.unlink(missing_ok=True)
    for step in (lambda: post_process(run), lambda: commit_and_push(run, before)):
        try:
            step()
        except Exception:  # 마무리 단계 하나가 실패해도 나머지와 보고서는 남김
            import traceback
            log("마무리 단계 오류:\n" + traceback.format_exc())
    write_report(run)
    log(f"끝. 창 확인: tmux attach -t {run.session} · 정리: tmux kill-session -t {run.session}")
    return 0 if all(j.state == "done" for j in run.jobs) else 1


def launch(args: argparse.Namespace) -> int:
    problems = check_environment(args)
    if problems:
        for p in problems:
            print(f"✖ {p}", file=sys.stderr)
        return 2
    tm = Tmux(args.session)
    if tm.has_session():
        print(f"✖ tmux 세션 {args.session}이 이미 있습니다", file=sys.stderr)
        return 2
    forward = ["--foreground", "--run-id", args.run_id, "--date", args.date, "--session", args.session,
               "--tasks", ",".join(args.tasks), "--models", ",".join(args.models),
               "--timeout-min", str(args.timeout_min), "--max-parallel", str(args.max_parallel),
               "--retries", str(args.retries)]
    if args.prev_date:
        forward += ["--prev-date", args.prev_date]
    for flag in ("no_commit", "no_push", "no_pull", "no_vault", "overwrite", "force_forecast"):
        if getattr(args, flag):
            forward.append("--" + flag.replace("_", "-"))
    cmd = shlex.join(["env", f"PATH={os.environ.get('PATH', '')}", sys.executable, str(SCRIPT), *forward])
    tm.new_window("control", cmd)
    print(f"tmux 세션 {args.session} 시작 (실행 ID {args.run_id}, 노트 날짜 {args.date})")
    print(f"  보기:  tmux attach -t {args.session}   (창: control · {' · '.join(args.models)}, Ctrl-b n 다음 창)")
    print(f"  기록:  {rel(RUNS_DIR / args.run_id)}/orchestrator.log")
    if args.attach:
        if os.environ.get("TMUX"):
            os.execvp("tmux", ["tmux", "switch-client", "-t", args.session])
        os.execvp("tmux", ["tmux", "attach-session", "-t", args.session])
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="daily_forecast.py", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Claude Fable Max · Codex Astra Max · AGY Argon High에 같은 프롬프트로 "
                    "SOXL·KORU 복기와 24시간 예측을 tmux에서 동시에 시키고, 결과를 볼트·저장소에 정리해 main에 push합니다.",
        epilog=__doc__.split("사용 예", 1)[1] if "사용 예" in (__doc__ or "") else None)
    p.add_argument("--tasks", default=",".join(TASKS), help=f"쉼표로 구분 (기본: 전부) {', '.join(TASKS)}")
    p.add_argument("--models", default=",".join(MODELS), help=f"쉼표로 구분 (기본: 전부) {', '.join(MODELS)}")
    p.add_argument("--date", help="노트 날짜 = 폴더 이름 (한국 날짜, 기본: 오늘)")
    p.add_argument("--prev-date", help="이 날짜 이하에서 복기 대상 회차를 찾음 (기본: 오늘 이전 최신)")
    p.add_argument("--timeout-min", type=int, default=150, help="작업 하나의 제한 시간(분), 기본 150")
    p.add_argument("--max-parallel", type=int, default=2, help="모델별 동시 작업 수, 기본 2 (SOXL·KORU 동시)")
    p.add_argument("--retries", type=int, default=1, help="노트를 못 만든 작업 재시도 횟수, 기본 1 (시간 초과 제외)")
    p.add_argument("--session", help="tmux 세션 이름 (기본: fc-<실행 ID>)")
    p.add_argument("--no-commit", action="store_true", help="git 커밋·push 하지 않음")
    p.add_argument("--no-push", action="store_true", help="커밋만 하고 push 하지 않음")
    p.add_argument("--no-pull", action="store_true", help="시작할 때 git pull 하지 않음")
    p.add_argument("--no-vault", action="store_true", help="이 스크립트의 볼트 쓰기(누락분·통합 비교·README) 생략")
    p.add_argument("--overwrite", action="store_true", help="오늘 노트가 이미 있어도 덮어씀")
    p.add_argument("--force-forecast", action="store_true", help="24시간 동안 미국장 거래가 없어도 예측 실행")
    p.add_argument("--dry-run", action="store_true", help="계획과 프롬프트만 만들고 실행하지 않음")
    p.add_argument("--attach", action="store_true", help="세션을 띄운 뒤 바로 붙음")
    p.add_argument("--foreground", action="store_true", help="오케스트레이터를 지금 터미널에서 실행 (모델은 tmux)")
    p.add_argument("--run-id", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    args.tasks = [x.strip() for x in args.tasks.split(",") if x.strip()]
    args.models = [x.strip() for x in args.models.split(",") if x.strip()]
    bad = [x for x in args.tasks if x not in TASKS] + [x for x in args.models if x not in MODELS]
    if bad:
        p.error(f"알 수 없는 값: {', '.join(bad)}")
    if args.date and not DATE_RE.fullmatch(args.date):
        p.error("--date는 YYYY-MM-DD")
    args.run_id = args.run_id or now_kst().strftime("%Y%m%d-%H%M%S")
    args.date = args.date or now_kst().date().isoformat()
    args.session = args.session or f"fc-{args.run_id}"
    return args


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_worker"] and len(argv) == 2:
        return worker_main(argv[1])
    args = parse_args(argv)
    if args.dry_run or args.foreground:
        return orchestrate(args)
    return launch(args)


if __name__ == "__main__":
    sys.exit(main())
