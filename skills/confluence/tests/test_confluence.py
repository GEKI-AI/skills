import base64
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "confluence.py"
spec = importlib.util.spec_from_file_location("confluence", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_search_text_builds_cql_and_cleans_results(cli, mock):
    result = cli("search", "--text", "onboarding")
    assert result.code == 0, result.err
    data = result.json
    assert data["results"][0]["title"] == "Onboarding guide"
    assert data["results"][0]["excerpt"].endswith("& meet your buddy.")
    assert data["results"][0]["id"] == "10001"
    sent = mock.requests[0]
    assert sent["path"] == "/wiki/rest/api/search"
    assert sent["query"]["cql"] == 'type = page AND text ~ "onboarding"'


def test_search_cql_is_sent_as_given(cli, mock):
    cql = 'space = DOCS AND title ~ "expense"'
    assert cli("search", "--cql", cql).code == 0
    assert mock.requests[0]["query"]["cql"] == cql


def test_page_is_markdown(cli, mock):
    result = cli("page", "10001")
    assert result.code == 0, result.err
    page = result.json
    assert page["title"] == "Onboarding guide"
    assert page["version"] == 4
    assert page["url"] == "https://acme.atlassian.net/wiki/spaces/DOCS/pages/10001/Onboarding+guide"
    body = page["body"]
    assert body.startswith("# Onboarding guide")
    assert "Welcome to **Acme**." in body
    assert "[handbook](https://acme.example/handbook)" in body
    assert "- Get your laptop" in body
    assert "  - Daily check-in" in body
    assert "1. Sign the contract" in body
    assert "| Tool | Owner |" in body
    assert "| VPN | IT |" in body
    assert "```\nvpn connect --profile acme\n```" in body
    assert "`#help-it`" in body
    assert mock.requests[0]["query"] == {"body-format": "storage"}


def test_page_storage_format(cli):
    result = cli("page", "10001", "--format", "storage")
    assert result.json["body"].startswith("<h1>Onboarding guide</h1>")


def test_pages_resolves_space_key(cli, mock):
    result = cli("pages", "--space", "DOCS")
    assert result.code == 0, result.err
    assert [p["title"] for p in result.json["results"]][1] == "Onboarding guide"
    assert [r["path"] for r in mock.requests] == [
        "/wiki/api/v2/spaces",
        "/wiki/api/v2/spaces/5001/pages",
    ]


def test_spaces_returns_cursor(cli):
    data = cli("spaces", "--limit", "2").json
    assert data["next"] == "abc123"
    assert data["results"][1]["key"] == "HR"


def test_children(cli, mock):
    assert cli("children", "10000").json["results"][0]["id"] == "10001"
    assert mock.requests[0]["path"] == "/wiki/api/v2/pages/10000/children"


def test_token_is_only_sent_as_basic_header(cli, mock):
    cli("spaces")
    header = mock.requests[0]["headers"]["authorization"]
    assert header.startswith("Basic ")
    assert base64.b64decode(header[6:]) == b"tester@example.com:test-token"


def test_email_setting_joins_the_token(cli, mock):
    cli("spaces", extra={"CONFLUENCE_EMAIL": "me@acme.test", "CONFLUENCE_TOKEN": "abc"})
    header = mock.requests[0]["headers"]["authorization"]
    assert base64.b64decode(header[6:]) == b"me@acme.test:abc"


def test_missing_variable_is_a_json_error(cli):
    result = cli("spaces", extra={"CONFLUENCE_URL": ""})
    assert result.code == 1
    assert "CONFLUENCE_URL is not set" in result.error["error"]


def test_http_error_is_a_json_error(cli):
    result = cli("page", "404")
    assert result.code == 1
    assert result.error["status"] == 404


def test_markdown_to_storage():
    text = (
        "# Notes\n\nA **bold** and _soft_ word with `code` and a [link](https://x.test).\n\n"
        "- one\n  - nested\n- two\n\n1. first\n2. second\n\n"
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```python\nprint(1 < 2)\n```\n\n> quoted\n"
    )
    html = module.to_storage(text)
    assert html.startswith("<h1>Notes</h1><p>A <strong>bold</strong> and <em>soft</em> word")
    assert "<code>code</code>" in html
    assert '<a href="https://x.test">link</a>' in html
    assert "<ul><li>one<ul><li>nested</li></ul></li><li>two</li></ul>" in html
    assert "<ol><li>first</li><li>second</li></ol>" in html
    assert (
        "<table><tbody><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></tbody></table>"
        in html
    )
    assert 'ac:name="code"' in html
    assert '<ac:parameter ac:name="language">python</ac:parameter>' in html
    assert "<![CDATA[print(1 < 2)]]>" in html
    assert "<blockquote><p>quoted</p></blockquote>" in html


def test_html_is_escaped():
    assert module.to_storage("a <script> & b") == "<p>a &lt;script&gt; &amp; b</p>"


def test_create_posts_storage_body(cli, mock):
    result = cli(
        "create", "--space", "DOCS", "--title", "Meeting notes 2026-11-02", "--body", "# Hi\n\nText"
    )
    assert result.code == 0, result.err
    assert result.json["id"] == "10077"
    assert (
        result.json["url"]
        == "https://acme.atlassian.net/wiki/spaces/DOCS/pages/10077/Meeting+notes+2026-11-02"
    )
    post = mock.requests[-1]
    assert (post["method"], post["path"]) == ("POST", "/wiki/api/v2/pages")
    assert post["body"]["spaceId"] == "5001"
    assert post["body"]["status"] == "current"
    assert post["body"]["title"] == "Meeting notes 2026-11-02"
    assert post["body"]["body"] == {"representation": "storage", "value": "<h1>Hi</h1><p>Text</p>"}
    assert "parentId" not in post["body"]


def test_create_with_parent_from_stdin(cli, mock):
    result = cli(
        "create",
        "--space",
        "5001",
        "--title",
        "T",
        "--parent",
        "10000",
        "--body-file",
        "-",
        stdin="Hello",
    )
    assert result.code == 0, result.err
    post = mock.requests[-1]
    assert post["body"]["parentId"] == "10000"
    assert post["body"]["body"]["value"] == "<p>Hello</p>"


def test_create_draft(cli, mock):
    assert cli("create", "--space", "5001", "--title", "Draft", "--draft", "--body", "x").code == 0
    assert mock.requests[-1]["body"]["status"] == "draft"


def test_update_raises_the_version(cli, mock):
    result = cli("update", "10001", "--body", "New text", "--message", "Fix")
    assert result.code == 0, result.err
    assert result.json["version"] == 5
    put = mock.requests[-1]
    assert (put["method"], put["path"]) == ("PUT", "/wiki/api/v2/pages/10001")
    assert put["body"]["version"] == {"number": 5, "message": "Fix"}
    assert put["body"]["title"] == "Onboarding guide"
    assert put["body"]["id"] == "10001"
    assert put["body"]["body"]["value"] == "<p>New text</p>"


def test_update_with_storage_format_keeps_markup(cli, mock):
    assert cli("update", "10001", "--format", "storage", "--body", "<p>raw</p>").code == 0
    assert mock.requests[-1]["body"]["body"]["value"] == "<p>raw</p>"


def test_comment(cli, mock):
    result = cli("comment", "10001", "--body", "Updated the table.")
    assert result.code == 0, result.err
    post = mock.requests[-1]
    assert post["path"] == "/wiki/api/v2/footer-comments"
    assert post["body"]["pageId"] == "10001"
    assert post["body"]["body"]["value"] == "<p>Updated the table.</p>"


def test_missing_text_is_an_error(cli):
    result = cli("create", "--space", "5001", "--title", "T")
    assert result.code == 1
    assert "--body" in result.error["error"]


@pytest.mark.real_api
def test_real_spaces(real_cli):
    result = real_cli("spaces", "--limit", "1")
    assert result.code == 0, result.err
    assert "results" in result.json
