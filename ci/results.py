"""Test results by fingerprint, kept on the branch `test-results`.

Each green result is one small JSON file `<skill>/<fingerprint>.json` on that branch.
It holds the fingerprint (`ci/fingerprint.py`), the date, the run, the model and the
pass counts. A skill whose current fingerprint has a green result is "already
verified" and is not tested again.

One file per fingerprint means that branches do not overwrite the results of each
other: a green result on a pull request still counts after a run on another branch.
Only the newest `KEEP_PER_SKILL` results of a skill are kept.

    python ci/results.py plan --mode diff|all [--base REF] [--skills a,b]
                              [--force] [--ref origin/test-results]
    python ci/results.py export DIR [--ref origin/test-results]
    python ci/results.py push GREEN_JSON
    python ci/results.py verified SKILL [SKILL ...] [--ref origin/test-results]

`plan` prints the plan as JSON and writes `todo`, `count` and `plan` to
`$GITHUB_OUTPUT`. `push` commits the results of GREEN_JSON (a list of result
records) and pushes them. A failed push is a warning.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from affected import affected_since
from common import ROOT, load_skills
from fingerprint import hashes, settings

BRANCH = "test-results"
REF = f"origin/{BRANCH}"
WORK = ROOT / ".cache" / "results"
COMMITTER = ["-c", "user.name=geki-skills CI", "-c", "user.email=noreply@geki.ai"]
KEEP_PER_SKILL = 20

Results = dict[str, dict[str, dict]]


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def fetch_results() -> None:
    git("fetch", "--quiet", "origin", f"+refs/heads/{BRANCH}:refs/remotes/{REF}", check=False)


def parse_result(skill: str, fingerprint: str, text: str) -> dict | None:
    """The record in `<skill>/<fingerprint>.json`, or None when it is broken or misplaced."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("skill") == skill and data.get("hash") == fingerprint:
        return data
    return None


def load_ref(ref: str = REF) -> Results:
    """The results on a git ref, by skill and fingerprint. Empty when the ref does not exist yet."""
    if not git("rev-parse", "--verify", "-q", ref, check=False).strip():
        return {}
    out: Results = {}
    for name in git("ls-tree", "-r", "--name-only", ref).splitlines():
        parts = name.split("/")
        if len(parts) != 2 or not parts[1].endswith(".json"):
            continue
        skill, fingerprint = parts[0], parts[1][:-5]
        try:
            data = parse_result(skill, fingerprint, git("show", f"{ref}:{name}"))
        except RuntimeError:
            continue
        if data:
            out.setdefault(skill, {})[fingerprint] = data
    return out


def load_tree(folder: Path) -> Results:
    """The results in a checkout of the results branch."""
    out: Results = {}
    for path in sorted(folder.glob("*/*.json")):
        data = parse_result(path.parent.name, path.stem, path.read_text(encoding="utf-8"))
        if data:
            out.setdefault(path.parent.name, {})[path.stem] = data
    return out


def newest(records: dict[str, dict]) -> dict:
    """The newest of the results of one skill."""
    return max(records.values(), key=lambda r: (str(r.get("date", "")), str(r.get("hash", ""))))


def load_dir(folder: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("skill") == path.stem:
            out[data["skill"]] = data
    return out


def green_result(name: str, current: dict[str, str], results: Results) -> dict | None:
    """The green result of a skill for its current fingerprint."""
    result = results.get(name, {}).get(current.get(name, ""))
    return result if result and result.get("status") == "green" else None


def is_verified(name: str, current: dict[str, str], results: Results) -> bool:
    return green_result(name, current, results) is not None


@dataclass
class Plan:
    todo: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)
    verified: dict[str, dict] = field(default_factory=dict)
    left_out: dict[str, str] = field(default_factory=dict)
    fingerprints: dict[str, str] = field(default_factory=dict)

    def as_json(self) -> dict:
        return {
            "todo": self.todo,
            "reasons": self.reasons,
            "verified": {
                n: {k: r.get(k) for k in ("date", "run_url", "model")}
                for n, r in self.verified.items()
            },
            "left_out": self.left_out,
            "fingerprints": self.fingerprints,
        }


