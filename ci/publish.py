"""Publish skills to the GEKI skills API.

    python ci/publish.py [--base COMMIT] [--only a,b] [--require-verified] [--dry-run]

For every skill this builds a zip and compares the repo `metadata.version` with the
`meta.version` of the current version on the platform. Without `--base` that is every skill. With
`--base`, only skills that are new or have a higher version than at that commit.

- the skill does not exist yet in the platform org: `POST /v1/skills`, with
  `shared_with=all` so every org sees it in the catalog.
- it exists: `POST /v1/skills/{id}` with `mode=new_version`. It never uses
  `overwrite`, so a shared version is never replaced.
- the platform has the same or a higher version: skipped. A second run does nothing.
- a shared skill of the platform org has no folder in the repo any more: it gets
  `deprecated=true`, so the catalog hides it. Pins keep working. It comes after all
  uploads, and `--only` leaves it out. A skill that comes back gets `deprecated=false`.

The zip has one folder `<name>/` with the skill files (including `assets/logo.svg`),
without `tests/`. Its `SKILL.md` gets `geki-tested` (the date of the green result) in
`metadata`. The repo files stay as they are. The `tags` field comes from `geki-tags`.

The script sends nothing unless `GEKI_PUBLISH_ENABLED=1` and `GEKI_PUBLISH_KEY` are
set, and it fails when they are not (`--dry-run` only prints. With a key it reads the
platform, so its lines say what a real run would do). With
`--require-verified` a skill without a green test result for its current files
(`ci/results.py`) stops the whole run before anything is sent.

The API is `services/geki-api/docs/skills.md` in geki-core, section Shared skills.
The assumptions are in `docs/publish.md`.
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

from common import Skill, load_skills
from versions import evaluate

EXCLUDED_DIRS = {"tests", "__pycache__", ".pytest_cache"}


def with_metadata(text: str, values: dict[str, str]) -> str:
    """`text` with each value set under the top-level `metadata:` map of the frontmatter."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "metadata:"), None)
    if start is None:
        return text
    end = start + 1
    while end < len(lines) and lines[end][:1].isspace():
        end += 1
    indent = "  "
    if end > start + 1:
        first = lines[start + 1]
        indent = first[: len(first) - len(first.lstrip())]
    keep = [line for line in lines[start + 1 : end] if line.split(":", 1)[0].strip() not in values]
    added = [f"{indent}{key}: {json.dumps(value)}" for key, value in values.items() if value]
    return "\n".join(lines[: start + 1] + keep + added + lines[end:])


def zip_metadata(skill: Skill, tested: str = "") -> dict[str, str]:
    return {"geki-tested": tested[:10]}


def build_zip(skill: Skill, tested: str = "") -> bytes:
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
        for arcname, path in sorted(entries):
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if os.access(path, os.X_OK) else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            data = path.read_bytes()
            if arcname == f"{skill.name}/SKILL.md":
                text = with_metadata(data.decode("utf-8"), zip_metadata(skill, tested))
                data = text.encode("utf-8")
            archive.writestr(info, data)
    return buffer.getvalue()


