"""Print facts about skills for the workflows.

    python ci/declared.py names [SKILL ...]      skill names
    python ci/declared.py paths [SKILL ...]      skill folders
    python ci/declared.py packages [SKILL ...]   declared Python packages
    python ci/declared.py env [SKILL ...]        variable names (secrets and settings)

Without skill names, or with `*`, all skills.
"""

from __future__ import annotations

import sys

from common import load_skills


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 2
    wanted = {name for name in argv[1:] if name != "*"}
    chosen = [s for s in load_skills() if not wanted or s.name in wanted]
    if argv[0] == "names":
        out = [s.name for s in chosen]
    elif argv[0] == "paths":
        out = [f"skills/{s.name}" for s in chosen]
    elif argv[0] == "packages":
        out = sorted({p for s in chosen for p in s.list("geki-python")})
    elif argv[0] == "env":
        out = sorted(
            {n for s in chosen for n in s.list("geki-credentials") + s.list("geki-settings")}
        )
    else:
        print(__doc__)
        return 2
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
