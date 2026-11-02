"""Run the agent tasks of the skills with a vanilla Pi against the mocks.

    python ci/agent_test.py [--skill NAME ...] [--runs 3] [--min-pass 2]

For every task in `skills/<name>/tests/tasks/*.yaml` the script starts the mock
of the skill (fixtures, and Prism when `MOCK_UPSTREAM_<TOOL>` is set), installs
the skill like a user would (copied to `~/.agents/skills` of an empty home), and
runs `pi -p` with the task prompt. A run passes when the requests that the mock
saw match the task: every `expect.requests` entry has a match, no `forbidden`
entry has one, the spec mock saw no violation, and the answer holds every
`answer_contains` text. A task passes with `--min-pass` of `--runs` runs.

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
from common import ROOT, TEST_ENV, Skill, load_skills
from mockserver import Mock

DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_BASE_URL = "https://api.geki.ai/v1"


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
        os.environ.get("AGENT_TEST_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions",
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
    upstreams = os.environ.get(f"MOCK_UPSTREAM_{skill.tool.upper()}", "").split(";")
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
            env.update(TEST_ENV[skill.tool](url))
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--skill", action="append", default=[])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--min-pass", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if not os.environ.get("GEKI_API_KEY"):
        print("GEKI_API_KEY is not set: skipping the agent tests")
        return 0
    model = os.environ.get("AGENT_TEST_MODEL", DEFAULT_MODEL)
    base_url = os.environ.get("AGENT_TEST_BASE_URL", DEFAULT_BASE_URL)
    reports = []
    for skill in load_skills():
        if args.skill and skill.name not in args.skill:
            continue
        for path in sorted((skill.path / "tests" / "tasks").glob("*.yaml")):
            task = yaml.safe_load(path.read_text(encoding="utf-8"))
            report = run_task(skill, task, args.runs, args.min_pass, model, base_url, args.timeout)
            reports.append(report)
            mark = "pass" if report["passed"] else "FAIL"
            print(
                f"{mark} {skill.name}/{task['name']}: {sum(r['passed'] for r in report['runs'])}/{len(report['runs'])}"
            )
            if not report["passed"]:
                for index, run in enumerate(report["runs"], 1):
                    for problem in run["problems"]:
                        print(f"  run {index}: {problem}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = ["| Skill | Task | Result |", "| --- | --- | --- |"]
        lines += [
            f"| {r['skill']} | {r['task']} | {'pass' if r['passed'] else 'FAIL'} ({sum(x['passed'] for x in r['runs'])}/{len(r['runs'])}) |"
            for r in reports
        ]
        Path(summary).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / ".cache").mkdir(exist_ok=True)
    (ROOT / ".cache" / "agent-report.json").write_text(
        json.dumps(reports, indent=2), encoding="utf-8"
    )
    return 0 if all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
