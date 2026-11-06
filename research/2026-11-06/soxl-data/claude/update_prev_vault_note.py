"""본인 직전 노트(볼트 PERSONAL/STOCK/SOXL/2026-11-05-claude-fable-max.md)의 6.2절을 저장소 노트의 갱신본으로 바꾸고
프론트매터를 status: completed로 바꾼다. vault_read의 version을 vault_write의 ifMatch로 넘긴다."""
import json, pathlib, re, sys
from vault_mcp import MCP

VPATH = "PERSONAL/STOCK/SOXL/2026-11-05-claude-fable-max.md"
REPO_NOTE = pathlib.Path("/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-05/forecast-24h-claude.md")
m = MCP()
cur = json.loads(m.call("vault_read", {"path": VPATH}))
content, version = cur["content"], cur["version"]
before = json.loads(pathlib.Path("prev_vault_note_before.json").read_text(encoding="utf-8"))
print("version", version, "| unchanged since first read:", content == before["content"])

repo = REPO_NOTE.read_text(encoding="utf-8")
new62 = repo[repo.index("### 6.2 이번 노트 (2026-11-06 복기 기입)"):repo.index("## 7. 출처 및 원본 참조")]
link_repo = "[SOXL 11/5 회차 사후 평가 — Claude Fable Max](../2026-11-06/soxl-review-claude.md)"
assert new62.count(link_repo) == 1
new62 = new62.replace(link_repo, "[[PERSONAL/STOCK/SOXL/2026-11-05-review-claude-fable-max|SOXL 11/5 회차 사후 평가 — Claude Fable Max]] (저장소 `research/2026-11-06/soxl-review-claude.md`)")
assert "](../" not in new62

a = content.index("### 6.2 이번 노트 (만기 뒤 기입)"); b = content.index("## 7. 출처 및 원본 참조")
old62 = content[a:b]
assert "(만기 후 기입)" in old62 and old62.count("\n") < 15, old62
new = content[:a] + new62 + content[b:]
fm_end = new.index("\n---\n", 4)
fm = new[:fm_end]
assert fm.count("status: pending") == 1
new = fm.replace("status: pending", "status: completed") + new[fm_end:]
if "--dry" in sys.argv:
    print(new[a - 200:a + len(new62) + 80]); sys.exit()
print(m.call("vault_write", {"path": VPATH, "content": new, "ifMatch": version}))
chk = json.loads(m.call("vault_read", {"path": VPATH}))
print("after: version", chk["version"], "status", chk["frontmatter"].get("status"), "identical:", chk["content"] == new, "len", len(chk["content"]))
pathlib.Path("prev_vault_note_after.md").write_text(chk["content"], encoding="utf-8")
