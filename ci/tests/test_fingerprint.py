import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fingerprint  # noqa: E402
from common import ROOT, SKILLS, Skill, load_skills, mock_env  # noqa: E402


@pytest.fixture
def copy(tmp_path, monkeypatch):
    """A copy of one skill, with the specs out of the way."""
    (tmp_path / "skills").mkdir()
    shutil.copytree(SKILLS / "zammad-support", tmp_path / "skills" / "zammad-support")
    monkeypatch.setattr(fingerprint, "specs_of", lambda skill: "[]")
    return tmp_path / "skills" / "zammad-support"


def value(folder: Path) -> str:
    return fingerprint.skill_hash(Skill(folder))


def test_the_hash_is_stable(copy):
    assert value(copy) == value(copy)


@pytest.mark.parametrize(
    "name",
    [
        "SKILL.md",
        "scripts/zammad.py",
        "assets/logo.svg",
        "references/setup.md",
        "tests/env.json",
        "tests/fixtures/routes.json",
        "tests/test_zammad_support.py",
        "tests/tasks/close-ticket.yaml",
    ],
)
def test_a_file_of_the_skill_changes_the_hash(copy, name):
    before = value(copy)
    path = copy / name
    assert path.exists(), name
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert value(copy) != before


def test_a_new_file_changes_the_hash(copy):
    before = value(copy)
    (copy / "references" / "more.md").write_text("more", encoding="utf-8")
    assert value(copy) != before


def test_readme_and_changelog_do_not_change_the_hash(copy):
    before = value(copy)
    (copy / "README.md").write_text("changed", encoding="utf-8")
    (copy / "CHANGELOG.md").write_text("changed", encoding="utf-8")
    assert value(copy) == before


def test_the_folder_location_does_not_change_the_hash(copy, tmp_path):
    other = tmp_path / "other" / "zammad-support"
    shutil.copytree(copy, other)
    assert value(other) == value(copy)


def test_the_model_and_tool_versions_do_not_change_the_hash(copy, monkeypatch):
    before = value(copy)
    monkeypatch.setenv("AGENT_TEST_MODEL", "other-model")
    monkeypatch.setenv("AGENT_TEST_BASE_URL", "https://other.example")
    monkeypatch.setenv("AGENT_JUDGE_MODEL", "other-judge")
    monkeypatch.setenv("PI_VERSION", "0.0.1")
    monkeypatch.setenv("PRISM_VERSION", "0.0.1")
    assert value(copy) == before


def test_only_the_files_of_a_skill_are_read(copy, monkeypatch):
    """The hash must not depend on anything outside the skill folder and its spec entries."""
    outside = []
    real = Path.read_bytes
    folder = copy.resolve()

    def recording(path):
        if not path.resolve().is_relative_to(folder):
            outside.append(path)
        return real(path)

    monkeypatch.setattr(Path, "read_bytes", recording)
    value(copy)
    assert outside == []


def test_the_own_spec_entries_change_the_hash(monkeypatch):
    specs = [{"skills": ["a"], "url": "https://example.com/1"}]
    monkeypatch.setattr(fingerprint, "specs_for", lambda skill: specs)
    before = fingerprint.specs_of("a")
    specs[0]["url"] = "https://example.com/2"
    assert fingerprint.specs_of("a") != before


def test_another_skill_on_the_same_spec_does_not_change_the_hash(monkeypatch):
    entry = {"url": "https://example.com/1", "prefix": ""}
    monkeypatch.setattr(fingerprint, "specs_for", lambda s: [{"skills": ["a"], **entry}])
    before = fingerprint.specs_of("a")
    monkeypatch.setattr(fingerprint, "specs_for", lambda s: [{"skills": ["a", "b"], **entry}])
    assert fingerprint.specs_of("a") == before


def test_the_order_of_the_spec_entries_does_not_change_the_hash(monkeypatch):
    one, two = {"skills": ["a"], "url": "1"}, {"skills": ["a"], "url": "2"}
    monkeypatch.setattr(fingerprint, "specs_for", lambda s: [one, two])
    before = fingerprint.specs_of("a")
    monkeypatch.setattr(fingerprint, "specs_for", lambda s: [two, one])
    assert fingerprint.specs_of("a") == before


def test_specs_of_a_skill_are_its_own_entries():
    assert json.loads(json.loads(fingerprint.specs_of("github"))[0])["prefix"] == ""
    assert fingerprint.specs_of("zammad-support") == "[]"


def test_a_change_outside_the_skills_keeps_every_fingerprint(tmp_path):
    """The promise of the fingerprint, on a copy of the repo: change CI, nothing is tested."""
    repo = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(".git", ".cache", ".venv", "__pycache__", ".*_cache"),
    )

    def fingerprints():
        out = subprocess.run(
            [sys.executable, "ci/fingerprint.py"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return out

    before = fingerprints()
    assert before
    for name in ("ci/mocks.py", "ci/agent_test.py", "conftest.py", "pyproject.toml", "ci/pins.env"):
        path = repo / name
        path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert fingerprints() == before


def test_every_skill_has_test_variables_with_the_mock_address():
    for skill in load_skills():
        env = mock_env(skill.path, "http://mock.example")
        assert any("http://mock.example" in value for value in env.values()), skill.name


def test_settings_use_defaults_for_empty_variables(monkeypatch):
    monkeypatch.setenv("AGENT_TEST_MODEL", "")
    monkeypatch.setenv("AGENT_TEST_BASE_URL", "")
    config = fingerprint.settings()
    assert config["model"] == fingerprint.DEFAULT_MODEL
    assert config["base_url"] == fingerprint.DEFAULT_BASE_URL
    monkeypatch.setenv("AGENT_TEST_MODEL", "x-model")
    assert fingerprint.settings()["model"] == "x-model"
