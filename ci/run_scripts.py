"""Run the script tests of the chosen skills in a clean environment.

    python ci/run_scripts.py --skills a,b [--env empty|image] [--report FILE]

Per tool, in one go: start the Prism mocks of the tool, build the environment the
scripts run in, run pytest once per skill, stop the mocks.

- `empty`: a fresh venv of Python 3.11 with only the packages the skills declare
  (`geki-python`). The scripts run with that interpreter, so an undeclared import
  fails. The tests themselves run with the interpreter that started this script.
- `image`: the Python of the GEKI sandbox image (run this inside the image). The
  image has its libraries preinstalled. Declared packages it lacks are installed,
  as every session start does, and reported as warnings.

The report is JSON: `{skill: {tests, passed, failed, skipped, ok}}`. A skill is ok
when no test failed and at least one test passed: a skill without a passing test
is never green. With `$GITHUB_OUTPUT` set, the report goes there as `report`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from common import ROOT, Skill, load_skills
from fingerprint import EMPTY_PYTHON
from mocks import serve

WORK = ROOT / ".cache" / "scripts"


def make_empty_env(packages: list[str], folder: Path) -> str:
    shutil.rmtree(folder, ignore_errors=True)
    if shutil.which("uv"):
        subprocess.run(["uv", "venv", "--quiet", "--python", EMPTY_PYTHON, str(folder)], check=True)
        python = str(folder / "bin" / "python")
        if packages:
            subprocess.run(
                ["uv", "pip", "install", "--quiet", "--python", python, *packages], check=True
            )
        return python
    base = shutil.which(f"python{EMPTY_PYTHON}") or sys.executable
    subprocess.run([base, "-m", "venv", str(folder)], check=True)
    python = str(folder / "bin" / "python")
    if packages:
        subprocess.run([python, "-m", "pip", "install", "--quiet", *packages], check=True)
    return python


def make_image_env(packages: list[str], folder: Path) -> str:
    """The image Python plus what is missing. Packages the image lacks are reported."""
    shutil.rmtree(folder, ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(folder)], check=True
    )
    python = str(folder / "bin" / "python")
    missing = []
    for package in packages:
        have = subprocess.run(
            [python, "-c", f"import importlib.metadata as m; m.version({package!r})"],
            capture_output=True,
            check=False,
        )
        if have.returncode != 0:
            missing.append(package)
            print(f"::warning::{package} is declared by a skill and is not in the GEKI image")
    if missing:
        subprocess.run([python, "-m", "pip", "install", "--quiet", *missing], check=True)
    return python


def read_junit(path: Path) -> dict:
    counts = {"tests": 0, "failed": 0, "skipped": 0}
    if not path.exists():
        return {**counts, "passed": 0, "ok": False}
    root = ET.parse(path).getroot()
    for suite in root.iter("testsuite"):
        counts["tests"] += int(suite.get("tests", 0))
        counts["failed"] += int(suite.get("failures", 0)) + int(suite.get("errors", 0))
        counts["skipped"] += int(suite.get("skipped", 0))
    passed = counts["tests"] - counts["failed"] - counts["skipped"]
    return {**counts, "passed": passed, "ok": counts["failed"] == 0 and passed > 0}


def run_tool(tool: str, skills: list[Skill], env: str) -> dict[str, dict]:
    packages = sorted({p for s in skills for p in s.list("geki-python")})
    folder = WORK / f"env-{tool}"
    python = (make_image_env if env == "image" else make_empty_env)(packages, folder)
    print(
        f"{tool}: scripts run with {python}, packages: {', '.join(packages) or 'none'}", flush=True
    )
    report: dict[str, dict] = {}
    with serve(tool):
        for skill in skills:
            junit = WORK / f"junit-{skill.name}.xml"
            junit.parent.mkdir(parents=True, exist_ok=True)
            junit.unlink(missing_ok=True)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    f"--junitxml={junit}",
                    f"skills/{skill.name}",
                ],
                cwd=ROOT,
                env={
                    **os.environ,
                    "SKILL_PYTHON": python,
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                check=False,
            )
            report[skill.name] = read_junit(junit)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--skills", default="")
    parser.add_argument("--env", choices=["empty", "image"], default="empty")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    wanted = {n.strip() for n in args.skills.split(",") if n.strip()}
    skills = [s for s in load_skills() if not wanted or s.name in wanted]
    if wanted and len(skills) != len(wanted):
        print(f"unknown skills: {', '.join(sorted(wanted - {s.name for s in skills}))}")
        return 2
    report: dict[str, dict] = {}
    for tool in sorted({s.tool for s in skills}):
        report.update(run_tool(tool, [s for s in skills if s.tool == tool], args.env))
    for name, row in report.items():
        mark = "ok  " if row["ok"] else "FAIL"
        print(
            f"{mark} {name}: {row['passed']} passed, {row['failed']} failed, {row['skipped']} skipped"
        )
    text = json.dumps(report, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"report={text}\n")
    return 0 if all(row["ok"] for row in report.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
