import pytest


def test_create_for_a_customer(cli, mock):
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
    assert result.json == {"id": 43, "number": "52043", "title": "Printer offline"}
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/api/v1/tickets")
    body = sent["body"]
    assert body["group"] == "Users"
    assert body["customer"] == "anna@example.com"
    assert body["article"] == {
        "subject": "Printer offline",
        "body": "The printer in room 2 is offline.",
        "type": "note",
        "internal": False,
        "content_type": "text/plain",
        "sender": "Customer",
    }
    assert "priority" not in body
    assert "state" not in body


def test_create_for_the_owner_of_the_token(cli, mock):
    result = cli("create", "--title", "Printer offline", "--group", "Users", "--body", "Help")
    assert result.code == 0, result.err
    body = mock.requests[0]["body"]
    assert "customer" not in body
    assert "sender" not in body["article"]


def test_priority_and_text_from_stdin(cli, mock):
    cli(
        "create",
        "--title",
        "Printer offline",
        "--group",
        "Users",
        "--priority",
        "3 high",
        "--body-file",
        "-",
        stdin="From a file",
    )
    body = mock.requests[0]["body"]
    assert body["priority"] == "3 high"
    assert body["article"]["body"] == "From a file"


def test_it_has_no_command_to_read_or_answer_tickets(cli):
    for command in ("search", "ticket", "reply", "update"):
        assert cli(command, "42").code != 0


def test_me_checks_the_connection(cli, mock):
    result = cli("me")
    assert result.json["login"] == "bot@example.com"
    assert mock.requests[0]["path"] == "/api/v1/users/me"


def test_token_goes_in_the_authorization_header(cli, mock):
    cli("me")
    assert mock.requests[0]["headers"]["authorization"] == "Token token=test-token"


def test_missing_text_is_an_error(cli, mock):
    result = cli("create", "--title", "x", "--group", "Users")
    assert result.code == 1
    assert "--body" in result.error["error"]
    assert mock.requests == []


def test_missing_url_is_a_json_error(cli):
    result = cli("me", extra={"ZAMMAD_URL": ""})
    assert result.code == 1
    assert "ZAMMAD_URL is not set" in result.error["error"]


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
    result = cli("create", "--title", "x", "--group", "Nope", "--body", "x")
    assert result.code == 1
    assert result.error["status"] == 422
    assert "group" in result.error["detail"]


@pytest.mark.real_api
def test_real_me(real_cli):
    result = real_cli("me")
    assert result.code == 0, result.err
    assert result.json["id"]
