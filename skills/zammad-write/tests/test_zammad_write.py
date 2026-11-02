import pytest


def test_create_ticket(cli, mock):
    result = cli(
        "create",
        "--title",
        "Printer offline",
        "--group",
        "Users",
        "--customer",
        "anna@example.com",
        "--body",
        "The printer in room 2 is offline.",
    )
    assert result.code == 0, result.err
    assert result.json["id"] == 43
    assert result.json["number"] == "52043"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/api/v1/tickets")
    body = sent["body"]
    assert body["title"] == "Printer offline"
    assert body["group"] == "Users"
    assert body["customer"] == "anna@example.com"
    assert body["article"]["body"] == "The printer in room 2 is offline."
    assert body["article"]["type"] == "note"
    assert body["article"]["internal"] is False
    assert "state" not in body


def test_create_with_state_and_priority_from_stdin(cli, mock):
    cli(
        "create",
        "--title",
        "Printer offline",
        "--group",
        "Users",
        "--customer",
        "a@b.test",
        "--state",
        "open",
        "--priority",
        "3 high",
        "--body-file",
        "-",
        stdin="From a file",
    )
    body = mock.requests[0]["body"]
    assert body["state"] == "open"
    assert body["priority"] == "3 high"
    assert body["article"]["body"] == "From a file"


def test_reply_internal_note(cli, mock):
    result = cli("reply", "42", "--body", "We replaced the toner.", "--internal")
    assert result.code == 0, result.err
    assert result.json["id"] == 104
    body = mock.requests[0]["body"]
    assert mock.requests[0]["path"] == "/api/v1/ticket_articles"
    assert body["ticket_id"] == 42
    assert body["internal"] is True
    assert body["type"] == "note"
    assert body["sender"] == "Agent"


def test_reply_email_to_customer(cli, mock):
    cli("reply", "42", "--type", "email", "--to", "anna@example.com", "--body", "Works again.")
    body = mock.requests[0]["body"]
    assert body["type"] == "email"
    assert body["to"] == "anna@example.com"
    assert body["internal"] is False


def test_set_state(cli, mock):
    result = cli("set-state", "42", "--state", "closed")
    assert result.code == 0, result.err
    assert result.json["state"] == "closed"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("PUT", "/api/v1/tickets/42")
    assert sent["body"] == {"state": "closed"}


def test_states(cli):
    names = [r["name"] for r in cli("states").json["results"]]
    assert "closed" in names


def test_token_goes_in_the_authorization_header(cli, mock):
    cli("states")
    assert mock.requests[0]["headers"]["authorization"] == "Token token=test-token"


def test_missing_text_is_an_error(cli):
    result = cli("reply", "42")
    assert result.code == 1
    assert "--body" in result.error["error"]


def test_server_error_is_reported(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "POST",
            "path": "/api/v1/tickets",
            "status": 422,
            "body": {"error": "No lookup value found for 'group': \"Nope\""},
        },
    )
    result = cli(
        "create", "--title", "x", "--group", "Nope", "--customer", "a@b.test", "--body", "x"
    )
    assert result.code == 1
    assert result.error["status"] == 422
    assert "group" in result.error["detail"]


@pytest.mark.real_api
def test_real_states(real_cli):
    result = real_cli("states")
    assert result.code == 0, result.err
    assert any(r["name"] == "open" for r in result.json["results"])
