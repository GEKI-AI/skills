import io
import json
import shutil
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog  # noqa: E402
import publish  # noqa: E402
import validate  # noqa: E402
from common import SKILLS, Skill, load_skills  # noqa: E402


def test_repo_passes_the_validator():
    assert validate.main([]) == 0


def test_readmes_are_up_to_date():
    for path, text in catalog.render().items():
        assert path.read_text(encoding="utf-8") == text, f"run python ci/catalog.py: {path}"


def broken(tmp_path: Path, old: str, new: str) -> list[str]:
    target = tmp_path / "confluence-read"
    shutil.copytree(SKILLS / "confluence-read", target)
    skill_md = target / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    errors: list[str] = []
    validate.check_skill(Skill(target), errors)
    return errors


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("geki-hosts: $CONFLUENCE_URL", "geki-hosts: https://x.test", "not a valid host name"),
        (
            "geki-hosts: $CONFLUENCE_URL",
            "geki-hosts: $OTHER_URL",
            "needs OTHER_URL in geki-settings",
        ),
        ("geki-credentials: CONFLUENCE_TOKEN", "geki-credentials: GEKI_TOKEN", "reserved name"),
        (
            "geki-credentials: CONFLUENCE_TOKEN",
            "geki-credentials: 1BAD",
            "not an environment variable name",
        ),
        ("geki-access: read", "geki-access: admin", "geki-access must be"),
        ("geki-auth: company, person-token", "geki-auth: magic", "geki-auth must list"),
        ('version: "1"', "version: 1", "must be a string"),
        ('version: "1"', 'version: "0"', "version must be an integer"),
        ("geki-category: knowledge", "geki-category: nonsense", "geki-category must be"),
        (
            "  geki-tool: confluence\n",
            "  geki-tool: confluence\n  geki-unknown: x\n",
            "not in the convention",
        ),
        ("license: Apache-2.0", "license: Proprietary", "license must be one of"),
        ("name: confluence-read", "name: other-name", "name must equal the folder name"),
    ],
)
def test_validator_rejects(tmp_path, old, new, expected):
    assert any(expected in e for e in broken(tmp_path, old, new)), broken(tmp_path, old, new)


def test_script_cannot_import_an_undeclared_package(tmp_path):
    target = tmp_path / "confluence-read"
    shutil.copytree(SKILLS / "confluence-read", target)
    script = target / "scripts" / "confluence.py"
    script.write_text("import requests\n" + script.read_text(encoding="utf-8"), encoding="utf-8")
    errors: list[str] = []
    validate.check_skill(Skill(target), errors)
    assert any("imports requests" in e for e in errors)


def test_zip_has_one_folder_logo_and_no_tests():
    skill = next(s for s in load_skills() if s.name == "github")
    names = zipfile.ZipFile(io.BytesIO(publish.build_zip(skill))).namelist()
    assert "github/SKILL.md" in names
    assert "github/scripts/github.py" in names
    assert "github/assets/logo.svg" in names
    assert not [n for n in names if "/tests/" in n or n.endswith(".pyc")]
    assert all(n.startswith("github/") for n in names)
    assert publish.build_zip(skill) == publish.build_zip(skill)


class FakeApi:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def respond(self, payload):
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                outer.calls.append(("GET", self.path, None, self.headers.get("Authorization")))
                self.respond({"data": outer.rows})

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.calls.append(("POST", self.path, body, self.headers.get("Authorization")))
                self.respond({"id": "new"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def test_publish_creates_a_new_shared_skill():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    api = FakeApi([])
    try:
        message = publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert "create and share with all" in message
    method, path, body, auth = api.calls[-1]
    assert (method, path, auth) == ("POST", "/v1/skills", "Bearer key-1")
    assert b'name="shared_with"\r\n\r\nall' in body
    assert b'name="name"\r\n\r\nhubspot' in body
    assert b'name="files"; filename="hubspot.zip"' in body
    assert b"mode" not in body.split(b'name="files"')[0]


def test_publish_adds_a_version_and_never_overwrites():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    api = FakeApi([{"id": "sk_1", "name": "hubspot", "version": 0}])
    try:
        message = publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert "new_version" in message
    method, path, body, _ = api.calls[-1]
    assert (method, path) == ("POST", "/v1/skills/sk_1")
    assert b'name="mode"\r\n\r\nnew_version' in body
    assert b"overwrite" not in body
    assert b"shared_with" not in body


def test_publish_skips_a_version_the_platform_has():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    api = FakeApi([{"id": "sk_1", "name": "hubspot", "version": 1}])
    try:
        message = publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert "skip" in message
    assert [c[0] for c in api.calls] == ["GET"]


def test_publish_without_enable_is_a_dry_run(monkeypatch, capsys):
    monkeypatch.delenv("GEKI_PUBLISH_ENABLED", raising=False)
    monkeypatch.setattr(sys, "argv", ["publish.py", "--base", ""])
    assert publish.main() == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "would create and share with all" in out
