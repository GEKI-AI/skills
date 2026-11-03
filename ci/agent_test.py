"""Run the agent tasks of the skills with a vanilla Pi against the mocks.

    python ci/agent_test.py [--skill NAME ...] [--runs 3] [--min-pass 2] [--report FILE]

For every task in `skills/<name>/tests/tasks/*.yaml` the script starts the mock
of the skill (fixtures, and Prism for skills that have a vendor spec), installs
the skill like a user would (copied to `~/.agents/skills` of an empty home), and
runs `pi -p` with the task prompt. A run passes when the requests that the mock
saw match the task: every `expect.requests` entry has a match, no `forbidden`
entry has one, the spec mock saw no violation, and the answer holds every
`answer_contains` text. A task passes with `--min-pass` of `--runs` runs. It
stops early: after `--min-pass` passes, and after more failures than the task can
afford (two failures of three runs).

Without GEKI_API_KEY nothing can run, and the script fails: a skill is never
green without a test. A skill without tasks fails too.

The report (JSON) is `{skill: {ok, model, tasks: {name: {passed, passes, runs}}}}`.
With `$GITHUB_OUTPUT` set, it goes there as `report`.

Environment: GEKI_API_KEY (the key of the Models preset), AGENT_TEST_MODEL
(default deepseek-v4.1-flash), AGENT_TEST_BASE_URL (default
https://api.geki.ai/v1), PI_BIN (default pi), AGENT_JUDGE_MODEL (optional: a
cheap model that checks `judge:` criteria of a task).

Task file: name, prompt, expect.requests (method, path, query, json),
expect.forbidden (method, path), expect.answer_contains, judge. A value that
starts with `re:` is a regular expression searched in the text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from common import TEST_ENV, Skill, load_skills
from fingerprint import DEFAULT_BASE_URL, DEFAULT_MODEL
from mocks import serve
from mockserver import Mock


def match_value(want: object, have: object) -> bool:
    if isinstance(want, str) and want.startswith("re:"):
        return isinstance(have, str) and re.search(want[3:], have) is not None
    if isinstance(want, dict):
        return isinstance(have, dict) and all(
            k in have and match_value(v, have[k]) for k, v in want.items()
        )
    if isinstance(want, list):
        return isinstance(have, list) and all(any(match_value(w, h) for h in have) for w in want)
    return want == have or (isinstance(have, str) and str(want) == have)


def match_request(rule: dict, request: dict) -> bool:
    methods = rule.get("method")
    if methods:
        allowed = [methods] if isinstance(methods, str) else methods
        if request["method"] not in [m.upper() for m in allowed]:
            return False
    if "path" in rule and not match_value(rule["path"], request["path"]):
        return False
    if "query" in rule and not match_value(rule["query"], request["query"]):
        return False
    return not ("json" in rule and not match_value(rule["json"], request["body"]))


def check(task: dict, requests: list[dict], violations: list, answer: str) -> list[str]:
    problems: list[str] = []
    expect = task.get("expect") or {}
    for rule in expect.get("requests", []):
        if not any(match_request(rule, r) for r in requests):
            problems.append(f"no request matched {json.dumps(rule)}")
    for rule in expect.get("forbidden", []):
        hit = next((r for r in requests if match_request(rule, r)), None)
        if hit:
            problems.append(f"forbidden request {hit['method']} {hit['path']}")
    if violations:
        problems.append(
            f"the spec mock rejected {len(violations)} request(s): {violations[0]['request']}"
        )
    for text in expect.get("answer_contains", []):
        if text.lower() not in answer.lower():
            problems.append(f"the answer does not contain {text!r}")
    return problems


def judge(task: dict, answer: str) -> str | None:
    model = os.environ.get("AGENT_JUDGE_MODEL")
    if not model or "judge" not in task:
        return None
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You check an answer against a criterion. Reply with PASS or FAIL only.",
            },
            {"role": "user", "content": f"Criterion: {task['judge']}\n\nAnswer:\n{answer}"},
        ],
        "max_tokens": 5,
    }
    request = urllib.request.Request(
        (os.environ.get("AGENT_TEST_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['GEKI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        verdict = json.loads(response.read())["choices"][0]["message"]["content"]
    return None if "PASS" in verdict.upper() else f"the judge said: {verdict.strip()[:80]}"


def write_pi_home(home: Path, model: str, base_url: str) -> dict[str, str]:
    agent = home / ".pi" / "agent"
    agent.mkdir(parents=True)
    models = {
        "providers": {
            "geki": {
                "baseUrl": base_url,
                "api": "openai-completions",
                "apiKey": "$GEKI_API_KEY",
                "compat": {"supportsDeveloperRole": False, "supportsReasoningEffort": True},
                "models": [{"id": model, "reasoning": True}],
            }
        }
    }
    (agent / "models.json").write_text(json.dumps(models), encoding="utf-8")
    return {"HOME": str(home), "PI_CODING_AGENT_DIR": str(agent)}


def install_skill(skill: Skill, home: Path) -> None:
    target = home / ".agents" / "skills" / skill.name
    shutil.copytree(skill.path, target, ignore=shutil.ignore_patterns("tests", "__pycache__"))


@dataclass
class Run:
    passed: bool
    problems: list[str]
    answer: str
    requests: list[dict] = field(default_factory=list)


def run_once(skill: Skill, task: dict, model: str, base_url: str, timeout: int) -> Run:
    upstreams = os.environ.get("MOCK_UPSTREAM", "").split(";")
    mock = Mock(skill.path / "tests" / "fixtures" / "routes.json", upstreams)
    url = mock.start()
    try:
        with tempfile.TemporaryDirectory(prefix="geki-agent-") as tmp:
            home = Path(tmp) / "home"
            work = Path(tmp) / "work"
            work.mkdir()
            env = {
                "PATH": os.environ["PATH"],
                "LANG": "C.UTF-8",
                "GEKI_API_KEY": os.environ.get("GEKI_API_KEY", ""),
            }
            env.update(write_pi_home(home, model, base_url))
            env.update(TEST_ENV[skill.name](url))
            install_skill(skill, home)
            command = [
                os.environ.get("PI_BIN", "pi"),
                "-p",
                "--no-session",
                "--no-context-files",
                "--provider",
                "geki",
                "--model",
                model,
                "--thinking",
                "low",
                task["prompt"].strip(),
            ]
            try:
                proc = subprocess.run(
                    command,
                    cwd=work,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                answer, code, err = proc.stdout, proc.returncode, proc.stderr
            except subprocess.TimeoutExpired:
                answer, code, err = "", 124, "timeout"
            except OSError as exc:
                answer, code, err = "", 127, str(exc)
    finally:
        mock.stop()
    problems = check(task, mock.requests, mock.violations, answer)
    if code != 0:
        problems.insert(0, f"pi exited with {code}: {err.strip()[-200:]}")
    elif not problems:
        verdict = judge(task, answer)
        if verdict:
            problems.append(verdict)
    return Run(not problems, problems, answer, mock.requests)


def run_task(
    skill: Skill, task: dict, runs: int, min_pass: int, model: str, base_url: str, timeout: int
) -> dict:
    results: list[Run] = []
    for _ in range(runs):
        results.append(run_once(skill, task, model, base_url, timeout))
        passed = sum(r.passed for r in results)
        failed = len(results) - passed
        if passed >= min_pass or failed > runs - min_pass:
            break
    passed = sum(r.passed for r in results)
    return {
        "skill": skill.name,
        "task": task["name"],
        "passed": passed >= min_pass,
        "runs": [{"passed": r.passed, "problems": r.problems} for r in results],
    }


def skill_report(reports: list[dict], model: str) -> dict:
    """The compact report of one skill from the reports of its tasks."""
    tasks = {
        r["task"]: {
            "passed": r["passed"],
            "passes": sum(x["passed"] for x in r["runs"]),
            "runs": len(r["runs"]),
        }
        for r in reports
    }
    return {
        "ok": bool(tasks) and all(t["passed"] for t in tasks.values()),
        "model": model,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--skill", action="append", default=[])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--min-pass", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not os.environ.get("GEKI_API_KEY"):
        print("GEKI_API_KEY is not set: the agent tests cannot run, so nothing is verified")
        return 2
    model = os.environ.get("AGENT_TEST_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("AGENT_TEST_BASE_URL") or DEFAULT_BASE_URL
    skills = [s for s in load_skills() if not args.skill or s.name in args.skill]
    if args.skill and len(skills) != len(set(args.skill)):
        print(f"unknown skills: {', '.join(sorted(set(args.skill) - {s.name for s in skills}))}")
        return 2
    result: dict[str, dict] = {}
    lines = ["| Skill | Task | Result |", "| --- | --- | --- |"]
    for skill in skills:
        with serve(skill.name):
            reports = []
            paths = sorted((skill.path / "tests" / "tasks").glob("*.yaml"))
            for path in paths:
                task = yaml.safe_load(path.read_text(encoding="utf-8"))
                report = run_task(
                    skill, task, args.runs, args.min_pass, model, base_url, args.timeout
                )
                reports.append(report)
                passes = sum(r["passed"] for r in report["runs"])
                count = f"{passes}/{len(report['runs'])}"
                print(
                    f"{'pass' if report['passed'] else 'FAIL'} {skill.name}/{task['name']}: {count}"
                )
                lines.append(
                    f"| {skill.name} | {task['name']} | {'pass' if report['passed'] else 'FAIL'} ({count}) |"
                )
                if not report["passed"]:
                    for index, run in enumerate(report["runs"], 1):
                        for problem in run["problems"]:
                            print(f"  run {index}: {problem}")
            if not paths:
                print(f"FAIL {skill.name}: no agent tasks, so nothing is verified")
            result[skill.name] = skill_report(reports, model)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    text = json.dumps(result, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"report={text}\n")
    return 0 if all(r["ok"] for r in result.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
