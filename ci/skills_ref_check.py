"""Run the Agent Skills reference validator (`skills-ref`) on every skill.

    python ci/skills_ref_check.py

Install it with the pinned commit in `.github/workflows/ci.yml`. The PyPI package
`skills-ref` installs the command under another name, so the script uses the
Python API.
"""

from __future__ import annotations

import sys

from common import skill_paths
from skills_ref import validate


def main() -> int:
    failed = False
    for path in skill_paths():
        errors = validate(path)
        for error in errors:
            failed = True
            print(f"{path.name}: {error}")
    if not failed:
        print(f"ok: skills-ref accepts {len(skill_paths())} skills")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
