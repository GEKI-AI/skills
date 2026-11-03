import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import results  # noqa: E402

NAMES = ["a", "b", "c", "d"]
HASH = {n: f"h-{n}" for n in NAMES}


def green(name, date, hash_=None):
    return {
        "skill": name,
        "status": "green",
        "hash": hash_ or HASH[name],
        "date": date,
        "run_url": f"run-{name}",
        "model": "m",
        "script": {"passed": 3},
        "agent": {"tasks": 1, "passed": 1},
    }


STORED = {
    "a": green("a", "2026-11-01T00:00:00Z"),
    "b": green("b", "2026-10-01T00:00:00Z"),
    "c": green("c", "2026-10-20T00:00:00Z", "old-hash"),
}


def test_diff_tests_only_affected_skills_without_a_green_result():
    plan = results.select(NAMES, HASH, STORED, mode="diff", candidates=["a", "c", "d"])
    assert plan.todo == ["c", "d"]
    assert plan.reasons["c"] == "no green result for this fingerprint"
    assert plan.reasons["d"] == "never verified"
    assert list(plan.verified) == ["a"]
    assert plan.left_out == {"b": "not affected by the change"}
    assert plan.fingerprints == {"c": "h-c", "d": "h-d"}


def test_diff_with_nothing_affected_tests_nothing():
    plan = results.select(NAMES, HASH, STORED, mode="diff", candidates=[])
    assert plan.todo == []


def test_a_failed_or_missing_status_is_not_verified():
    stored = {"a": {**STORED["a"], "status": "red"}}
    plan = results.select(["a"], HASH, stored, mode="diff", candidates=["a"])
    assert plan.todo == ["a"]


def test_all_skips_verified_unless_forced():
    plan = results.select(NAMES, HASH, STORED, mode="all")
    assert plan.todo == ["c", "d"]
    forced = results.select(NAMES, HASH, STORED, mode="all", force=True)
    assert forced.todo == NAMES
    assert forced.reasons["a"] == "forced"
    some = results.select(NAMES, HASH, STORED, mode="all", candidates=["a"], force=True)
    assert some.todo == ["a"]


def test_load_dir_ignores_wrong_names_and_broken_files(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(STORED["a"]), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(STORED["a"]), encoding="utf-8")
    (tmp_path / "c.json").write_text("{", encoding="utf-8")
    assert list(results.load_dir(tmp_path)) == ["a"]


@pytest.fixture
def remote(tmp_path, monkeypatch):
    """A bare origin and a clone, with the results module pointed at the clone."""

    def git(*args, cwd):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    origin = tmp_path / "origin.git"
    clone = tmp_path / "clone"
    origin.mkdir()
    git("init", "-q", "--bare", "-b", "main", cwd=origin)
    git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    git("config", "user.email", "t@example.com", cwd=clone)
    git("config", "user.name", "t", cwd=clone)
    (clone / "x.txt").write_text("x", encoding="utf-8")
    git("add", ".", cwd=clone)
    git("commit", "-qm", "init", cwd=clone)
    git("push", "-q", "origin", "main", cwd=clone)
    monkeypatch.setattr(results, "ROOT", clone)
    monkeypatch.setattr(results, "WORK", clone / ".cache" / "results")
    monkeypatch.setenv("RUN_URL", "https://ci.example/run/1")
    return clone


def run_push(tmp_path, records):
    path = tmp_path / "green.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return results.main(["push", str(path)])


def test_push_creates_the_branch_and_later_pushes_keep_other_skills(remote, tmp_path):
    assert run_push(tmp_path, [STORED["a"]]) == 0
    assert list(results.load_ref(results.REF)) == ["a"]
    assert run_push(tmp_path, [STORED["b"]]) == 0
    stored = results.load_ref(results.REF)
    assert sorted(stored) == ["a", "b"]
    assert stored["b"]["hash"] == "h-b"
    files = results.git("ls-tree", "--name-only", results.REF).split()
    assert "TESTED.md" in files and "README.md" in files
    log = results.git("log", "--format=%an %ae %s", results.REF)
    assert "geki-skills CI noreply@geki.ai" in log


def test_push_of_the_same_result_changes_nothing(remote, tmp_path, capsys):
    run_push(tmp_path, [STORED["a"]])
    before = results.git("rev-parse", results.REF).strip()
    run_push(tmp_path, [STORED["a"]])
    assert results.git("rev-parse", results.REF).strip() == before
    assert "nothing to save" in capsys.readouterr().out


def test_push_failure_is_a_warning(remote, tmp_path, capsys):
    results.git("remote", "set-url", "origin", str(tmp_path / "missing.git"))
    assert run_push(tmp_path, [STORED["a"]]) == 0
    assert "::warning::" in capsys.readouterr().out


def test_push_works_again_after_a_failed_push(remote, tmp_path):
    good = results.git("remote", "get-url", "origin").strip()
    results.git("remote", "set-url", "origin", str(tmp_path / "missing.git"))
    assert run_push(tmp_path, [STORED["a"]]) == 0
    results.git("remote", "set-url", "origin", good)
    assert run_push(tmp_path, [STORED["a"]]) == 0
    assert list(results.load_ref(results.REF)) == ["a"]


def test_verified_command(remote, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(results, "hashes", lambda skills=None: dict(HASH))
    run_push(tmp_path, [STORED["a"]])
    assert results.main(["verified", "a"]) == 0
    assert results.main(["verified", "a", "b"]) == 1
    assert "b: no green test result" in capsys.readouterr().out


def test_plan_command_writes_github_outputs(remote, tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr(results, "load_skills", lambda: [])
    monkeypatch.setattr(results, "hashes", lambda skills=None: {})
    assert results.main(["plan", "--mode", "all"]) == 0
    text = out.read_text(encoding="utf-8")
    assert "todo=[]" in text and "count=0" in text and "names=" in text
