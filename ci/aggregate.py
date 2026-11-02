"""The one check that sums up a CI run: "Skills / tests".

    NEEDS='<json of the needs context>' python ci/aggregate.py [--green FILE]

Reads the results of the other jobs, prints a short report and fails when the run
is not good. A run is good when

- the plan and the static checks succeeded,
- every skill in the plan has green script tests and green agent tests, and
- no job was cancelled.

A job that did not run is only fine when the plan did not ask for it. The GEKI
image tests are the exception: they run only when the variable GEKI_SANDBOX_IMAGE
names an image. When they did not run, the report says so. It is not a pass.

`--green FILE` writes the result records of the skills that are green in both
test jobs. `ci/results.py push` saves them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from results import record_for


def output(needs: dict, job: str, name: str, default: str = "") -> str:
    return str((needs.get(job, {}).get("outputs") or {}).get(name) or default)


def loads(text: str, default):
    try:
        return json.loads(text) if text else default
    except json.JSONDecodeError:
        return default


def judge(needs: dict) -> tuple[bool, list[str], list[dict]]:
    """(ok, report lines, records of the green skills)."""
    lines: list[str] = []
    problems: list[str] = []
    result = {job: str(data.get("result", "")) for job, data in needs.items()}

    plan = loads(output(needs, "plan", "plan"), {})
    todo: list[str] = loads(output(needs, "plan", "todo"), [])
    if result.get("plan") != "success":
        problems.append(f"plan: {result.get('plan') or 'missing'}")
    if result.get("static") != "success":
        problems.append(f"static checks: {result.get('static') or 'missing'}")
    for job in needs:
        if result[job] == "cancelled":
            problems.append(f"{job}: cancelled")

    scripts = loads(output(needs, "scripts", "report"), {})
    agents = loads(output(needs, "agents", "report"), {})
    green: list[dict] = []
    for name in todo:
        script_ok = bool(scripts.get(name, {}).get("ok"))
        agent_ok = bool(agents.get(name, {}).get("ok"))
        if script_ok and agent_ok:
            fingerprint = (plan.get("fingerprints") or {}).get(name, "")
            green.append(record_for(name, fingerprint, scripts[name], agents[name]))
            row = scripts[name]
            tasks = agents[name].get("tasks", {})
            lines.append(
                f"- {name}: verified now. {row['passed']} script tests passed"
                f" ({row['skipped']} skipped), {sum(1 for t in tasks.values() if t['passed'])} of"
                f" {len(tasks)} agent tasks passed (reason: {plan.get('reasons', {}).get(name, '')})"
            )
        else:
            why = []
            if not script_ok:
                why.append("script tests not green")
            if not agent_ok:
                why.append(
                    "agent tests not green"
                    if result.get("agents") != "skipped"
                    else "agent tests did not run"
                )
            problems.append(f"{name}: {', '.join(why)}")
            lines.append(f"- {name}: NOT verified ({', '.join(why)})")

    for job, label in (("scripts", "script tests"), ("agents", "agent tests")):
        state = result.get(job, "missing")
        if (
            todo
            and state != "success"
            and not (job == "agents" and result.get("scripts") != "success")
        ):
            problems.append(f"{label}: job {state}")
        if not todo and state not in ("skipped", "success"):
            problems.append(f"{label}: job {state}")

    for name, row in (plan.get("verified") or {}).items():
        lines.append(
            f"- {name}: already verified in run {row.get('run_url') or '?'}"
            f" on {str(row.get('date', ''))[:10]} with {row.get('model')}"
        )
    for name, why in (plan.get("left_out") or {}).items():
        lines.append(f"- {name}: not tested, {why}")

    image = result.get("geki_image", "skipped")
    if image == "success":
        lines.append("- GEKI image: script tests passed in the sandbox image")
    elif image == "skipped" and todo:
        lines.append(
            "- GEKI image: NOT RUN. GEKI_SANDBOX_IMAGE is not set, there is no Docker image of the"
            " guest image yet. This is not a pass."
        )
    elif image != "skipped":
        problems.append(f"GEKI image tests: {image}")

    head = "FAIL" if problems else "PASS"
    count = f"{len(green)} verified now, {len(plan.get('verified') or {})} already verified"
    report = [f"Skills / tests: {head} ({count})", ""] + lines
    if problems:
        report += ["", "Problems:"] + [f"- {p}" for p in problems]
    return not problems, report, green


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--green", type=Path)
    args = parser.parse_args()
    needs = loads(os.environ.get("NEEDS", ""), {})
    ok, report, green = judge(needs)
    text = "\n".join(report)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    if args.green:
        args.green.parent.mkdir(parents=True, exist_ok=True)
        args.green.write_text(json.dumps(green), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
