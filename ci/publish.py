"""Publish skills with a higher version to the GEKI skills API.

    python ci/publish.py --base BEFORE_SHA [--dry-run]

For every skill whose `metadata.version` is higher than at the base commit
(or that is new), this builds a zip and calls the GEKI API:

- the skill does not exist yet in the GEKI org: `POST /v1/skills`, with
  `shared_with=all` so every org sees it in the catalog.
- it exists: `POST /v1/skills/{id}` with `mode=new_version`. It never uses
  `overwrite`, so a shared version is never replaced.

The zip has one folder `<name>/` with the skill files, without `tests/`, plus
`assets/logo.svg` from `tools/<tool>/`. Nothing is sent unless
`GEKI_PUBLISH_ENABLED=1` and `GEKI_PUBLISH_KEY` are set. Without them the script
prints what it would do and exits 0.

The shared-skills API is in development. The assumptions about its shape are in
`docs/publish.md`.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

from common import TOOLS, Skill
from versions import evaluate

EXCLUDED_DIRS = {"tests", "__pycache__", ".pytest_cache"}


def build_zip(skill: Skill) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        files = sorted(
            p
            for p in skill.path.rglob("*")
            if p.is_file()
            and not (set(p.relative_to(skill.path).parts) & EXCLUDED_DIRS)
            and p.suffix != ".pyc"
        )
        entries = [(f"{skill.name}/{p.relative_to(skill.path).as_posix()}", p) for p in files]
        logo = TOOLS / skill.tool / "logo.svg"
        if logo.exists():
            entries.append((f"{skill.name}/assets/logo.svg", logo))
        for arcname, path in sorted(entries):
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def multipart(fields: dict[str, str], file_name: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{file_name}"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode()
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class Api:
    def __init__(self, base: str, key: str) -> None:
        self.base = base.rstrip("/")
        self.key = key

    def call(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> dict:
        url = self.base + path + (f"?{urllib.parse.urlencode(params)}" if params else "")
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                f"{method} {path}: {exc.code} {exc.read().decode('utf-8', 'replace')[:500]}"
            ) from exc

    def find(self, name: str) -> dict | None:
        data = self.call("GET", "/v1/skills", {"scope": "own", "q": name, "limit": 100})
        rows = data.get("data", data) if isinstance(data, dict) else data
        return next((r for r in rows if isinstance(r, dict) and r.get("name") == name), None)


def tags_for(skill: Skill) -> str:
    return json.dumps([t for t in (skill.tool, skill.get("geki-category")) if t])


def publish_one(api: Api | None, skill: Skill) -> str:
    data = build_zip(skill)
    existing = api.find(skill.name) if api else None
    if existing is None:
        action = "create and share with all"
    else:
        current = existing.get("version") or existing.get("current_version") or 0
        if int(current) >= skill.version:
            return f"{skill.name}: platform has version {current}, repo has {skill.version}, skip"
        action = f"new_version after {current}"
    if api is None:
        return f"{skill.name}@{skill.version}: would {action} ({len(data)} bytes)"
    fields = {"description": skill.description[:1024], "tags": tags_for(skill)}
    if existing is None:
        fields.update({"name": skill.name, "shared_with": "all"})
        body, ctype = multipart(fields, f"{skill.name}.zip", data)
        api.call("POST", "/v1/skills", body=body, content_type=ctype)
    else:
        fields["mode"] = "new_version"
        body, ctype = multipart(fields, f"{skill.name}.zip", data)
        api.call("POST", f"/v1/skills/{existing['id']}", body=body, content_type=ctype)
    return f"{skill.name}@{skill.version}: {action}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="comma-separated skill names")
    parser.add_argument("--out", type=Path, help="write the zips here")
    args = parser.parse_args()

    selected = [s for s, before, _ in evaluate(args.base) if before is None or s.version > before]
    if args.only:
        wanted = set(args.only.split(","))
        selected = [s for s in selected if s.name in wanted]
    enabled = os.environ.get("GEKI_PUBLISH_ENABLED") == "1" and os.environ.get("GEKI_PUBLISH_KEY")
    api = None
    if enabled and not args.dry_run:
        api = Api(
            os.environ.get("GEKI_API_URL", "https://api.geki.ai"), os.environ["GEKI_PUBLISH_KEY"]
        )
    elif not args.dry_run:
        print("publishing is not enabled (GEKI_PUBLISH_ENABLED=1 and GEKI_PUBLISH_KEY): dry run")
    if not selected:
        print("no skill with a higher version")
    for skill in selected:
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{skill.name}.zip").write_bytes(build_zip(skill))
        print(publish_one(api, skill))
    return 0


if __name__ == "__main__":
    sys.exit(main())
