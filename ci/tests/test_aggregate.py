import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aggregate  # noqa: E402


def job(result, **outputs):
    return {"result": result, "outputs": {k: json.dumps(v) for k, v in outputs.items()}}


def plan(todo, verified=None):
    return job(
        "success",
        todo=todo,
        plan={
            "todo": todo,
            "reasons": {n: "changed" for n in todo},
            "verified": verified or {},
            "left_out": {},
            "fingerprints": {n: f"h-{n}" for n in todo},
        },
    )


SCRIPT_OK = {"ok": True, "passed": 5, "failed": 0, "skipped": 1, "tests": 6}
AGENT_OK = {"ok": True, "model": "m", "tasks": {"t": {"passed": True, "passes": 2, "runs": 2}}}


def needs(todo, scripts="success", agents="success", static="success", image="skipped", **rest):
    return {
        "plan": plan(todo),
        "static": job(static),
        "scripts": job(scripts, report={n: SCRIPT_OK for n in todo}),
        "agents": job(agents, report={n: AGENT_OK for n in todo}),
        "geki_image": job(image),
        **rest,
    }


def test_all_green_passes_and_returns_the_records():
    ok, report, green = aggregate.judge(needs(["a", "b"]))
    assert ok
    assert [g["skill"] for g in green] == ["a", "b"]
    assert green[0]["hash"] == "h-a" and green[0]["agent"]["passed"] == 1
    assert report[0].startswith("Skills / tests: PASS")


def test_nothing_to_test_passes_when_the_test_jobs_were_skipped():
    data = {
        "plan": plan([], verified={"a": {"run_url": "run-1", "date": "2026-11-01", "model": "m"}}),
        "static": job("success"),
        "scripts": job("skipped"),
        "agents": job("skipped"),
        "geki_image": job("skipped"),
    }
    ok, report, green = aggregate.judge(data)
    assert ok and green == []
    text = "\n".join(report)
    assert "a: already verified in run run-1" in text


def test_a_failed_static_check_fails():
    ok, report, _ = aggregate.judge(needs(["a"], static="failure"))
    assert not ok and "static checks: failure" in "\n".join(report)


def test_a_missing_model_key_fails_even_when_scripts_pass():
    data = needs(["a"], agents="failure")
    data["agents"] = {"result": "failure", "outputs": {}}
    ok, report, green = aggregate.judge(data)
    assert not ok and green == []
    assert "agent tests: job failure" in "\n".join(report)


def test_skipped_agents_after_failed_scripts_do_not_pass():
    data = needs(["a"], scripts="failure", agents="skipped")
    data["scripts"] = job("failure", report={"a": {**SCRIPT_OK, "ok": False, "failed": 1}})
    ok, report, green = aggregate.judge(data)
    assert not ok and green == []
    text = "\n".join(report)
    assert "script tests not green" in text
    assert "agent tests: job" not in text


def test_a_skill_missing_from_a_report_is_not_green():
    data = needs(["a", "b"])
    data["agents"] = job("success", report={"a": AGENT_OK})
    ok, _, green = aggregate.judge(data)
    assert not ok
    assert [g["skill"] for g in green] == ["a"]


def test_a_cancelled_job_fails():
    ok, report, _ = aggregate.judge(needs(["a"], agents="cancelled"))
    assert not ok and "agents: cancelled" in "\n".join(report)


def test_the_geki_image_that_did_not_run_is_reported_not_passed():
    ok, report, _ = aggregate.judge(needs(["a"]))
    assert ok
    assert any("GEKI image: NOT RUN" in line for line in report)


def test_failing_geki_image_tests_fail_the_run():
    ok, report, _ = aggregate.judge(needs(["a"], image="failure"))
    assert not ok and "GEKI image tests: failure" in "\n".join(report)


def test_an_agent_report_without_tasks_is_not_green():
    data = needs(["a"])
    data["agents"] = job("success", report={"a": {"ok": False, "model": "m", "tasks": {}}})
    ok, _, green = aggregate.judge(data)
    assert not ok and green == []
