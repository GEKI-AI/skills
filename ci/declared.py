"""Print facts about the skills of one tool for the workflows.

    python ci/declared.py names TOOL      skill names
    python ci/declared.py paths TOOL      skill folders
    python ci/declared.py packages TOOL   declared Python packages
    python ci/declared.py env TOOL        variable names (secrets and settings)
    python ci/declared.py tools           tool ids

TOOL `*` means all tools.
"""

from __future__ import annotations

import sys

from common import load_skills


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 2
    skills = load_skills()
    if argv[0] == "tools":
        print("\n".join(sorted({s.tool for s in skills})))
        return 0
    tool = argv[1]
    chosen = [s for s in skills if tool in ("*", s.tool)]
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
