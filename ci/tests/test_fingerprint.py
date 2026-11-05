import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fingerprint  # noqa: E402
from common import ROOT, SKILLS, Skill  # noqa: E402


@pytest.fixture
def copy(tmp_path, monkeypatch):
    """A copy of one skill, with the module pointed at the copy."""
    (tmp_path / "skills").mkdir()
    shutil.copytree(SKILLS / "zammad-support", tmp_path / "skills" / "zammad-support")
    monkeypatch.setattr(fingerprint, "RUNNER_FILES", [])
    monkeypatch.setattr(fingerprint, "specs_of", lambda skill: "[]")
    return tmp_path


def value(root: Path, **config) -> str:
    base = {"pi": "1", "prism": "1", "python": "3.11", "model": "m", "base_url": "u", "judge": ""}
    return fingerprint.skill_hash(Skill(root / "skills" / "zammad-support"), {**base, **config})


def test_the_hash_is_stable(copy):
    assert value(copy) == value(copy)


def test_a_script_fixture_or_test_change_changes_the_hash(copy):
    before = value(copy)
    script = copy / "skills" / "zammad-support" / "scripts" / "zammad.py"
    script.write_text(script.read_text(encoding="utf-8") + "\n# x\n", encoding="utf-8")
    assert value(copy) != before


def test_readme_and_changelog_do_not_change_the_hash(copy):
    before = value(copy)
    folder = copy / "skills" / "zammad-support"
    (folder / "README.md").write_text("changed", encoding="utf-8")
    (folder / "CHANGELOG.md").write_text("changed", encoding="utf-8")
    assert value(copy) == before


def test_the_logo_changes_the_hash(copy):
    before = value(copy)
    (copy / "skills" / "zammad-support" / "assets" / "logo.svg").write_text(
        "<svg/>", encoding="utf-8"
    )
    assert value(copy) != before


def test_specs_pins_and_models_change_the_hash(copy, monkeypatch):
    before = value(copy)
    assert value(copy, model="other") != before
    assert value(copy, pi="2") != before
    assert value(copy, prism="2") != before
    assert value(copy, judge="j") != before
    assert value(copy, base_url="v") != before
    monkeypatch.setattr(fingerprint, "specs_of", lambda skill: '[{"url": "x"}]')
    assert value(copy) != before


def test_runner_code_changes_the_hash(copy, monkeypatch):
    runner = copy / "runner.py"
    runner.write_text("a", encoding="utf-8")
    monkeypatch.setattr(fingerprint, "RUNNER_FILES", ["runner.py"])
    monkeypatch.setattr(fingerprint, "ROOT", copy)
    before = value(copy)
    runner.write_text("b", encoding="utf-8")
    assert value(copy) != before


def test_specs_of_a_skill_are_its_own_entries():
    assert json.loads(fingerprint.specs_of("github"))[0]["skills"] == ["github"]
    assert fingerprint.specs_of("zammad-support") == "[]"


def test_every_runner_file_exists():
    for name in fingerprint.RUNNER_FILES:
        assert (ROOT / name).exists(), name


def test_settings_use_defaults_for_empty_variables(monkeypatch):
    monkeypatch.setenv("AGENT_TEST_MODEL", "")
    monkeypatch.setenv("AGENT_TEST_BASE_URL", "")
    config = fingerprint.settings()
    assert config["model"] == fingerprint.DEFAULT_MODEL
    assert config["base_url"] == fingerprint.DEFAULT_BASE_URL
    monkeypatch.setenv("AGENT_TEST_MODEL", "x-model")
    assert fingerprint.settings()["model"] == "x-model"
