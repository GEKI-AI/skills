"""Fixtures for the script tests of every skill."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "ci"))

from common import TEST_ENV, Skill  # noqa: E402
from mockserver import Mock  # noqa: E402


@dataclass
class Result:
    code: int
    out: str
    err: str

    @property
    def json(self):
        return json.loads(self.out)

    @property
    def error(self):
        return json.loads(self.err)


def _skill_dir(request: pytest.FixtureRequest) -> Path:
    return Path(str(request.node.fspath)).resolve().parents[1]


def _runner(skill_dir: Path, env: dict[str, str]):
    tool = Skill(skill_dir).tool
    script = next((skill_dir / "scripts").glob(f"{tool}.py"))
    python = os.environ.get("SKILL_PYTHON", sys.executable)

    def run(*args: str, stdin: str | None = None, extra: dict[str, str] | None = None) -> Result:
        full = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", **env, **(extra or {})}
        proc = subprocess.run(
            [python, str(script), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=full,
            timeout=60,
            check=False,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr)

    return run


@pytest.fixture
def mock(request: pytest.FixtureRequest):
    skill_dir = _skill_dir(request)
    tool = Skill(skill_dir).tool
    upstreams = os.environ.get(f"MOCK_UPSTREAM_{tool.upper()}", "").split(";")
    server = Mock(skill_dir / "tests" / "fixtures" / "routes.json", upstreams)
    server.start()
    yield server
    server.stop()
    assert not server.violations, f"the mock spec rejected requests: {server.violations}"


@pytest.fixture
def cli(request: pytest.FixtureRequest, mock: Mock):
    skill_dir = _skill_dir(request)
    return _runner(skill_dir, TEST_ENV[Skill(skill_dir).tool](mock.url))


@pytest.fixture
def real_cli(request: pytest.FixtureRequest):
    """The script against the real API. Needs the variables of the tool in the environment."""
    if os.environ.get("REAL_API") != "1":
        pytest.skip("REAL_API is not 1")
    skill_dir = _skill_dir(request)
    skill = Skill(skill_dir)
    names = skill.list("geki-credentials") + skill.list("geki-settings")
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        pytest.skip(f"missing {', '.join(missing)}")
    return _runner(skill_dir, {n: os.environ[n] for n in names})
