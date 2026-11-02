import pytest


def test_search_sends_query_and_returns_rows(cli, mock):
    result = cli("search", 'state.name:open AND title:"printer"', "--limit", "5")
    assert result.code == 0, result.err
    rows = result.json["results"]
    assert [r["id"] for r in rows] == [42, 37]
    assert rows[0]["title"] == "Printer offline"
    sent = mock.requests[0]
    assert sent["path"] == "/api/v1/tickets/search"
    assert sent["query"]["query"] == 'state.name:open AND title:"printer"'
    assert sent["query"]["limit"] == "5"
    assert sent["query"]["expand"] == "true"
    assert sent["method"] == "GET"


def test_ticket_hides_internal_notes_by_default(cli, mock):
    data = cli("ticket", "42").json
    assert data["state"] == "open"
    assert [a["id"] for a in data["articles"]] == [101, 103]
    assert (
        data["articles"][0]["body"] == "Hello,\nthe printer in room 2 shows offline since Monday."
    )
    assert [r["path"] for r in mock.requests] == [
        "/api/v1/tickets/42",
        "/api/v1/ticket_articles/by_ticket/42",
    ]


def test_ticket_internal_flag_shows_notes(cli):
    data = cli("ticket", "42", "--internal").json
    assert [a["id"] for a in data["articles"]] == [101, 102, 103]


def test_kb_search(cli, mock):
    result = cli("kb-search", "reset password", "--kb", "1", "--locale", "en-us")
    assert result.code == 0, result.err
    assert result.json["results"][0]["title"] == "How to reset your password"
    sent = mock.requests[0]
    assert sent["method"] == "POST"
    assert sent["body"]["query"] == "reset password"
    assert sent["body"]["knowledge_base_id"] == "1"
    assert sent["body"]["locale"] == "en-us"


def test_kb_answer(cli):
    data = cli("kb-answer", "7", "--kb", "1").json
    assert data["translations"][0]["title"] == "How to reset your password"
    assert "Forgot password" in data["translations"][0]["body"]


def test_token_goes_in_the_authorization_header(cli, mock):
    cli("search", "printer")
    request = mock.requests[0]
    assert request["headers"]["authorization"] == "Token token=test-token"
    assert "test-token" not in request["path"]
    assert "test-token" not in str(request["query"])


def test_missing_url_is_a_json_error(cli):
    result = cli("search", "x", extra={"ZAMMAD_URL": ""})
    assert result.code == 1
    assert "ZAMMAD_URL is not set" in result.error["error"]


def test_http_error_is_a_json_error(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "GET",
            "path": "/api/v1/tickets/{id}",
            "status": 403,
            "body": {"error": "forbidden"},
        },
    )
    result = cli("ticket", "42")
    assert result.code == 1
    assert result.error["status"] == 403


@pytest.mark.real_api
def test_real_search(real_cli):
    result = real_cli("search", "*", "--limit", "1")
    assert result.code == 0, result.err
    assert "results" in result.json