def multipart(
    fields: dict[str, str], file_name: str | None = None, data: bytes = b""
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    if file_name:
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
            detail = exc.read().decode("utf-8", "replace")[:500]
            hint = ""
            if exc.code == 403 and "staff_only" in detail:
                hint = " (only a key of the platform org may set shared_with)"
            raise SystemExit(f"{method} {path}: {exc.code} {detail}{hint}") from exc

    def find(self, name: str) -> dict | None:
        """The skill of the key's org with this name. Reads every page of the search."""
        after = None
        for _ in range(50):
            params = {"scope": "own", "q": name, "limit": 100}
            if after:
                params["after"] = after
            data = self.call("GET", "/v1/skills", params)
            rows = data.get("data", []) if isinstance(data, dict) else data
            found = next((r for r in rows if isinstance(r, dict) and r.get("name") == name), None)
            if found or not isinstance(data, dict) or not data.get("has_more"):
                return found
            after = data.get("last_id")
        return None

    def own_skills(self) -> list[dict]:
        """Every skill of the key's org, also the deprecated ones."""
        out: list[dict] = []
        after = None
        for _ in range(50):
            params = {"scope": "own", "limit": 100}
            if after:
                params["after"] = after
            data = self.call("GET", "/v1/skills", params)
            out.extend(r for r in data.get("data", []) if isinstance(r, dict))
            if not data.get("has_more"):
                return out
            after = data.get("last_id")
        raise SystemExit("GET /v1/skills: too many pages, nothing was hidden")

    def set_deprecated(self, skill_id: str, value: bool) -> None:
        """The API has no call for the flag alone: this adds a version with the same files."""
        fields = {"mode": "new_version", "deprecated": "true" if value else "false"}
        body, ctype = multipart(fields)
        self.call("POST", f"/v1/skills/{skill_id}", body=body, content_type=ctype)


def tags_for(skill: Skill) -> str:
    return json.dumps(skill.list("geki-tags"))


def publish_one(api: Api | None, skill: Skill, tested: str = "", dry_run: bool = False) -> str:
    data = build_zip(skill, tested)
    existing = api.find(skill.name) if api else None
    if existing is None:
        action = "create and share with all"
    else:
        current = (existing.get("meta") or {}).get("version") or 0
        if int(current) >= skill.version:
            if existing.get("deprecated"):
                if dry_run:
                    return f"{skill.name}: back in the repo, the catalog would show it again"
                api.set_deprecated(existing["id"], False)
                return f"{skill.name}: back in the repo, the catalog shows it again"
            return f"{skill.name}: platform has version {current}, repo has {skill.version}, skip"
        action = f"new_version after {current}"
    if api is None:
        return f"{skill.name}@{skill.version}: would upload, no key to read the platform ({len(data)} bytes)"
    if dry_run:
        return f"{skill.name}@{skill.version}: would {action} ({len(data)} bytes)"
    fields = {"description": skill.description[:1024], "tags": tags_for(skill)}
    if existing is None:
        fields.update({"name": skill.name, "shared_with": "all"})
        body, ctype = multipart(fields, f"{skill.name}.zip", data)
        api.call("POST", "/v1/skills", body=body, content_type=ctype)
    else:
        fields["mode"] = "new_version"
        if existing.get("deprecated"):
            fields["deprecated"] = "false"
        if existing.get("shared_with", "all") != "all":
            fields["shared_with"] = "all"
        body, ctype = multipart(fields, f"{skill.name}.zip", data)
        api.call("POST", f"/v1/skills/{existing['id']}", body=body, content_type=ctype)
    return f"{skill.name}@{skill.version}: {action}"


def removed_from_repo(rows: list[dict], names: set[str]) -> list[dict]:
    """The catalog skills without a folder in the repo. Skills not shared with all stay."""
    if not names:
        raise SystemExit("no skill in the repo, nothing was hidden")
    return [
        row
        for row in rows
        if row.get("shared_with") == "all"
        and not row.get("deprecated")
        and row.get("name") not in names
    ]


def hide_removed(api: Api, *, dry_run: bool) -> None:
    names = {skill.name for skill in load_skills()}
    for row in removed_from_repo(api.own_skills(), names):
        if dry_run:
            print(f"{row['name']}: not in the repo, would hide it in the catalog")
        else:
            api.set_deprecated(row["id"], True)
            print(f"{row['name']}: not in the repo, hidden in the catalog")


def tested_dates(skills: list[Skill], ref: str) -> dict[str, str]:
    """The date of the green result for the current files, per verified skill."""
    from fingerprint import hashes
    from results import fetch_results, green_result, load_ref

    fetch_results()
    results = load_ref(ref)
    current = hashes(skills)
    return {
        s.name: str(verified.get("date", ""))[:10]
        for s in skills
        if (verified := green_result(s.name, current, results))
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="comma-separated skill names")
    parser.add_argument("--out", type=Path, help="write the zips here")
    parser.add_argument("--require-verified", action="store_true")
    parser.add_argument("--results-ref", default="origin/test-results")
    args = parser.parse_args()

    selected = [s for s, before, _ in evaluate(args.base) if before is None or s.version > before]
    if args.only:
        wanted = set(args.only.split(","))
        selected = [s for s in selected if s.name in wanted]
    api = None
    tested: dict[str, str] = {}
    if args.dry_run:
        if os.environ.get("GEKI_PUBLISH_KEY"):
            api = Api(
                os.environ.get("GEKI_API_URL") or "https://api.geki.ai",
                os.environ["GEKI_PUBLISH_KEY"],
            )
    else:
        if os.environ.get("GEKI_PUBLISH_ENABLED") != "1":
            print("publishing is not enabled: set the variable PUBLISH_ENABLED to true")
            return 1
        if not os.environ.get("GEKI_PUBLISH_KEY"):
            print("GEKI_PUBLISH_KEY is not set: add the secret of a key of the platform org")
            return 1
        api = Api(
            os.environ.get("GEKI_API_URL") or "https://api.geki.ai",
            os.environ["GEKI_PUBLISH_KEY"],
        )
        if args.require_verified:
            tested = tested_dates(selected, args.results_ref)
            missing = [s.name for s in selected if s.name not in tested]
            if missing:
                print(
                    "no green test result for the current files of: "
                    + ", ".join(missing)
                    + ". Nothing was published. Run the Skills workflow and tag again."
                )
                return 1
    if not selected:
        print("no skill with a higher version")
    for skill in selected:
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{skill.name}.zip").write_bytes(
                build_zip(skill, tested.get(skill.name, ""))
            )
        print(publish_one(api, skill, tested.get(skill.name, ""), dry_run=args.dry_run))
    if args.only:
        return 0
    if api:
        hide_removed(api, dry_run=args.dry_run)
    else:
        print("no key: cannot read which skills left the repo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
