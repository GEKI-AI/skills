import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "confluence.py"
spec = importlib.util.spec_from_file_location("confluence_write", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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


def test_show_returns_storage(cli):
    data = cli("show", "10001").json
    assert data["version"] == 4
    assert data["storage"].startswith("<h1>Onboarding guide</h1>")


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
def test_real_auth_check(real_cli):
    # Read only: a write skill still has to prove that the token and URL work.
    result = real_cli("show", "1")
    assert result.code in (0, 1)
    if result.code == 1:
        assert result.error["status"] in (400, 403, 404)
