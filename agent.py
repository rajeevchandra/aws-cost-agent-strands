import json, os, re, subprocess, threading, queue
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
        hello = self.recv(timeout=5)
        if not hello or hello.get("type") != "hello":
            try:
                err = self.proc.stderr.read()
            except Exception:
                err = ""
            raise RuntimeError(f"MCP server failed to start. Stderr:\n{err}")

    def _reader(self):
        for line in self.proc.stdout:
            try:
                self.out_q.put(json.loads(line))
            except Exception:
                pass

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n"); self.proc.stdin.flush()

    def recv(self, timeout=None):
        try:
            return self.out_q.get(timeout=timeout)
        except queue.Empty:
            return None

    def call_tool(self, name, params, call_id="1"):
        self.send({"type": "tool_call", "id": call_id, "name": name, "params": params})
        while True:
            msg = self.recv(timeout=30)
            if not msg:
                raise TimeoutError("No response from MCP server")
            if msg.get("type") == "tool_result" and msg.get("id") == call_id:
                return msg["content"]
            if msg.get("type") == "error":
                details = msg.get("details")
                message = msg.get("message", "tool error")
                if details:
                    raise RuntimeError(f"{message}: {details}")
                raise RuntimeError(message)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

def handle(query: str):
    m = re.search(r"(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", query, re.IGNORECASE)
    if not m:
        return {"message":"Ask like: 'What is my spend from 2025-09-01 to 2025-10-01?'", "hint":"Include 'YYYY-MM-DD to YYYY-MM-DD'."}
    start, end = m.group(1), m.group(2)

    mcp_cmd = os.getenv("MCP_COMMAND", "python mcp_cost_server_safe.py").split()
    mcp = MCPClient(mcp_cmd); mcp.start()
    try:
        tool_name = "get_cost_forecast" if re.search(r"forecast", query, re.IGNORECASE) else "get_cost_summary"
        tool_data = mcp.call_tool(tool_name, {"start": start, "end": end})
    finally:
        mcp.stop()

    system = "You are a FinOps assistant. Summarize totals and top drivers for non-experts."              if tool_name == "get_cost_summary"              else "You are a FinOps assistant. Explain the forecast and any confidence ranges in plain English."
    prompt = f"Summarize this cost data: {json.dumps(tool_data)}"
    model_out = invoke_bedrock([{"role":"user","content":prompt}], system_prompt=system)
    return {"tool_data": tool_data, "summary": model_out}
