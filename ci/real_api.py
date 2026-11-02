"""Run the read-only real-API tests of the skills.

    python ci/real_api.py [--tool TOOL]

Manual and optional. It is not part of `Skills / tests`, of publishing or of the
READMEs. For each tool the variables of its skills (secrets and settings) must be in
the environment. A tool with missing variables fails loudly, and so does a failing
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
    parser.add_argument("--tool", default="")
    args = parser.parse_args()
    skills = [s for s in load_skills() if not args.tool or s.tool == args.tool]
    if not skills:
        print(f"no skills for the tool {args.tool!r}")
        return 2
    failed = False
    WORK.mkdir(parents=True, exist_ok=True)
    for tool in sorted({s.tool for s in skills}):
        chosen = [s for s in skills if s.tool == tool]
        names = sorted(
            {n for s in chosen for n in s.list("geki-credentials") + s.list("geki-settings")}
        )
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            print(f"FAIL {tool}: cannot run, missing {', '.join(missing)}")
            failed = True
            continue
        junit = WORK / f"real-{tool}.xml"
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
                *[f"skills/{s.name}" for s in chosen],
            ],
            cwd=ROOT,
            env={**os.environ, "REAL_API": "1"},
            check=False,
        )
        row = read_junit(junit)
        good = row["failed"] == 0
        print(
            f"{'ok  ' if good else 'FAIL'} {tool}: {row['passed']} passed, {row['failed']} failed, {row['skipped']} skipped"
        )
        failed = failed or not good
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
