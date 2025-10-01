import os, json, re, subprocess, threading, queue
from bedrock_model import invoke_bedrock

class MCPClient:
    def __init__(self, cmd):
        self.cmd = cmd
        self.proc = None
        self.out_q = queue.Queue()

    def start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        t = threading.Thread(target=self._reader, daemon=True); t.start()
        hello = self.out_q.get(timeout=5)
        if not isinstance(hello, dict) or hello.get("type") != "hello":
            err = self.proc.stderr.read()
            raise RuntimeError(f"MCP server failed to start. Stderr:\n{err}")

    def _reader(self):
        for line in self.proc.stdout:
            try:
                self.out_q.put(json.loads(line))
            except Exception:
                pass

    def call(self, name, params):
        call_id = "1"
        self.proc.stdin.write(json.dumps({"type":"tool_call","id":call_id,"name":name,"params":params}) + "\n")
        self.proc.stdin.flush()
        while True:
            msg = self.out_q.get(timeout=30)
            if msg.get("type") == "tool_result" and msg.get("id") == call_id:
                return msg["content"]
            if msg.get("type") == "error":
                details = msg.get("details"); message = msg.get("message","tool error")
                raise RuntimeError(message + (": "+details if details else ""))

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

def run_with_strands_like_agent(query: str):
    m = re.search(r"(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", query, re.IGNORECASE)
    if not m:
        return {"message": "Please include a date range 'YYYY-MM-DD to YYYY-MM-DD'."}
    start, end = m.group(1), m.group(2)

    mcp_cmd = os.getenv("MCP_COMMAND","python mcp_cost_server_safe.py").split()
    mcp = MCPClient(mcp_cmd); mcp.start()
    try:
        name = "get_cost_forecast" if re.search(r"forecast", query, re.IGNORECASE) else "get_cost_summary"
        data = mcp.call(name, {"start": start, "end": end})
    finally:
        mcp.stop()

    system = "You are a FinOps assistant. Summarize totals and top drivers for non-experts."              if name == "get_cost_summary"              else "You are a FinOps assistant. Explain the forecast in plain English."
    prompt = f"Summarize this cost data: {json.dumps(data)}"
    summary = invoke_bedrock([{"role":"user","content":prompt}], system_prompt=system)
    return {"tool_data": data, "summary": summary}
