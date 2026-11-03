"""Which skills does a change touch?

    python ci/affected.py --base REF       print the affected skills as JSON
    python ci/affected.py --all            print every skill

The rules, by changed path:

- `skills/<name>/...`  that skill
- `ci/specs.json`      the skills whose specs changed
- documentation (`*.md` at the root, `docs/`, `.github/`, `LICENSE`, `NOTICE`,
  `.gitignore`, `package.json`)  nothing
- everything else (`ci/`, `.forgejo/`, `conftest.py`, `pyproject.toml`,
  unknown files)  every skill

The skills come from the repo, not from a list in a workflow. An empty
or unknown base means every skill. The result is a superset: the fingerprint of a
skill (`ci/fingerprint.py`) decides what really runs.
"""

from __future__ import annotations

import argparse
import json
import sys

from common import load_skills, run, specs_for

IGNORED_FILES = {
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "LICENSE",
    "NOTICE",
    ".gitignore",
    "package.json",
}
IGNORED_DIRS = ("docs/", ".github/")


SPECS_PATH = "ci/specs.json"


def affected(paths: list[str], names: list[str], spec_users: list[str] | None = None) -> list[str]:
    """Skill names touched by `paths`. `spec_users` are the skills whose specs changed, if known."""
    hit: set[str] = set()
    for path in paths:
        parts = path.split("/")
        if parts[0] == "skills" and len(parts) > 2:
            if parts[1] in names:
                hit.add(parts[1])
        elif path == SPECS_PATH and spec_users is not None:
            hit.update(name for name in spec_users if name in names)
        elif path in IGNORED_FILES or path.startswith(IGNORED_DIRS):
            continue
        else:
            return sorted(names)
    return sorted(hit)


def base_known(base: str) -> bool:
    if not base or set(base) == {"0"}:
        return False
    return bool(run("git", "cat-file", "-t", base, check=False).strip())


def changed_paths(base: str) -> list[str] | None:
    """Paths changed since the merge base of `base` and HEAD. None when the base is unknown."""
    if not base_known(base):
        return None
    if not run("git", "merge-base", base, "HEAD", check=False).strip():
        return None
    out = run("git", "diff", "--name-only", f"{base}...HEAD", check=False)
    return [line for line in out.splitlines() if line]


def spec_users(base: str, names: list[str]) -> list[str]:
    """Skills whose specs differ between `base` and the working tree."""
    before = run("git", "show", f"{base}:{SPECS_PATH}", check=False)
    try:
        return [name for name in names if specs_for(name, before) != specs_for(name)]
    except (ValueError, TypeError, KeyError):
        return names


def affected_since(base: str) -> tuple[list[str], str]:
    """(skill names, reason) for a base."""
    names = [s.name for s in load_skills()]
    paths = changed_paths(base)
    if paths is None:
        return sorted(names), "base unknown, every skill"
    users = spec_users(base, names) if SPECS_PATH in paths else None
    return affected(paths, names, users), f"{len(paths)} changed files"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all:
        names = sorted(s.name for s in load_skills())
    else:
        names, _ = affected_since(args.base)
    print(json.dumps(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
