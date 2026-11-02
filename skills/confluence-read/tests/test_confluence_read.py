import base64

import pytest


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


@pytest.mark.real_api
def test_real_spaces(real_cli):
    result = real_cli("spaces", "--limit", "1")
    assert result.code == 0, result.err
    assert "results" in result.json
