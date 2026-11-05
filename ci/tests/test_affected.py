import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import affected  # noqa: E402
from common import SKILLS, SPECS  # noqa: E402

NAMES = ["confluence-read", "confluence-write", "zammad-read", "github"]


def test_a_skill_file_affects_that_skill_only():
    assert affected.affected(["skills/zammad-read/scripts/zammad.py"], NAMES) == ["zammad-read"]
    assert affected.affected(["skills/github/tests/fixtures/routes.json"], NAMES) == ["github"]


def test_changed_specs_affect_the_skills_that_use_them():
    paths = ["ci/specs.json"]
    assert affected.affected(paths, NAMES, ["confluence-read", "confluence-write"]) == [
        "confluence-read",
        "confluence-write",
    ]
    assert affected.affected(paths, NAMES, []) == []


def test_changed_specs_with_unknown_users_affect_every_skill():
    assert affected.affected(["ci/specs.json"], NAMES) == sorted(NAMES)


def test_spec_users_are_the_skills_whose_specs_differ_from_the_base(monkeypatch):
    entries = [e for e in json.loads(SPECS.read_text()) if e["skills"] != ["github"]]
    monkeypatch.setattr(affected, "run", lambda *args, **kwargs: json.dumps(entries))
    assert affected.spec_users("base", ["github", "hubspot", "zammad-read"]) == ["github"]


def test_a_base_without_the_new_spec_format_means_every_skill(monkeypatch):
    monkeypatch.setattr(affected, "run", lambda *args, **kwargs: '{"zammad": []}')
    assert affected.spec_users("base", ["github", "hubspot"]) == ["github", "hubspot"]


def test_shared_code_specs_and_workflows_affect_every_skill():
    every = sorted(NAMES)
    for path in [
        "ci/mockserver.py",
        "conftest.py",
        ".forgejo/workflows/skills.yml",
        "pyproject.toml",
        "something-new.txt",
    ]:
        assert affected.affected([path], NAMES) == every, path


def test_documentation_affects_nothing():
    docs = ["README.md", "docs/testing.md", ".github/pull_request_template.md", "LICENSE"]
    assert affected.affected(docs, NAMES) == []


def test_a_removed_skill_is_ignored():
    assert affected.affected(["skills/gone/SKILL.md"], NAMES) == []


def test_mixed_changes_add_up():
    paths = ["README.md", "skills/github/SKILL.md", "skills/zammad-read/SKILL.md"]
    assert affected.affected(paths, NAMES) == ["github", "zammad-read"]


def test_unknown_base_means_every_skill(monkeypatch):
    monkeypatch.setattr(affected, "changed_paths", lambda base: None)
    names, why = affected.affected_since("0000000")
    assert names == sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))
    assert "unknown" in why


def test_changed_paths_reads_the_diff_from_the_merge_base(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("a")
    git("add", ".")
    git("commit", "-qm", "one")
    git("checkout", "-q", "-b", "feature")
    (tmp_path / "b.txt").write_text("b")
    git("add", ".")
    git("commit", "-qm", "two")
    git("checkout", "-q", "main")
    (tmp_path / "c.txt").write_text("c")
    git("add", ".")
    git("commit", "-qm", "three")
    git("checkout", "-q", "feature")

    def run(*cmd, cwd=None, check=True):
        return subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False).stdout

    monkeypatch.setattr(affected, "run", run)
    assert affected.changed_paths("main") == ["b.txt"]
    assert affected.changed_paths("0" * 40) is None
