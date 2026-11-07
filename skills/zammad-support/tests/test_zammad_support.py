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


def test_ticket_lists_attachments(cli):
    article = cli("ticket", "42").json["articles"][0]
    assert article["attachments"] == [{"id": 19, "filename": "photo.png", "size": "2048"}]


def test_attachment_is_saved_to_a_file(cli, mock, tmp_path):
    target = tmp_path / "photo.png"
    result = cli("attachment", "42", "101", "19", "--output", str(target))
    assert result.code == 0, result.err
    assert mock.requests[0]["path"] == "/api/v1/ticket_attachment/42/101/19"
    assert target.read_bytes() == b'{"fixture": "attachment"}'
    assert result.json["size"] == target.stat().st_size


def test_users_search_leaves_out_other_fields(cli, mock):
    rows = cli("users", "anna").json["results"]
    assert rows[0]["email"] == "anna@example.com"
    assert "password" not in rows[0]
    assert mock.requests[0]["path"] == "/api/v1/users/search"
    assert mock.requests[0]["query"]["query"] == "anna"


def test_states_and_priorities(cli):
    assert "closed" in [r["name"] for r in cli("states").json["results"]]
    assert "3 high" in [r["name"] for r in cli("priorities").json["results"]]


def create_args(*extra):
    return (
        "create",
        "--title",
        "Printer offline",
        "--group",
        "Users",
        "--customer",
        "anna@example.com",
        "--body",
        "It is offline.",
        *extra,
    )


def test_create_ticket(cli, mock):
    result = cli(*create_args())
    assert result.code == 0, result.err
    assert result.json["number"] == "52043"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/api/v1/tickets")
    assert sent["body"]["customer"] == "anna@example.com"
    assert sent["body"]["article"]["type"] == "note"
    assert sent["body"]["article"]["internal"] is False
    assert "sender" not in sent["body"]["article"]
    assert "state" not in sent["body"]


def test_create_from_a_phone_call_of_the_customer(cli, mock):
    cli(*create_args("--type", "phone", "--from-customer", "--owner", "agent@example.com"))
    body = mock.requests[0]["body"]
    assert body["article"]["type"] == "phone"
    assert body["article"]["sender"] == "Customer"
    assert body["owner"] == "agent@example.com"


def test_create_cannot_send_email(cli, mock):
    assert cli(*create_args("--type", "email")).code != 0
    assert mock.requests == []


def test_reply_internal_note(cli, mock):
    result = cli("reply", "42", "--body", "We replaced the toner.", "--internal", "--time", "15")
    assert result.code == 0, result.err
    assert result.json["id"] == 104
    sent = mock.requests[0]
    assert sent["path"] == "/api/v1/ticket_articles"
    assert sent["body"]["ticket_id"] == 42
    assert sent["body"]["internal"] is True
    assert sent["body"]["type"] == "note"
    assert sent["body"]["sender"] == "Agent"
    assert sent["body"]["time_unit"] == "15"


def test_reply_email_with_copy_and_attachment(cli, mock, tmp_path):
    file = tmp_path / "manual.pdf"
    file.write_bytes(b"cake")
    result = cli(
        "reply",
        "42",
        "--type",
        "email",
        "--to",
        "anna@example.com",
        "--cc",
        "ben@example.com",
        "--body",
        "Works again.",
        "--attach",
        str(file),
    )
    assert result.code == 0, result.err
    body = mock.requests[0]["body"]
    assert (body["type"], body["to"], body["cc"]) == (
        "email",
        "anna@example.com",
        "ben@example.com",
    )
    assert body["internal"] is False
    assert body["attachments"] == [
        {"filename": "manual.pdf", "data": "Y2FrZQ==", "mime-type": "application/pdf"}
    ]


def test_email_without_recipient_is_not_sent(cli, mock):
    result = cli("reply", "42", "--type", "email", "--body", "x")
    assert result.code == 1
    assert "--to" in result.error["error"]
    assert mock.requests == []


def test_internal_email_is_not_sent(cli, mock):
    result = cli("reply", "42", "--type", "email", "--to", "a@b.test", "--internal", "--body", "x")
    assert result.code == 1
    assert mock.requests == []


