import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ROOT, load_skills  # noqa: E402
from fake_llm import FakeLLM  # noqa: E402

PI = os.environ.get("PI_BIN") or shutil.which("pi")


@pytest.mark.skipif(not PI, reason="pi is not installed")
def test_pi_install_finds_every_skill(tmp_path):
    """`pi install <repo>` in an empty home makes Pi list every skill of the repo."""
    home = tmp_path / "home"
    agent = home / ".pi" / "agent"
    agent.mkdir(parents=True)
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "PI_CODING_AGENT_DIR": str(agent)}
    installed = subprocess.run(
        [PI, "install", str(ROOT)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr

    fake = FakeLLM([{"text": "ok"}])
    base_url = fake.start()
    models = {
        "providers": {
            "geki": {
                "baseUrl": base_url,
                "api": "openai-completions",
                "apiKey": "x",
                "models": [{"id": "m"}],
            }
        }
    }
    (agent / "models.json").write_text(json.dumps(models), encoding="utf-8")
    try:
        ran = subprocess.run(
            [PI, "-p", "--no-session", "--provider", "geki", "--model", "m", "hi"],
            env=env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    finally:
        fake.stop()
    assert ran.returncode == 0, ran.stderr
    prompt = json.dumps(fake.requests[0]["messages"])
    missing = [
        s.name
        for s in load_skills()
        if f"<name>{s.name}</name>" not in prompt and s.name not in prompt
    ]
    assert not missing
