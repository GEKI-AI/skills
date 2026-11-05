import io
import json
import shutil
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


VERSION = f'version: "{Skill(SKILLS / "confluence").version}"'


def broken(tmp_path: Path, old: str, new: str) -> list[str]:
    target = tmp_path / "confluence"
    shutil.copytree(SKILLS / "confluence", target)
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
        (VERSION, "version: 1", "must be a string"),
        (VERSION, 'version: "0"', "version must be an integer"),
        ("geki-category: knowledge", "geki-category: nonsense", "geki-category must be"),
        (
            "  geki-tags: confluence, wiki, atlassian\n",
            "  geki-tags: confluence, wiki, atlassian\n  geki-unknown: x\n",
            "not in the convention",
        ),
        ("geki-tags: confluence, wiki, atlassian", "geki-tags: ", "needs at least one tag"),
        ("geki-tags: confluence, wiki, atlassian", "geki-tags: Confluence", "geki-tags entry"),
        ("geki-tags: confluence, wiki, atlassian", "geki-tags: wiki page", "geki-tags entry"),
        ("license: Apache-2.0", "license: Proprietary", "license must be one of"),
        ("name: confluence", "name: other-name", "name must equal the folder name"),
    ],
)
def test_validator_rejects(tmp_path, old, new, expected):
    assert any(expected in e for e in broken(tmp_path, old, new)), broken(tmp_path, old, new)


def test_script_cannot_import_an_undeclared_package(tmp_path):
    target = tmp_path / "confluence"
    shutil.copytree(SKILLS / "confluence", target)
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


def test_zipped_skill_md_gets_the_test_date_only():
    skill = next(s for s in load_skills() if s.name == "github")
    archive = zipfile.ZipFile(io.BytesIO(publish.build_zip(skill, "2026-11-02T03:17:00Z")))
    text = archive.read("github/SKILL.md").decode("utf-8")
    added = '  geki-tested: "2026-11-02"\n'
    assert added in text
    assert text.replace(added, "") == skill.text


def test_tags_come_from_the_metadata():
    skill = next(s for s in load_skills() if s.name == "github")
    assert json.loads(publish.tags_for(skill)) == ["github", "issues", "pull-requests"]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, "tests/env.json must exist"),
        ("{", "tests/env.json must exist"),
        ('{"A_URL": 1}', "must map variable names to strings"),
        ('{"A_URL": "http://example.com"}', "needs a variable with {mock_url}"),
    ],
)
def test_validator_checks_the_test_variables(tmp_path, content, expected):
    target = tmp_path / "skills" / "github"
    shutil.copytree(SKILLS / "github", target)
    env = target / "tests" / "env.json"
    if content is None:
        env.unlink()
    else:
        env.write_text(content, encoding="utf-8")
    errors: list[str] = []
    validate.check_files(Skill(target), errors)
    assert any(expected in error for error in errors), errors


def test_validator_checks_the_logo(tmp_path):
    target = tmp_path / "github"
    shutil.copytree(SKILLS / "github", target)
    logo = target / "assets" / "logo.svg"
    for text, expected in [
        ("<svg", "not valid XML"),
        ("<html/>", "root is not svg"),
        ('<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', "script"),
        ("<svg>" + " " * 70_000 + "</svg>", "larger than 64 KB"),
    ]:
        logo.write_text(text, encoding="utf-8")
        errors: list[str] = []
        validate.check_logo(Skill(target), errors)
        assert any(expected in e for e in errors), (text[:20], errors)
    logo.unlink()
    errors = []
    validate.check_logo(Skill(target), errors)
    assert errors == []


class FakeApi:
    def __init__(self, rows, page=100):
        self.rows = rows
        self.page = page
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
                query = parse_qs(urlparse(self.path).query)
                rows = outer.rows
                if "after" in query:
                    ids = [r["id"] for r in rows]
                    rows = rows[ids.index(query["after"][0]) + 1 :]
                chunk = rows[: outer.page]
                self.respond(
                    {
                        "data": chunk,
                        "has_more": len(rows) > outer.page,
                        "last_id": chunk[-1]["id"] if chunk else None,
                    }
                )

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
    api = FakeApi(
        [{"id": "sk_1", "name": "hubspot", "meta": {"version": None}, "shared_with": "all"}]
    )
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
    api = FakeApi([{"id": "sk_1", "name": "hubspot", "meta": {"version": skill.version}}])
    try:
        message = publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert "skip" in message
    assert [c[0] for c in api.calls] == ["GET"]


def test_publish_shares_a_skill_that_exists_but_is_not_shared():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    api = FakeApi(
        [{"id": "sk_1", "name": "hubspot", "meta": {"version": None}, "shared_with": "none"}]
    )
    try:
        publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert b'name="shared_with"\r\n\r\nall' in api.calls[-1][2]


def test_publish_finds_the_skill_on_a_later_page():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    rows = [{"id": f"sk_{i}", "name": f"other-{i}", "meta": {"version": 1}} for i in range(5)]
    rows.append({"id": "sk_h", "name": "hubspot", "meta": {"version": skill.version}})
    api = FakeApi(rows, page=2)
    try:
        message = publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert "skip" in message
    gets = [c[1] for c in api.calls if c[0] == "GET"]
    assert len(gets) == 3 and "after=sk_1" in gets[1]


def test_only_catalog_skills_that_left_the_repo_are_hidden():
    rows = [
        {"id": "1", "name": "kept", "shared_with": "all", "deprecated": False},
        {"id": "2", "name": "gone", "shared_with": "all", "deprecated": False},
        {"id": "3", "name": "hidden", "shared_with": "all", "deprecated": True},
        {"id": "4", "name": "internal", "shared_with": "none", "deprecated": False},
    ]
    assert [r["name"] for r in publish.removed_from_repo(rows, {"kept"})] == ["gone"]