def select(
    names: list[str],
    current: dict[str, str],
    results: Results,
    *,
    mode: str,
    candidates: list[str] | None = None,
    force: bool = False,
) -> Plan:
    """Which skills need a test run.

    `diff`: the candidates (the affected skills) without a green result for their fingerprint.
    `all`: the candidates (all skills by default), without a green result unless `force`.
    """
    plan = Plan()
    wanted = set(names if candidates is None else candidates)
    for name in names:
        if name not in wanted:
            plan.left_out[name] = "not affected by the change"
        elif force and mode == "all":
            plan.todo.append(name)
            plan.reasons[name] = "forced"
        elif verified := green_result(name, current, results):
            plan.verified[name] = verified
        else:
            plan.todo.append(name)
            plan.reasons[name] = (
                "no green result for this fingerprint" if name in results else "never verified"
            )
    plan.todo.sort()
    plan.fingerprints = {name: current[name] for name in plan.todo}
    return plan


def write_outputs(plan: Plan) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"todo={json.dumps(plan.todo)}\n")
        handle.write(f"names={','.join(plan.todo)}\n")
        handle.write(f"count={len(plan.todo)}\n")
        handle.write(f"plan={json.dumps(plan.as_json(), separators=(',', ':'))}\n")


def cmd_plan(args: argparse.Namespace) -> int:
    skills = load_skills()
    names = sorted(s.name for s in skills)
    current = hashes(skills)
    fetch_results()
    results = load_ref(args.ref)
    candidates = None
    if args.skills:
        wanted = {n.strip() for n in args.skills.split(",") if n.strip()}
        unknown = wanted - set(names)
        if unknown:
            print(f"unknown skills: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        candidates = sorted(wanted)
    elif args.mode == "diff":
        candidates, why = affected_since(args.base)
        print(f"affected: {why}", file=sys.stderr)
    plan = select(
        names,
        current,
        results,
        mode=args.mode,
        candidates=candidates,
        force=args.force,
    )
    print(json.dumps(plan.as_json(), indent=2))
    write_outputs(plan)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    folder = Path(args.dir)
    folder.mkdir(parents=True, exist_ok=True)
    current = hashes()
    fetch_results()
    for name, records in load_ref(args.ref).items():
        data = green_result(name, current, {name: records}) or newest(records)
        (folder / f"{name}.json").write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


def cmd_verified(args: argparse.Namespace) -> int:
    """Exit 1 when a skill has no green result for its current fingerprint."""
    current = hashes()
    fetch_results()
    results = load_ref(args.ref)
    missing = [n for n in args.skills if not is_verified(n, current, results)]
    for name in missing:
        print(f"{name}: no green test result for the current files")
    return 1 if missing else 0


def tested_table(results: Results) -> str:
    rows = [
        "| Skill | Verified | Model | Script tests | Agent tasks | Run |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name in sorted(results):
        r = newest(results[name])
        script, agent = r.get("script", {}), r.get("agent", {})
        rows.append(
            f"| {name} | {str(r.get('date', ''))[:10]} | {r.get('model', '')} "
            f"| {script.get('passed', 0)} passed | {agent.get('passed', 0)} of {agent.get('tasks', 0)} "
            f"| {r.get('run_url', '')} |"
        )
    return "\n".join(rows) + "\n"


BRANCH_README = """# Test results

This branch is written by CI. Do not edit it by hand.

Each `<skill>/<fingerprint>.json` is one green test result: the fingerprint, the
date, the model and the pass counts. A skill with a green result for its current
fingerprint is not tested again. `TESTED.md` lists the newest result of each skill.
"""


def prepare_worktree(folder: Path) -> bool:
    """Check out the results branch at `folder`. Returns False when the branch is new."""
    if folder.exists():
        git("worktree", "remove", "--force", str(folder), check=False)
        shutil.rmtree(folder, ignore_errors=True)
    git("worktree", "prune", check=False)
    git("branch", "-D", BRANCH, check=False)
    fetch_results()
    if git("rev-parse", "--verify", "-q", REF, check=False).strip():
        git("worktree", "add", "--quiet", "--detach", str(folder), REF)
        return True
    git("worktree", "add", "--quiet", "--detach", str(folder), "HEAD")
    git("checkout", "--quiet", "--orphan", BRANCH, cwd=folder)
    git("rm", "-rf", "--quiet", ".", cwd=folder, check=False)
    return False


def prune(folder: Path, kept: set[str]) -> None:
    """Remove the oldest results of each skill. A skill that lost one is tested again."""
    for skill, records in load_tree(folder).items():
        by_age = sorted(
            records.values(),
            key=lambda r: (r["hash"] in kept, str(r.get("date", "")), r["hash"]),
            reverse=True,
        )
        for record in by_age[KEEP_PER_SKILL:]:
            (folder / skill / f"{record['hash']}.json").unlink()


def write_results(folder: Path, green: list[dict]) -> None:
    for path in folder.glob("*.json"):  # the old layout, one file per skill
        path.unlink()
    for record in green:
        path = folder / record["skill"] / f"{record['hash']}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prune(folder, {record["hash"] for record in green})
    (folder / "README.md").write_text(BRANCH_README, encoding="utf-8")
    (folder / "TESTED.md").write_text(
        "# Last green results\n\n" + tested_table(load_tree(folder)), encoding="utf-8"
    )


def push_once(green: list[dict], run_url: str) -> None:
    prepare_worktree(WORK)
    write_results(WORK, green)
    git("add", "-A", cwd=WORK)
    if not git("status", "--porcelain", cwd=WORK).strip():
        print("results: nothing to save")
        return
    names = ", ".join(r["skill"] for r in green)
    message = f"chore(results): {names}\n\n{run_url}".strip()
    git(*COMMITTER, "commit", "--quiet", "-m", message, cwd=WORK)
    git("push", "--quiet", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=WORK)
    print(f"results: saved {names}")


def cmd_push(args: argparse.Namespace) -> int:
    green = json.loads(Path(args.green).read_text(encoding="utf-8"))
    if not green:
        print("results: no green skill to save")
        return 0
    run_url = os.environ.get("RUN_URL", "")
    error = ""
    for attempt in range(1, 5):
        try:
            push_once(green, run_url)
            return 0
        except RuntimeError as exc:
            error = str(exc)
            print(f"results: attempt {attempt} failed: {error}", file=sys.stderr)
    print(
        f"::warning::the test results could not be saved to the branch {BRANCH}. "
        f"The next run tests these skills again. {error}"
    )
    return 0


def record_for(name: str, fingerprint: str, script: dict, agent: dict) -> dict:
    """The record that is stored for a skill whose script and agent tests are green."""
    config = settings()
    model = agent.get("model") or config["model"]
    return {
        "skill": name,
        "status": "green",
        "hash": fingerprint,
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_url": os.environ.get("RUN_URL", ""),
        "commit": os.environ.get("COMMIT", ""),
        "model": model,
        "pi_version": config["pi"],
        "script": {
            "passed": script.get("passed", 0),
            "failed": script.get("failed", 0),
            "skipped": script.get("skipped", 0),
        },
        "agent": {
            "tasks": len(agent.get("tasks", {})),
            "passed": sum(1 for t in agent.get("tasks", {}).values() if t.get("passed")),
            "runs": sum(t.get("runs", 0) for t in agent.get("tasks", {}).values()),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--mode", choices=["diff", "all"], required=True)
    plan.add_argument("--base", default="")
    plan.add_argument("--skills", default="")
    plan.add_argument("--force", action="store_true")
    plan.add_argument("--ref", default=REF)
    export = sub.add_parser("export")
    export.add_argument("dir")
    export.add_argument("--ref", default=REF)
    push = sub.add_parser("push")
    push.add_argument("green")
    verified = sub.add_parser("verified")
    verified.add_argument("skills", nargs="+")
    verified.add_argument("--ref", default=REF)
    args = parser.parse_args(argv)
    return {
        "plan": cmd_plan,
        "export": cmd_export,
        "push": cmd_push,
        "verified": cmd_verified,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
