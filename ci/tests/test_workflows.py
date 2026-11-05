import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ROOT  # noqa: E402

WORKFLOWS = ROOT / ".forgejo" / "workflows"


def load(name: str) -> dict:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))
    return data


def test_the_workflows_are_for_forgejo_only():
    assert not (ROOT / ".github" / "workflows").exists()
    assert sorted(p.name for p in WORKFLOWS.glob("*.yml")) == [
        "publish.yml",
        "real-api.yml",
        "skills.yml",
    ]
    for path in WORKFLOWS.glob("*.yml"):
        for job in yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"].values():
            assert job["runs-on"] == "datenhof-ci"


def test_every_input_of_a_workflow_has_a_type():
    """Forgejo shows "Invalid input type" in the form when the type is missing."""
    for path in WORKFLOWS.glob("*.yml"):
        inputs = load(path.name)["on"].get("workflow_dispatch", {}).get("inputs", {})
        for name, config in inputs.items():
            assert config.get("type") in {"string", "boolean"}, f"{path.name}: {name}"


def test_the_one_aggregate_check_is_skills_tests():
    data = load("skills.yml")
    assert data["name"] == "Skills"
    assert data["jobs"]["tests"]["name"] == "tests"
    assert data["jobs"]["tests"]["if"] == "${{ always() }}"
    others = set(data["jobs"]) - {"tests"}
    assert set(data["jobs"]["tests"]["needs"]) == others
    for job_id, job in data["jobs"].items():
        assert job_id == "tests" or job["name"] != "tests"


def test_every_job_has_a_timeout():
    for name in ("skills.yml", "publish.yml", "real-api.yml"):
        for job_id, job in load(name)["jobs"].items():
            assert job.get("timeout-minutes"), f"{name}: {job_id}"


def test_the_publish_workflow_runs_only_for_tags_or_by_hand():
    on = load("publish.yml")["on"]
    assert set(on) == {"push", "workflow_dispatch"}
    assert on["push"] == {"tags": ["publish-*"]}


def test_the_agent_job_fails_without_the_key_and_waits_for_the_scripts():
    data = load("skills.yml")["jobs"]["agents"]
    assert "scripts" in data["needs"]
    first = data["steps"][0]
    assert "GEKI_API_KEY" in first["env"]["KEY"]
    assert "exit 1" in first["run"]


def test_workflows_do_not_reinstall_the_runner_toolchains():
    text = "\n".join(p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml"))
    assert not re.search(r"setup-(python|node)", text)
    assert "ubuntu-latest" not in text
    assert "docker run" not in text


def test_every_script_the_workflows_call_exists():
    text = "\n".join(p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml"))
    for name in set(re.findall(r"ci/([a-z_]+\.(?:py|sh))", text)):
        assert (ROOT / "ci" / name).exists(), name
