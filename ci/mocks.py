"""Start and stop the Prism mocks of one tool.

    python ci/mocks.py start TOOL [--work DIR]   prints MOCK_UPSTREAM_<TOOL>=...
    python ci/mocks.py stop [--work DIR]

The specs are listed in `ci/specs.json` with pinned URLs. Prism (Stoplight,
Apache 2.0) is the binary `prism`, from `npm install @stoplight/prism-cli`.
A tool without specs (Zammad) prints nothing: its tests use fixtures only.

Spec fixups: `one-of-to-any-of` turns `oneOf` into `anyOf`. Atlassian's
Confluence v2 spec marks the page body as `oneOf` two schemas that both match,
so Prism would reject every valid write.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def rename_key(node: object, old: str, new: str) -> object:
    if isinstance(node, dict):
        return {(new if k == old else k): rename_key(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [rename_key(v, old, new) for v in node]
    return node


def fetch(url: str, target: Path) -> None:
    if target.exists():
        return
    request = urllib.request.Request(url, headers={"User-Agent": "geki-skills-ci"})
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())


def wait_for(port: int, seconds: int) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def prism_binary(work: Path) -> str:
    candidates = [
        os.environ.get("PRISM", ""),
        str(ROOT / ".cache" / "prism" / "node_modules" / ".bin" / "prism"),
        shutil.which("prism") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("prism not found: npm install --prefix .cache/prism @stoplight/prism-cli@5.16.0")


def start(tool: str, work: Path) -> str:
    """Start Prism for the specs of a tool. Returns the `MOCK_UPSTREAM_<TOOL>` value, empty without specs."""
    specs = json.loads((ROOT / "ci" / "specs.json").read_text(encoding="utf-8")).get(tool, [])
    if not specs:
        return ""
    work.mkdir(parents=True, exist_ok=True)
    prism = prism_binary(work)
    upstreams: list[str] = []
    pids: list[int] = []
    ports: list[int] = []
    for index, spec in enumerate(specs):
        raw = work / f"{tool}-{index}.raw.json"
        fetch(spec["url"], raw)
        path = work / f"{tool}-{index}.json"
        document = json.loads(raw.read_text(encoding="utf-8"))
        if "one-of-to-any-of" in spec.get("fixups", []):
            document = rename_key(document, "oneOf", "anyOf")
        path.write_text(json.dumps(document), encoding="utf-8")
        port = free_port()
        log = open(work / f"prism-{tool}-{index}.log", "wb")  # noqa: SIM115
        proc = subprocess.Popen(
            [prism, "mock", "--port", str(port), "--host", "127.0.0.1", str(path)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pids.append(proc.pid)
        ports.append(port)
        suffix = ",strip" if spec.get("strip") else ""
        if spec.get("rewrite"):
            suffix += f",rewrite={spec['rewrite']}"
        upstreams.append(f"{spec['prefix']}=http://127.0.0.1:{port}{suffix}")
    (work / f"pids-{tool}.json").write_text(json.dumps(pids), encoding="utf-8")
    for port in ports:
        if not wait_for(port, 240):
            sys.exit(f"prism on port {port} did not start, see {work}/prism-*.log")
    return ";".join(upstreams)


@contextlib.contextmanager
def serve(tool: str, work: Path = ROOT / ".cache" / "mocks"):
    """Prism mocks of a tool while the block runs. Sets `MOCK_UPSTREAM_<TOOL>` in the environment."""
    name = f"MOCK_UPSTREAM_{tool.upper()}"
    try:
        value = start(tool, work)
        if value:
            os.environ[name] = value
        yield value
    finally:
        os.environ.pop(name, None)
        stop(work)


def stop(work: Path) -> None:
    for file in work.glob("pids-*.json"):
        for pid in json.loads(file.read_text(encoding="utf-8")):
            with contextlib.suppress(OSError):
                os.killpg(pid, signal.SIGTERM)
        file.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("tool", nargs="?")
    parser.add_argument("--work", type=Path, default=ROOT / ".cache" / "mocks")
    args = parser.parse_args()
    if args.action == "start":
        if not args.tool:
            parser.error("start needs a tool")
        value = start(args.tool, args.work)
        if value:
            print(f"MOCK_UPSTREAM_{args.tool.upper()}={value}")
    else:
        stop(args.work)


if __name__ == "__main__":
    main()
