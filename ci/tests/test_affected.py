import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import affected  # noqa: E402

TOOL_OF = {
    "confluence-read": "confluence",
    "confluence-write": "confluence",
    "zammad-read": "zammad",
    "github": "github",
}


def test_a_skill_file_affects_that_skill_only():
    assert affected.affected(["skills/zammad-read/scripts/zammad.py"], TOOL_OF) == ["zammad-read"]
    assert affected.affected(["skills/github/tests/fixtures/routes.json"], TOOL_OF) == ["github"]


def test_a_tool_file_affects_all_skills_of_the_tool():
    assert affected.affected(["tools/confluence/logo.svg"], TOOL_OF) == [
        "confluence-read",
        "confluence-write",
    ]


def test_shared_code_specs_and_workflows_affect_every_skill():
    every = sorted(TOOL_OF)
    for path in [
        "ci/mockserver.py",
        "ci/specs.json",
        "conftest.py",
        ".forgejo/workflows/skills.yml",
        "pyproject.toml",
        "something-new.txt",
    ]:
        assert affected.affected([path], TOOL_OF) == every, path


def test_documentation_affects_nothing():
    docs = ["README.md", "docs/testing.md", ".github/pull_request_template.md", "LICENSE"]
    assert affected.affected(docs, TOOL_OF) == []


def test_a_removed_skill_or_tool_is_ignored():
    assert affected.affected(["skills/gone/SKILL.md", "tools/gone/tool.yaml"], TOOL_OF) == []


def test_mixed_changes_add_up():
    paths = ["README.md", "skills/github/SKILL.md", "skills/zammad-read/SKILL.md"]
    assert affected.affected(paths, TOOL_OF) == ["github", "zammad-read"]


def test_unknown_base_means_every_skill(monkeypatch):
    monkeypatch.setattr(affected, "changed_paths", lambda base: None)
    names, why = affected.affected_since("0000000")
    assert names == sorted(names) and len(names) >= 6
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
