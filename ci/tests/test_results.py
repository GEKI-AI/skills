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
    "a": {"h-a": green("a", "2026-11-01T00:00:00Z")},
    "b": {"h-b": green("b", "2026-10-01T00:00:00Z")},
    "c": {"old-hash": green("c", "2026-10-20T00:00:00Z", "old-hash")},
}


A = STORED["a"]["h-a"]


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
    stored = {"a": {"h-a": {**STORED["a"]["h-a"], "status": "red"}}}
    plan = results.select(["a"], HASH, stored, mode="diff", candidates=["a"])
    assert plan.todo == ["a"]


def test_the_current_fingerprint_counts_even_when_another_is_newer():
    stored = {
        "a": {
            "h-a": green("a", "2026-10-01T00:00:00Z"),
            "other": green("a", "2026-11-01T00:00:00Z", "other"),
        }
    }
    plan = results.select(["a"], HASH, stored, mode="diff", candidates=["a"])
    assert plan.todo == []
    assert plan.verified["a"]["hash"] == "h-a"


def test_all_skips_verified_unless_forced():
    plan = results.select(NAMES, HASH, STORED, mode="all")
    assert plan.todo == ["c", "d"]
    forced = results.select(NAMES, HASH, STORED, mode="all", force=True)
    assert forced.todo == NAMES
    assert forced.reasons["a"] == "forced"
    some = results.select(NAMES, HASH, STORED, mode="all", candidates=["a"], force=True)
    assert some.todo == ["a"]


def test_load_dir_ignores_wrong_names_and_broken_files(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(STORED["a"]["h-a"]), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(STORED["a"]["h-a"]), encoding="utf-8")
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
    assert run_push(tmp_path, [A]) == 0
    assert list(results.load_ref(results.REF)) == ["a"]
    assert run_push(tmp_path, [STORED["b"]["h-b"]]) == 0
    stored = results.load_ref(results.REF)
    assert sorted(stored) == ["a", "b"]
    assert stored["b"]["h-b"]["hash"] == "h-b"
    assert "a/h-a.json" in results.git("ls-tree", "-r", "--name-only", results.REF).split()
    files = results.git("ls-tree", "--name-only", results.REF).split()
    assert "TESTED.md" in files and "README.md" in files
    log = results.git("log", "--format=%an %ae %s", results.REF)
    assert "geki-skills CI noreply@geki.ai" in log


def test_a_result_of_another_fingerprint_does_not_replace_a_result(remote, tmp_path):
    run_push(tmp_path, [A])
    run_push(tmp_path, [green("a", "2026-11-02T00:00:00Z", "from-a-branch")])
    stored = results.load_ref(results.REF)
    assert sorted(stored["a"]) == ["from-a-branch", "h-a"]
    assert results.is_verified("a", {"a": "h-a"}, stored)
    assert results.is_verified("a", {"a": "from-a-branch"}, stored)


def test_two_runs_that_push_at_once_keep_both_results(remote, tmp_path, monkeypatch):
    run_push(tmp_path, [A])
    real_git = results.git
    pushed = []

    def git_with_another_run_first(*args, **kwargs):
        if args[0] == "push" and not pushed:
            pushed.append(True)
            other = tmp_path / "other"
            url = real_git("remote", "get-url", "origin").strip()
            real_git("clone", "-q", "-b", results.BRANCH, url, str(other))
            (other / "b").mkdir()
            (other / "b" / "h-b.json").write_text(json.dumps(STORED["b"]["h-b"]), encoding="utf-8")
            real_git("add", "-A", cwd=other)
            real_git(*results.COMMITTER, "commit", "-qm", "other run", cwd=other)
            real_git("push", "-q", "origin", results.BRANCH, cwd=other)
        return real_git(*args, **kwargs)

    monkeypatch.setattr(results, "git", git_with_another_run_first)
    assert run_push(tmp_path, [green("a", "2026-11-02T00:00:00Z", "second")]) == 0
    results.fetch_results()
    stored = results.load_ref(results.REF)
    assert sorted(stored["a"]) == ["h-a", "second"]
    assert list(stored["b"]) == ["h-b"]


def test_old_results_are_removed_but_never_the_new_one(remote, tmp_path, monkeypatch):
    monkeypatch.setattr(results, "KEEP_PER_SKILL", 2)
    run_push(tmp_path, [green("a", "2026-11-03T00:00:00Z", "newest")])
    run_push(tmp_path, [green("a", "2026-11-02T00:00:00Z", "middle")])
    run_push(tmp_path, [green("a", "2026-11-01T00:00:00Z", "pushed-last")])
    assert sorted(results.load_ref(results.REF)["a"]) == ["newest", "pushed-last"]


def test_the_old_layout_is_ignored_and_removed(remote, tmp_path):
    run_push(tmp_path, [A])
    other = tmp_path / "other"
    url = results.git("remote", "get-url", "origin").strip()
    results.git("clone", "-q", "-b", results.BRANCH, url, str(other))
    (other / "b.json").write_text(json.dumps(STORED["b"]["h-b"]), encoding="utf-8")
    results.git("add", "-A", cwd=other)
    results.git(*results.COMMITTER, "commit", "-qm", "old layout", cwd=other)
    results.git("push", "-q", "origin", results.BRANCH, cwd=other)
    results.fetch_results()
    assert list(results.load_ref(results.REF)) == ["a"]
    run_push(tmp_path, [green("a", "2026-11-02T00:00:00Z", "second")])
    assert "b.json" not in results.git("ls-tree", "--name-only", results.REF).split()


def test_tested_table_shows_the_newest_result():
    table = results.tested_table(
        {
            "a": {
                "old": green("a", "2026-10-01T00:00:00Z", "old"),
                "new": green("a", "2026-11-01T00:00:00Z", "new"),
            }
        }
    )
    assert "2026-11-01" in table and "2026-10-01" not in table


def test_export_prefers_the_result_of_the_current_files(remote, tmp_path, monkeypatch):
    monkeypatch.setattr(results, "hashes", lambda skills=None: dict(HASH))
    run_push(tmp_path, [A])
    run_push(tmp_path, [green("a", "2026-11-02T00:00:00Z", "from-a-branch")])
    run_push(tmp_path, [green("b", "2026-11-03T00:00:00Z", "only-other")])
    out = tmp_path / "export"
    assert results.main(["export", str(out)]) == 0
    exported = results.load_dir(out)
    assert exported["a"]["hash"] == "h-a"
    assert exported["b"]["hash"] == "only-other"


def test_push_of_the_same_result_changes_nothing(remote, tmp_path, capsys):
    run_push(tmp_path, [A])
    before = results.git("rev-parse", results.REF).strip()
    run_push(tmp_path, [A])
    assert results.git("rev-parse", results.REF).strip() == before
    assert "nothing to save" in capsys.readouterr().out


def test_push_failure_is_a_warning(remote, tmp_path, capsys):
    results.git("remote", "set-url", "origin", str(tmp_path / "missing.git"))
    assert run_push(tmp_path, [A]) == 0
    assert "::warning::" in capsys.readouterr().out


def test_push_works_again_after_a_failed_push(remote, tmp_path):
    good = results.git("remote", "get-url", "origin").strip()
    results.git("remote", "set-url", "origin", str(tmp_path / "missing.git"))
    assert run_push(tmp_path, [A]) == 0
    results.git("remote", "set-url", "origin", good)
    assert run_push(tmp_path, [A]) == 0
    assert list(results.load_ref(results.REF)) == ["a"]


def test_verified_command(remote, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(results, "hashes", lambda skills=None: dict(HASH))
    run_push(tmp_path, [A])
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