def test_email_off_refuses_email(cli, mock):
    args = ("reply", "42", "--type", "email", "--to", "anna@example.com", "--body", "x")
    result = cli(*args, extra={"ZAMMAD_EMAIL": "off"})
    assert result.code == 1
    assert "ZAMMAD_EMAIL" in result.error["error"]
    assert mock.requests == []


def test_email_off_still_writes_notes(cli, mock):
    result = cli("reply", "42", "--internal", "--body", "x", extra={"ZAMMAD_EMAIL": "off"})
    assert result.code == 0, result.err
    assert mock.requests[0]["body"]["type"] == "note"


def test_reply_is_plain_text_by_default(cli, mock):
    assert cli("reply", "42", "--internal", "--body", "x").code == 0
    assert mock.requests[0]["body"]["content_type"] == "text/plain"


def test_reply_html_with_subject(cli, mock):
    result = cli(
        "reply",
        "42",
        "--internal",
        "--html",
        "--subject",
        "Answer for the customer",
        "--body",
        "<p>Hello,</p><ul><li>Restart the printer.</li></ul>",
    )
    assert result.code == 0, result.err
    body = mock.requests[0]["body"]
    assert body["content_type"] == "text/html"
    assert body["subject"] == "Answer for the customer"
    assert body["body"] == "<p>Hello,</p><ul><li>Restart the printer.</li></ul>"


def test_missing_attachment_is_an_error(cli, mock):
    result = cli("reply", "42", "--body", "x", "--attach", "/nonexistent/file")
    assert result.code == 1
    assert mock.requests == []


def test_missing_text_is_an_error(cli):
    result = cli("reply", "42")
    assert result.code == 1
    assert "--body" in result.error["error"]


def test_update_sends_only_what_changes(cli, mock):
    result = cli("update", "42", "--state", "closed")
    assert result.code == 0, result.err
    assert result.json["state"] == "closed"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("PUT", "/api/v1/tickets/42")
    assert sent["body"] == {"state": "closed"}


def test_update_owner_priority_group_and_pending_time(cli, mock):
    cli(
        "update",
        "42",
        "--owner",
        "agent@example.com",
        "--priority",
        "3 high",
        "--group",
        "Sales",
        "--state",
        "pending reminder",
        "--pending-time",
        "2026-12-01T09:00:00Z",
    )
    assert mock.requests[0]["body"] == {
        "owner": "agent@example.com",
        "priority": "3 high",
        "group": "Sales",
        "state": "pending reminder",
        "pending_time": "2026-12-01T09:00:00Z",
    }


def test_update_without_a_field_is_an_error(cli, mock):
    assert cli("update", "42").code == 1
    assert mock.requests == []


def test_tags(cli, mock):
    assert cli("tags", "42").json["tags"] == ["printer", "hardware"]
    assert mock.requests[0]["query"] == {"object": "Ticket", "o_id": "42"}


def test_tag_add_and_remove(cli, mock):
    assert cli("tag-add", "42", "printer").json["added"] == "printer"
    assert cli("tag-remove", "42", "printer").json["removed"] == "printer"
    add, remove = mock.requests
    assert (add["method"], add["path"]) == ("POST", "/api/v1/tags/add")
    assert (remove["method"], remove["path"]) == ("DELETE", "/api/v1/tags/remove")
    assert add["body"] == remove["body"] == {"item": "printer", "object": "Ticket", "o_id": 42}


def test_links(cli, mock):
    rows = cli("links", "42").json["results"]
    assert rows == [{"type": "normal", "id": 37, "number": "52037", "title": "Printer toner empty"}]
    assert mock.requests[0]["query"] == {"link_object": "Ticket", "link_object_value": "42"}


def test_link_add_takes_the_id_and_the_number(cli, mock):
    result = cli("link-add", "42", "52037")
    assert result.code == 0, result.err
    assert mock.requests[0]["body"] == {
        "link_type": "normal",
        "link_object_target": "Ticket",
        "link_object_target_value": 42,
        "link_object_source": "Ticket",
        "link_object_source_number": "52037",
    }


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
