"""A small HTTP mock for skill tests.

It serves fixtures from a `routes.json` file and logs every request. With
`--upstream PREFIX=URL[,strip]` it first forwards the request to a Prism mock
that was started from the vendor OpenAPI spec. Prism rejects requests that do
not match the spec. The mock records such a rejection as a violation. When
Prism accepts the request, the mock answers with the fixture, so tests see
realistic data. Without a fixture, the Prism answer goes through.

Routes file: a JSON list of objects with `method`, `path` (with `{name}`
parts), optional `query` (subset of the query), optional `json` (subset of the
request body), `status`, and `body` or `file` (path relative to the routes file).

The log is a list of requests: method, path, query, headers, body.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "date", "server"}


def _subset(want: object, have: object) -> bool:
    if isinstance(want, dict):
        return (
            not want
            or isinstance(have, dict)
            and all(k in have and _subset(v, have[k]) for k, v in want.items())
        )
    return want == have


def _template(path: str) -> re.Pattern[str]:
    pieces = re.split(r"\{[^/}]+\}", path)
    return re.compile("^" + "[^/]+".join(re.escape(p) for p in pieces) + "$")


def request_violations(headers: dict[str, str]) -> list[dict]:
    """Violations of the request. Prism also reports its own generated examples; those are not ours."""
    try:
        found = json.loads(headers.get("sl-violations", "[]"))
    except ValueError:
        return [{"message": headers.get("sl-violations", "")}]
    return [v for v in found if (v.get("location") or ["request"])[0] == "request"]


class Upstream:
    def __init__(self, spec: str) -> None:
        target, *flags = spec.split(",")
        prefix, _, url = target.partition("=")
        self.prefix = prefix.rstrip("/")
        self.strip = "strip" in flags
        self.rewrite = next((f[len("rewrite=") :] for f in flags if f.startswith("rewrite=")), "")
        parts = urlsplit(url)
        self.host = parts.hostname or "127.0.0.1"
        self.port = parts.port or 80

    def matches(self, path: str) -> bool:
        return path == self.prefix or path.startswith(self.prefix + "/") or not self.prefix

    def forward(
        self, method: str, path: str, query: str, headers: dict[str, str], body: bytes
    ) -> tuple[int, dict[str, str], bytes]:
        target = path[len(self.prefix) :] if self.strip else path
        if self.rewrite:
            target = self.rewrite + path[len(self.prefix) :]
        if not target.startswith("/"):
            target = "/" + target
        if query:
            target += "?" + query
        conn = http.client.HTTPConnection(self.host, self.port, timeout=60)
        try:
            conn.request(method, target, body=body or None, headers=headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, data
        finally:
            conn.close()


class Mock:
    def __init__(self, routes: Path | None = None, upstreams: list[str] | None = None) -> None:
        self.routes: list[dict] = []
        self.base = routes.parent if routes else Path(".")
        if routes and routes.exists():
            self.routes = json.loads(routes.read_text(encoding="utf-8"))
        self.upstreams = [Upstream(spec) for spec in (upstreams or []) if spec.strip()]
        self.requests: list[dict] = []
        self.violations: list[dict] = []
        self.unmatched: list[dict] = []
        self.lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None

    def start(self, port: int = 0, host: str = "127.0.0.1") -> str:
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def do_GET(self) -> None:
                mock.handle(self)

            do_POST = do_PUT = do_PATCH = do_DELETE = do_GET

        self._server = ThreadingHTTPServer((host, port), Handler)
        threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        return self.url

    @property
    def url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def find(self, entry: dict) -> dict | None:
        for route in self.routes:
            if route["method"].upper() != entry["method"]:
                continue
            if not _template(route["path"]).match(entry["path"]):
                continue
            if not _subset(route.get("query", {}), entry["query"]):
                continue
            if not _subset(route.get("json", {}), entry["body"]):
                continue
            return route
        return None

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        parts = urlsplit(handler.path)
        if parts.path == "/__requests":
            return self.reply(handler, 200, {}, json.dumps(self.requests).encode())
        if parts.path == "/__violations":
            return self.reply(handler, 200, {}, json.dumps(self.violations).encode())
        length = int(handler.headers.get("Content-Length") or 0)
        raw = handler.rfile.read(length) if length else b""
        try:
            body: object = json.loads(raw) if raw else None
        except ValueError:
            body = raw.decode("utf-8", "replace")
        entry = {
            "method": handler.command,
            "path": parts.path,
            "query": {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parts.query).items()},
            "headers": {k.lower(): v for k, v in handler.headers.items()},
            "body": body,
        }
        with self.lock:
            self.requests.append(entry)
        upstream = next((u for u in self.upstreams if u.matches(parts.path)), None)
        answer: tuple[int, dict[str, str], bytes] | None = None
        if upstream is not None:
            forward = {
                k: v for k, v in entry["headers"].items() if k in {"authorization", "content-type"}
            }
            forward["accept"] = "application/json"
            try:
                answer = upstream.forward(handler.command, parts.path, parts.query, forward, raw)
            except OSError as exc:
                return self.reply(handler, 502, {}, f"upstream mock failed: {exc}".encode())
            status, headers, data = answer
            violated = (
                request_violations(headers)
                or status in (401, 404, 422)
                or (status == 400 and not data)
            )
            if violated:
                note = headers.get("sl-violations") or data.decode("utf-8", "replace")[:300]
                self.violations.append(
                    {"request": f"{entry['method']} {entry['path']}", "detail": note}
                )
                return self.reply(handler, status, headers, data)
        route = self.find(entry)
        if route is not None:
            payload = route.get("body")
            if "file" in route:
                payload = json.loads((self.base / route["file"]).read_text(encoding="utf-8"))
            data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
            ctype = "text/plain" if isinstance(payload, str) else "application/json"
            return self.reply(handler, route.get("status", 200), {"content-type": ctype}, data)
        if answer is not None:
            return self.reply(handler, *answer)
        self.unmatched.append({"request": f"{entry['method']} {entry['path']}"})
        message = json.dumps({"error": f"no fixture for {entry['method']} {entry['path']}"})
        self.reply(handler, 404, {"content-type": "application/json"}, message.encode())

    @staticmethod
    def reply(
        handler: BaseHTTPRequestHandler, status: int, headers: dict[str, str], data: bytes
    ) -> None:
        handler.send_response(status)
        for key, value in headers.items():
            if key.lower() not in HOP:
                handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--upstream", action="append", default=[])
    args = parser.parse_args()
    mock = Mock(args.routes, args.upstream)
    print(mock.start(args.port), flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
