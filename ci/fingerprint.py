"""The fingerprint of a skill: what a green test result is valid for.

    python ci/fingerprint.py [skill ...]     print `name hash` for each skill

The hash covers only what belongs to the skill:

- the skill folder, without `README.md` and `CHANGELOG.md` (documentation, and the
  README gets the generated test line). The folder holds the script, the tests, the
  fixtures, the agent tasks and the test variables.
- the mock specs of the skill: the entries of `ci/specs.json` that list it, without
  the list of skills, so another skill can share a spec

A change to the runner, to the tool versions or to the model does not count. To
test the skills against such a change, start the workflow `Skills` by hand with `force`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from common import Skill, load_skills, read_pins, specs_for

DOC_FILES = {"README.md", "CHANGELOG.md"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
EMPTY_PYTHON = "3.11"
DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_BASE_URL = "https://api.geki.ai/v1"


def settings() -> dict[str, str]:
    """The test setup that a result records: the model, the judge, the versions of Pi and Prism."""
    pins = read_pins()
    return {
        "pi": os.environ.get("PI_VERSION") or pins.get("PI_VERSION", ""),
        "prism": os.environ.get("PRISM_VERSION") or pins.get("PRISM_VERSION", ""),
        "python": EMPTY_PYTHON,
        "model": os.environ.get("AGENT_TEST_MODEL") or DEFAULT_MODEL,
        "base_url": os.environ.get("AGENT_TEST_BASE_URL") or DEFAULT_BASE_URL,
        "judge": os.environ.get("AGENT_JUDGE_MODEL") or "",
    }


def tree_files(folder: Path, skip_docs: bool = False) -> list[Path]:
    out = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or SKIP_PARTS & set(path.relative_to(folder).parts):
            continue
        if path.suffix == ".pyc":
            continue
        if skip_docs and path.parent == folder and path.name in DOC_FILES:
            continue
        out.append(path)
    return out


def specs_of(skill: str) -> str:
    entries = [
        json.dumps({k: v for k, v in entry.items() if k != "skills"}, sort_keys=True)
        for entry in specs_for(skill)
    ]
    return json.dumps(sorted(entries))


def skill_hash(skill: Skill) -> str:
    digest = hashlib.sha256()

    def add(label: str, data: bytes) -> None:
        digest.update(label.encode() + b"\0" + str(len(data)).encode() + b"\0" + data)

    for path in tree_files(skill.path, skip_docs=True):
        add(f"skill:{path.relative_to(skill.path).as_posix()}", path.read_bytes())
    add("specs", specs_of(skill.name).encode())
    return digest.hexdigest()


def hashes(skills: list[Skill] | None = None) -> dict[str, str]:
    return {s.name: skill_hash(s) for s in (skills or load_skills())}


def main(argv: list[str]) -> int:
    for name, value in hashes().items():
        if not argv or name in argv:
            print(name, value[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
