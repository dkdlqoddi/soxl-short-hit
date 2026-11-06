"""저장소 복기 노트를 볼트용(프론트매터 + 위키링크 헤더)으로 바꿔 지정한 경로에 쓴다.
사용: python3 make_vault_note.py <out_file> "<reviewed_at KST>" """
import sys, pathlib

REPO = pathlib.Path("/home/dkdlqoddi/012_gemini/soxl-short-hit")
src = (REPO / "research/2026-11-06/soxl-review-claude.md").read_text(encoding="utf-8")
out, reviewed_at = sys.argv[1], sys.argv[2]
h1, body = src.split("\n", 1)
assert h1 == "# [SOXL] 2026-11-05 24시간 예측 사후 평가 — Claude Fable Max"
S = "PERSONAL/STOCK/SOXL"
reps = [
    ("[Claude Fable Max](../2026-11-05/forecast-24h-claude.md)", f"[[{S}/2026-11-05-claude-fable-max|Claude Fable Max]] (저장소 `research/2026-11-05/forecast-24h-claude.md`)"),
    ("[Codex Astra Max](../2026-11-05/forecast-24h-codex.md)", f"[[{S}/2026-11-05-codex|Codex Astra Max]] (저장소 `research/2026-11-05/forecast-24h-codex.md`)"),
    ("[Antigravity Argon High](../2026-11-04/soxl-forecast-24h-argon.md)", f"[[{S}/2026-11-04-antigravity-argon-high|Antigravity Argon High]] (저장소 `research/2026-11-04/soxl-forecast-24h-argon.md`)"),
    ("볼트 사본은 `PERSONAL/STOCK/SOXL/2026-11-05-claude-fable-max.md`, `2026-11-05-codex.md`, `2026-11-04-antigravity-argon-high.md`(요약 `2026-11-04.md`)이고,",
     f"Argon의 요약 노트는 [[{S}/2026-11-04|2026-11-04 요약]]이고,"),
    ("[KORU 11/4 회차 복기](../2026-11-05/koru-review-claude.md), 볼트 `PERSONAL/STOCK/SOXL/2026-11-03-review.md`",
     f"[[PERSONAL/STOCK/KORU/2026-11-04-review-claude-fable-max|KORU 11/4 회차 복기]], [[{S}/2026-11-03-review|SOXL 11/3 회차 사후 평가]]"),
    ("볼트 `PERSONAL/STOCK/SOXL/2026-11-05-claude-fable-max.md`의 \"6.2 이번 노트\" 절", f"볼트 [[{S}/2026-11-05-claude-fable-max|2026-11-05 Claude Fable Max 노트]]의 \"6.2 이번 노트\" 절"),
]
for a, b in reps:
    assert body.count(a) == 1, a
    body = body.replace(a, b)
assert "](../" not in body and "](./" not in body
fm = f"""---
type: stock-forecast-review
ticker: SOXL
date: 2026-11-05
reviewed_at: "{reviewed_at}"
reviewer: Claude Fable Max
horizon: 24h
models:
  - Claude Fable Max
  - Codex Astra Max
  - Antigravity Argon High
status: completed
tags:
  - stock
  - forecast-24h
  - review
  - SOXL
  - claude-fable-max
---

"""
head = f"""{h1}

> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]] · 이 회차의 3모델 통합 비교 노트는 없음 (Argon 요약: [[{S}/2026-11-04|2026-11-04 미국 11/4 시가 기준 요약]])
> 평가 대상 노트: [[{S}/2026-11-05-claude-fable-max|Claude Fable Max]] · [[{S}/2026-11-05-codex|Codex Astra Max]] · [[{S}/2026-11-04-antigravity-argon-high|Antigravity Argon High]]
> 이전 복기: [[{S}/2026-11-03-review|SOXL 2026-11-03 회차 사후 평가]] · [[PERSONAL/STOCK/KORU/2026-11-04-review-claude-fable-max|KORU 2026-11-04 회차 사후 평가 (Claude Fable Max)]]
> 후속 예측 노트: [[{S}/2026-11-06-claude-fable-max|2026-11-06 Claude Fable Max]] (이 복기 뒤에 작성)
> 저장소 원본: `research/2026-11-06/soxl-review-claude.md`

---
"""
pathlib.Path(out).write_text(fm + head + body, encoding="utf-8")
print("written", out, len(fm + head + body))
