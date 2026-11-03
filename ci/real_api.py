"""Run the read-only real-API tests of the skills.

    python ci/real_api.py [--skills a,b]

Manual and optional. It is not part of `Skills / tests`, of publishing or of the
READMEs. For each skill its variables (secrets and settings) must be in the
environment. A skill with missing variables fails loudly, and so does a failing
real test.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from common import ROOT, load_skills
from run_scripts import WORK, read_junit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--skills", default="")
    args = parser.parse_args()
    wanted = {n.strip() for n in args.skills.split(",") if n.strip()}
    skills = [s for s in load_skills() if not wanted or s.name in wanted]
    if wanted and len(skills) != len(wanted):
        print(f"unknown skills: {', '.join(sorted(wanted - {s.name for s in skills}))}")
        return 2
    failed = False
    WORK.mkdir(parents=True, exist_ok=True)
    for skill in skills:
        names = sorted(skill.list("geki-credentials") + skill.list("geki-settings"))
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            print(f"FAIL {skill.name}: cannot run, missing {', '.join(missing)}")
            failed = True
            continue
        junit = WORK / f"real-{skill.name}.xml"
        junit.unlink(missing_ok=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-m",
                "real_api",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit}",
                f"skills/{skill.name}",
            ],
            cwd=ROOT,
            env={**os.environ, "REAL_API": "1"},
            check=False,
        )
        row = read_junit(junit)
        good = row["failed"] == 0
        print(
            f"{'ok  ' if good else 'FAIL'} {skill.name}: {row['passed']} passed, {row['failed']} failed, {row['skipped']} skipped"
        )
        failed = failed or not good
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
