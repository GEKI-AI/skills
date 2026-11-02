"""A scripted OpenAI-compatible model server, to test the agent runner without a real model.

The script is a list of steps. Step N answers the request that follows N tool
results. A step is `{"tool": "bash", "arguments": {...}}` or `{"text": "..."}`.
The server keeps every request body in `requests`.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeLLM:
    def __init__(self, script: list[dict]) -> None:
        self.script = script
        self.requests: list[dict] = []
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> str:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                fake.requests.append(body)
                results = sum(1 for m in body.get("messages", []) if m.get("role") == "tool")
                step = fake.script[min(results, len(fake.script) - 1)]
                chunks = fake.chunks(step, body.get("model", "fake"))
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for chunk in chunks:
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    message = {"role": "assistant", "content": step.get("text")}
                    if "tool" in step:
                        message["tool_calls"] = [fake.tool_call(step)]
                    reply = {
                        "id": "fake",
                        "object": "chat.completion",
                        "created": 0,
                        "model": body.get("model"),
                        "choices": [
                            {
                                "index": 0,
                                "message": message,
                                "finish_reason": "tool_calls" if "tool" in step else "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    }
                    data = json.dumps(reply).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    @staticmethod
    def tool_call(step: dict) -> dict:
        return {
            "id": "call_1",
            "type": "function",
            "function": {"name": step["tool"], "arguments": json.dumps(step["arguments"])},
        }

    @staticmethod
    def chunks(step: dict, model: str) -> list[dict]:
        def chunk(delta: dict, finish: str | None = None) -> dict:
            return {
                "id": "fake",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }

        if "tool" in step:
            call = FakeLLM.tool_call(step)
            return [
                chunk({"role": "assistant", "content": None, "tool_calls": [{"index": 0, **call}]}),
                chunk({}, "tool_calls"),
            ]
        return [chunk({"role": "assistant", "content": step["text"]}), chunk({}, "stop")]
