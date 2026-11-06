"""obsidian MCP 서버(Local REST API with MCP 플러그인)를 JSON-RPC로 직접 호출하는 보조 스크립트 (Claude Fable Max).
세션 시작 때 MCP 연결이 실패해(ECONNREFUSED) 도구가 등록되지 않았고, 이후 서버가 살아나 같은 설정으로 호출한다.
URL·토큰은 이번 실행의 MCP 설정 파일(automation/runs/<run id>/claude-mcp.json)에서 읽으며 출력하지 않는다.

사용:
  python3 vault_mcp.py list                                  # tools/list
  python3 vault_mcp.py call <tool> '<json 인자>'              # 결과 JSON 출력
  python3 vault_mcp.py read <vault path> [저장할 파일]         # vault_read → content 저장/출력, version은 stderr
  python3 vault_mcp.py write <vault path> <파일> [ifMatch]    # vault_write
"""
import json, sys, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "automation" / "runs" / "20261106-094235" / "claude-mcp.json"

class MCP:
    def __init__(self):
        srv = json.loads(CFG.read_text(encoding="utf-8"))["mcpServers"]["obsidian"]
        self.url, self.auth, self.sid, self.n = srv["url"], srv["headers"]["Authorization"], None, 0
        r = self._post({"jsonrpc": "2.0", "id": self._id(), "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "koru-review-claude", "version": "1"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, notify=True)
        self.server = r.get("result", {}).get("serverInfo")

    def _id(self):
        self.n += 1
        return self.n

    def _post(self, body, notify=False):
        h = {"Authorization": self.auth, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.sid:
            h["mcp-session-id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.sid = resp.headers.get("mcp-session-id") or self.sid
            raw = resp.read().decode("utf-8")
        if notify or not raw.strip():
            return {}
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        out = {}
        for line in raw.splitlines():        # text/event-stream
            if line.startswith("data:"):
                try:
                    out = json.loads(line[5:].strip())
                except ValueError:
                    pass
        return out

    def call(self, tool, args):
        r = self._post({"jsonrpc": "2.0", "id": self._id(), "method": "tools/call", "params": {"name": tool, "arguments": args}})
        if "error" in r:
            raise RuntimeError(json.dumps(r["error"], ensure_ascii=False))
        res = r.get("result", {})
        text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if res.get("isError"):
            raise RuntimeError(text[:500])
        try:
            return json.loads(text)
        except ValueError:
            return text

    def tools(self):
        return self._post({"jsonrpc": "2.0", "id": self._id(), "method": "tools/list"}).get("result", {}).get("tools", [])

if __name__ == "__main__":
    m = MCP()
    cmd = sys.argv[1]
    if cmd == "list":
        print("server:", m.server)
        for t in m.tools():
            print("-", t["name"], "|", json.dumps(t.get("inputSchema", {}).get("properties", {}), ensure_ascii=False)[:300])
    elif cmd == "call":
        print(json.dumps(m.call(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}), ensure_ascii=False, indent=1)[:20000])
    elif cmd == "read":
        r = m.call("vault_read", {"path": sys.argv[2]})
        content = r.get("content", "") if isinstance(r, dict) else str(r)
        print("version:", r.get("version") if isinstance(r, dict) else None, "| keys:", list(r.keys()) if isinstance(r, dict) else None, "| chars:", len(content), file=sys.stderr)
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(content, encoding="utf-8")
        else:
            print(content)
    elif cmd == "write":
        args = {"path": sys.argv[2], "content": Path(sys.argv[3]).read_text(encoding="utf-8")}
        if len(sys.argv) > 4:
            args["ifMatch"] = sys.argv[4]
        print(json.dumps(m.call("vault_write", args), ensure_ascii=False)[:1000])
