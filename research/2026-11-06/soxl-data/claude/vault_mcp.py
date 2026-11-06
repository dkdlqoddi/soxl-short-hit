"""obsidian MCP 서버(Local REST API with MCP)를 JSON-RPC로 직접 호출하는 도우미.
세션 시작 때 MCP 연결이 실패해 도구가 로드되지 않았을 때만 쓴다. 토큰은 파일에 적지 않고
실행 폴더의 claude-mcp.json(오케스트레이터가 0600으로 만든 설정)에서 읽는다.

사용: python3 vault_mcp.py list <dir> | read <path> [out_file] | write <path> <content_file> [ifMatch]"""
import json, sys, urllib.request, pathlib

CFG = pathlib.Path("/home/dkdlqoddi/012_gemini/soxl-short-hit/automation/runs/20261106-094235/claude-mcp.json")


class MCP:
    def __init__(self):
        srv = json.loads(CFG.read_text())["mcpServers"]["obsidian"]
        self.url, self.headers = srv["url"], dict(srv["headers"])
        self.headers.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        self.sid, self.n = None, 0
        r = self._post({"jsonrpc": "2.0", "id": self._id(), "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "soxl-review-claude", "version": "1"}}}, init=True)
        self.server = r.get("result", {}).get("serverInfo")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, notify=True)

    def _id(self):
        self.n += 1
        return self.n

    def _post(self, body, init=False, notify=False):
        h = dict(self.headers)
        if self.sid:
            h["mcp-session-id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            if init:
                self.sid = resp.headers.get("mcp-session-id")
            raw = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")
        if notify or not raw.strip():
            return {}
        if "text/event-stream" in ctype:
            data = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
            raw = data[-1]
        return json.loads(raw)

    def tools(self):
        return self._post({"jsonrpc": "2.0", "id": self._id(), "method": "tools/list"})["result"]["tools"]

    def call(self, name, args):
        r = self._post({"jsonrpc": "2.0", "id": self._id(), "method": "tools/call", "params": {"name": name, "arguments": args}})
        if "error" in r:
            raise RuntimeError(r["error"])
        res = r["result"]
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        if res.get("isError"):
            raise RuntimeError(text)
        return text


if __name__ == "__main__":
    m = MCP()
    cmd = sys.argv[1]
    if cmd == "tools":
        for t in m.tools():
            print(t["name"], "|", json.dumps(t.get("inputSchema", {}).get("properties", {}), ensure_ascii=False)[:400])
    elif cmd == "list":
        print(m.call("vault_list", {"path": sys.argv[2]}))
    elif cmd == "read":
        t = m.call("vault_read", {"path": sys.argv[2]})
        if len(sys.argv) > 3:
            pathlib.Path(sys.argv[3]).write_text(t, encoding="utf-8")
            print("saved", len(t))
        else:
            print(t)
    elif cmd == "write":
        args = {"path": sys.argv[2], "content": pathlib.Path(sys.argv[3]).read_text(encoding="utf-8")}
        if len(sys.argv) > 4:
            args["ifMatch"] = sys.argv[4]
        print(m.call("vault_write", args))