def test_an_empty_repo_hides_nothing():
    rows = [{"id": "1", "name": "a", "shared_with": "all", "deprecated": False}]
    with pytest.raises(SystemExit, match="nothing was hidden"):
        publish.removed_from_repo(rows, set())


def test_hiding_adds_a_version_without_files_and_never_overwrites():
    api = FakeApi([])
    try:
        publish.Api(api.url, "key-1").set_deprecated("sk_1", True)
    finally:
        api.stop()
    method, path, body, _auth = api.calls[-1]
    assert (method, path) == ("POST", "/v1/skills/sk_1")
    assert b'name="mode"\r\n\r\nnew_version' in body
    assert b'name="deprecated"\r\n\r\ntrue' in body
    assert b'name="files"' not in body


def test_own_skills_reads_every_page():
    rows = [{"id": f"sk_{n}", "name": f"s{n}"} for n in range(5)]
    api = FakeApi(rows, page=2)
    try:
        found = publish.Api(api.url, "key-1").own_skills()
    finally:
        api.stop()
    assert [r["id"] for r in found] == [r["id"] for r in rows]


def test_a_skill_that_comes_back_with_the_same_version_is_shown_again():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    api = FakeApi(
        [{"id": "sk_1", "name": "hubspot", "deprecated": True, "meta": {"version": skill.version}}]
    )
    try:
        message = publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    assert "shows it again" in message
    _method, path, body, _auth = api.calls[-1]
    assert path == "/v1/skills/sk_1"
    assert b'name="deprecated"\r\n\r\nfalse' in body
    assert b'name="files"' not in body


def test_a_skill_that_comes_back_with_a_new_version_is_shown_again():
    skill = next(s for s in load_skills() if s.name == "hubspot")
    api = FakeApi([{"id": "sk_1", "name": "hubspot", "deprecated": True, "meta": {"version": 0}}])
    try:
        publish.publish_one(publish.Api(api.url, "key-1"), skill)
    finally:
        api.stop()
    body = api.calls[-1][2]
    assert b'name="deprecated"\r\n\r\nfalse' in body
    assert b'name="files"' in body


def run_main(monkeypatch, api, *args):
    monkeypatch.setenv("GEKI_PUBLISH_ENABLED", "1")
    monkeypatch.setenv("GEKI_PUBLISH_KEY", "key-1")
    monkeypatch.setenv("GEKI_API_URL", api.url)
    monkeypatch.setattr(sys, "argv", ["publish.py", *args])
    try:
        return publish.main()
    finally:
        api.stop()


def gone_row():
    return {"id": "sk_gone", "name": "gone", "shared_with": "all", "deprecated": False}


def test_a_publish_run_uploads_first_and_then_hides(monkeypatch, capsys):
    api = FakeApi([gone_row()])
    assert run_main(monkeypatch, api) == 0
    posts = [call[1] for call in api.calls if call[0] == "POST"]
    assert posts[-1] == "/v1/skills/sk_gone"
    assert posts.count("/v1/skills") == len(load_skills())
    assert "gone: not in the repo, hidden in the catalog" in capsys.readouterr().out


def test_a_run_with_only_hides_nothing(monkeypatch):
    api = FakeApi([gone_row()])
    assert run_main(monkeypatch, api, "--only", "hubspot") == 0
    assert "/v1/skills/sk_gone" not in [call[1] for call in api.calls]


def test_a_dry_run_with_a_key_reads_but_sends_nothing(monkeypatch, capsys):
    api = FakeApi([gone_row()])
    assert run_main(monkeypatch, api, "--dry-run") == 0
    assert {call[0] for call in api.calls} == {"GET"}
    assert "gone: not in the repo, would hide it" in capsys.readouterr().out


def test_publish_without_enable_fails_loudly(monkeypatch, capsys):
    monkeypatch.delenv("GEKI_PUBLISH_ENABLED", raising=False)
    monkeypatch.delenv("GEKI_PUBLISH_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["publish.py"])
    assert publish.main() == 1
    assert "PUBLISH_ENABLED" in capsys.readouterr().out


def test_publish_without_a_key_fails_loudly(monkeypatch, capsys):
    monkeypatch.setenv("GEKI_PUBLISH_ENABLED", "1")
    monkeypatch.delenv("GEKI_PUBLISH_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["publish.py"])
    assert publish.main() == 1
    assert "GEKI_PUBLISH_KEY" in capsys.readouterr().out


def test_publish_stops_before_sending_when_a_skill_is_not_verified(monkeypatch, capsys):
    monkeypatch.setenv("GEKI_PUBLISH_ENABLED", "1")
    monkeypatch.setenv("GEKI_PUBLISH_KEY", "key")
    monkeypatch.setattr(
        publish,
        "tested_dates",
        lambda skills, ref: {s.name: "2026-11-02" for s in skills if s.name != "hubspot"},
    )
    sent = []
    monkeypatch.setattr(publish, "publish_one", lambda api, skill, tested: sent.append(skill.name))
    monkeypatch.setattr(sys, "argv", ["publish.py", "--require-verified"])
    assert publish.main() == 1
    assert sent == []
    assert "hubspot" in capsys.readouterr().out


def test_publish_dry_run_prints_without_a_key(monkeypatch, capsys):
    monkeypatch.delenv("GEKI_PUBLISH_ENABLED", raising=False)
    monkeypatch.setattr(sys, "argv", ["publish.py", "--dry-run"])
    assert publish.main() == 0
    out = capsys.readouterr().out
    assert "would create and share with all" in out
