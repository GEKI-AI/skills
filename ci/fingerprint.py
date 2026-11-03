"""The fingerprint of a skill: what a green test result is valid for.

    python ci/fingerprint.py [skill ...]     print `name hash` for each skill

The hash covers:

- the skill folder, without `README.md` and `CHANGELOG.md` (documentation, and the
  README gets the generated test line)
- the mock specs of the skill (the entries of `ci/specs.json` that list it)
- the versions of Pi and Prism (`ci/pins.env`) and the Python of the empty environment
- the test model, the judge model and the model base URL
- the runner code: the files in `RUNNER_FILES`

Change any of these and a green result no longer counts.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from common import ROOT, Skill, load_skills, read_pins, specs_for

RUNNER_FILES = [
    "conftest.py",
    "pyproject.toml",
    "ci/common.py",
    "ci/mockserver.py",
    "ci/mocks.py",
    "ci/agent_test.py",
    "ci/run_scripts.py",
    "ci/requirements.txt",
]
DOC_FILES = {"README.md", "CHANGELOG.md"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
EMPTY_PYTHON = "3.11"
DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_BASE_URL = "https://api.geki.ai/v1"


def settings() -> dict[str, str]:
    """The test settings that are not files: the model, the judge, the versions of Pi and Prism."""
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
    return json.dumps(specs_for(skill), sort_keys=True)


def skill_hash(skill: Skill, config: dict[str, str] | None = None) -> str:
    config = config or settings()
    digest = hashlib.sha256()

    def add(label: str, data: bytes) -> None:
        digest.update(label.encode() + b"\0" + str(len(data)).encode() + b"\0" + data)

    for path in tree_files(skill.path, skip_docs=True):
        add(f"skill:{path.relative_to(skill.path).as_posix()}", path.read_bytes())
    add("specs", specs_of(skill.name).encode())
    for name in RUNNER_FILES:
        path = ROOT / name
        add(f"runner:{name}", path.read_bytes() if path.exists() else b"")
    add("config", json.dumps(config, sort_keys=True).encode())
    return digest.hexdigest()


def hashes(skills: list[Skill] | None = None) -> dict[str, str]:
    config = settings()
    return {s.name: skill_hash(s, config) for s in (skills or load_skills())}


def main(argv: list[str]) -> int:
    for name, value in hashes().items():
        if not argv or name in argv:
            print(name, value[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
