import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_test import check, match_request, match_value, run_once  # noqa: E402
from common import SKILLS, Skill  # noqa: E402
from fake_llm import FakeLLM  # noqa: E402


def test_match_value():
    assert match_value("a", "a")
    assert match_value("re:^Hel+o", "Hello world")
    assert not match_value("re:^world", "Hello world")
    assert match_value({"a": {"b": 1}}, {"a": {"b": 1, "c": 2}})
    assert not match_value({"a": 1}, {"b": 1})
    assert match_value(["bug"], ["bug", "urgent"])
    assert match_value(42, "42")
    assert match_value({"to": {"id": "301"}}, {"to": {"id": "301"}, "types": []})


def test_match_request():
    request = {"method": "POST", "path": "/x/1", "query": {"a": "1"}, "body": {"title": "T"}}
    assert match_request({"method": "POST", "path": "/x/1"}, request)
    assert match_request(
        {
            "method": ["POST", "PUT"],
            "path": "re:^/x/\\d$",
            "query": {"a": "1"},
            "json": {"title": "T"},
        },
        request,
    )
    assert not match_request({"method": "GET"}, request)
    assert not match_request({"method": "POST", "json": {"title": "other"}}, request)


def test_check_reports_each_problem():
    task = {
        "expect": {
            "requests": [{"method": "GET", "path": "/a"}],
            "forbidden": [{"method": ["DELETE"]}],
            "answer_contains": ["Done"],
        }
    }
    good = [{"method": "GET", "path": "/a", "query": {}, "body": None}]
    assert check(task, good, [], "all done") == []
    bad = [{"method": "DELETE", "path": "/b", "query": {}, "body": None}]
    problems = check(task, bad, [{"request": "GET /z", "detail": ""}], "nope")
    assert len(problems) == 4


PI = os.environ.get("PI_BIN") or shutil.which("pi")


@pytest.mark.skipif(not PI, reason="pi is not installed")
def test_vanilla_pi_discovers_and_runs_a_skill(monkeypatch):
    """Pi finds the skill in ~/.agents/skills and runs its script against the mock."""
    monkeypatch.setenv("PI_BIN", PI)
    monkeypatch.setenv("GEKI_API_KEY", "not-a-real-key")
    skill = Skill(SKILLS / "zammad-read")
    script = "$HOME/.agents/skills/zammad-read/scripts/zammad.py"
    fake = FakeLLM(
        [
            {"tool": "bash", "arguments": {"command": f"python3 {script} search printer"}},
            {"text": "Anna and Ben wrote tickets about the printer."},
        ]
    )
    base_url = fake.start()
    task = {
        "name": "printer",
        "prompt": "Which customers wrote about printers?",
        "expect": {
            "requests": [{"method": "GET", "path": "/api/v1/tickets/search"}],
            "answer_contains": ["Anna"],
        },
    }
    try:
        run = run_once(skill, task, "fake-model", base_url, timeout=120)
    finally:
        fake.stop()
    assert run.passed, run.problems
    first = fake.requests[0]
    prompt = " ".join(str(m.get("content")) for m in first["messages"])
    assert "zammad-read" in prompt
    assert "Search and read tickets" in prompt
    assert "test-token" not in prompt
