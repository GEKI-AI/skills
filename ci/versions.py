"""Compare skill versions with a base commit.

    python ci/versions.py check --base origin/main     fail when a changed skill keeps its version
    python ci/versions.py bumped --base BEFORE_SHA     print the skills whose version is higher, as JSON

A skill counts as changed when a file outside `tests/` and `README.md` changed.
A new skill needs no earlier version. An unknown or empty base means every skill
is new.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import yaml
from common import Skill, load_skills, run, split_frontmatter


def base_exists(base: str) -> bool:
    if not base or set(base) == {"0"}:
        return False
    return bool(run("git", "cat-file", "-t", base, check=False).strip())


def version_at(base: str, name: str) -> int | None:
    text = run("git", "show", f"{base}:skills/{name}/SKILL.md", check=False)
    if not text:
        return None
    parts = split_frontmatter(text)
    try:
        meta = (yaml.safe_load("\n".join(parts[0])) or {}).get("metadata", {}) if parts else {}
        return int(meta.get("version"))
    except (ValueError, TypeError, AttributeError, yaml.YAMLError):
        return 0


def changed_files(base: str, name: str) -> list[str]:
    out = run("git", "diff", "--name-only", f"{base}...HEAD", "--", f"skills/{name}", check=False)
    prefix = f"skills/{name}/"
    files = [line for line in out.splitlines() if line.startswith(prefix)]
    return [f for f in files if not f.startswith(prefix + "tests/") and f != prefix + "README.md"]


def evaluate(base: str) -> list[tuple[Skill, int | None, bool]]:
    """(skill, version at base, changed) for each skill."""
    known = base_exists(base)
    rows = []
    for skill in load_skills():
        before = version_at(base, skill.name) if known else None
        changed = True if before is None else bool(changed_files(base, skill.name))
        rows.append((skill, before, changed))
    return rows


def check(base: str) -> int:
    failed = False
    for skill, before, changed in evaluate(base):
        if before is None or not changed:
            continue
        if skill.version <= before:
            failed = True
            print(f"skills/{skill.name}: files changed, raise metadata.version above {before}")
        changelog = (skill.path / "CHANGELOG.md").read_text(encoding="utf-8")
        if not re.search(rf"^## {skill.version}\b", changelog, re.MULTILINE):
            failed = True
            print(f"skills/{skill.name}: CHANGELOG.md needs a '## {skill.version}' entry")
    if not failed:
        print("ok: versions and changelogs")
    return 1 if failed else 0


def bumped(base: str) -> int:
    out = [
        {"name": skill.name, "version": skill.version, "previous": before}
        for skill, before, _changed in evaluate(base)
        if before is None or skill.version > before
    ]
    print(json.dumps(out))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["check", "bumped"])
    parser.add_argument("--base", default="")
    args = parser.parse_args()
    return check(args.base) if args.action == "check" else bumped(args.base)


if __name__ == "__main__":
    sys.exit(main())
