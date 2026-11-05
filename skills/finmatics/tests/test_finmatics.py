import base64

import pytest

CLIENT = "11111111-1111-4111-8111-111111111111"
DOC = "aaaaaaaa-0000-4000-8000-000000000001"


def documents_requests(mock):
    return [r for r in mock.requests if r["path"] == "/api/v1/documents/" and r["method"] == "GET"]


def test_clients(cli):
    result = cli("clients")
    assert result.code == 0, result.err
    assert result.json["results"] == [
        {"id": CLIENT, "name": "Example Trading GmbH", "number": "1000"}
    ]


def test_upload_sends_a_form_with_client_type_and_file(cli, mock, tmp_path):
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"%PDF-1.4 sample")
    result = cli("upload", str(path))
    assert result.code == 0, result.err
    assert result.json["id"] == "aaaaaaaa-0000-4000-8000-000000000009"
    assert result.json["status"] == "processing"
    sent = mock.requests[-1]
    assert (sent["method"], sent["path"]) == ("POST", "/api/v1/documents/")
    assert sent["headers"]["content-type"].startswith("multipart/form-data; boundary=")
    assert 'name="client"\r\n\r\n' + CLIENT in sent["body"]
    assert 'name="bookingName"\r\n\r\nER' in sent["body"]
    assert 'name="file"; filename="invoice.pdf"' in sent["body"]
    assert "Content-Type: application/pdf" in sent["body"]
    assert "%PDF-1.4 sample" in sent["body"]


def test_upload_with_client_and_type_does_not_look_up_clients(cli, mock, tmp_path):
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"x")
    result = cli("upload", str(path), "--type", "AR", "--client", "my-client")
    assert result.code == 0, result.err
    assert len(mock.requests) == 1
    assert 'name="bookingName"\r\n\r\nAR' in mock.requests[0]["body"]
    assert 'name="client"\r\n\r\nmy-client' in mock.requests[0]["body"]


def test_upload_of_a_missing_file_is_an_error(cli, mock):
    result = cli("upload", "/nonexistent/invoice.pdf")
    assert result.code == 1
    assert "cannot find the file" in result.error["error"]
    assert mock.requests == []


def test_list_of_a_month_asks_for_the_month_and_keeps_only_that_month(cli, mock):
    result = cli("list", "--month", "2026-09", "--type", "ER", "--client", CLIENT)
    assert result.code == 0, result.err
    sent = documents_requests(mock)[0]["query"]
    assert sent["fields"] == "all"
    assert sent["invoiceDate__gte"] == "2026-09-01"
    assert sent["invoiceDate__lte"] == "2026-09-30"
    assert sent["bookingName"] == "ER"
    assert sent["client"] == CLIENT
    # The mock ignores filters, as Finmatics does with one it does not know.
    assert [d["invoice_no"] for d in result.json["results"]] == ["S-100", "O-55"]
    assert result.json["more"] is False
    # `fields=all` leaves the net amount empty, its lines have it.
    assert [d["net"] for d in result.json["results"]] == [100.1, None]
    assert result.json["results"][0]["gross"] == 120.12


def test_list_reads_further_pages_by_number_and_stops_at_the_limit(cli, mock):
    result = cli("list", "--limit", "4")
    assert [d["invoice_no"] for d in result.json["results"]] == ["S-100", "O-55", "S-99", "AR-7"]
    assert result.json["more"] is True
    assert [r["query"]["page"] for r in documents_requests(mock)] == ["1", "2"]


def test_february_of_a_leap_year(cli, mock):
    cli("list", "--month", "2028-02")
    assert documents_requests(mock)[0]["query"]["invoiceDate__lte"] == "2028-02-29"


def test_get_joins_both_answers_and_leaves_out_empty_fields(cli, mock):
    result = cli("get", DOC)
    assert result.code == 0, result.err
    assert result.json["taxCode"] == "V20"
    assert result.json["items"][0]["itemText"] == "Paper"
    assert result.json["totalNetAmount"] == 100.1
    assert "comment" not in result.json
    assert "dueDate" not in result.json
    assert [r["query"].get("fields") for r in mock.requests] == [None, "all"]


def test_text_is_grouped_by_page_and_line(cli):
    result = cli("text", DOC)
    assert result.code == 0, result.err
    assert result.json["pages"] == [
        {"page": 1, "lines": ["Invoice S-100", "Total"]},
        {"page": 2, "lines": ["Terms"]},
    ]


def test_download_writes_the_pdf_or_the_original(cli, tmp_path):
    target = tmp_path / "out.pdf"
    result = cli("download", DOC, "--output", str(target))
    assert result.code == 0, result.err
    assert target.read_bytes() == b"%PDF-converted"
    assert result.json["bytes"] == len(b"%PDF-converted")
    cli("download", DOC, "--output", str(target), "--original")
    assert target.read_bytes() == b"%PDF-original"


def test_update_sends_only_the_fields_and_shows_what_is_stored(cli, mock):
    result = cli("update", DOC, "--set", "invoiceNo=S-100", "--set", "comment=hello")
    assert result.code == 0, result.err
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("PATCH", f"/api/v1/documents/{DOC}/")
    assert sent["body"] == {"invoiceNo": "S-100", "comment": "hello"}
    # The fixture does not store `comment`, like the real service.
    assert result.json == {"id": DOC, "stored": {"invoiceNo": "S-100", "comment": None}}


def test_update_needs_name_and_value(cli, mock):
    assert "name=value" in cli("update", DOC, "--set", "novalue").error["error"]
    assert "at least one" in cli("update", DOC).error["error"]
    assert mock.requests == []


def test_partners_are_found_by_part_of_the_name_in_any_case(cli):
    result = cli("partners", "--name", "SUPPLIES")
    assert result.code == 0, result.err
    assert [p["partnerNo"] for p in result.json["results"]] == ["70001", "70003"]
    assert "vat" not in result.json["results"][0]


def test_partners_by_number_and_client(cli, mock):
    assert [p["partnerName"] for p in cli("partners", "--number", "70002").json["results"]] == [
        "Example Office KG"
    ]
    result = cli("partners", "--client", CLIENT)
    assert [p["partnerNo"] for p in result.json["results"]] == ["70001", "70002"]
    assert mock.requests[-1]["query"]["client"] == CLIENT


def test_partners_stop_at_the_limit(cli):
    result = cli("partners", "--limit", "2")
    assert len(result.json["results"]) == 2 and result.json["more"] is True


def test_create_partner_sends_the_required_fields_and_more(cli, mock):
    result = cli(
        "create-partner",
        "--name",
        "Example Tools AG",
        "--number",
        "70009",
        "--set",
        "city=Example City",
        "--set",
        "country=AT",
    )
    assert result.code == 0, result.err
    assert result.json["id"] == "bbbbbbbb-0000-4000-8000-000000000009"
    sent = mock.requests[-1]
    assert (sent["method"], sent["path"]) == ("POST", "/api/v1/partners/")
    assert sent["body"] == {
        "partnerName": "Example Tools AG",
        "partnerNo": "70009",
        "bookingCategory": "ER",
        "client": CLIENT,
        "city": "Example City",
        "country": "AT",
    }


def test_create_partner_refuses_a_number_that_exists(cli, mock):
    result = cli("create-partner", "--name", "Other Name", "--number", "70001")
    assert result.code == 1
    assert "exists already" in result.error["error"]
    assert result.error["detail"]["partnerName"] == "Example Supplies Ltd"
    assert all(r["method"] == "GET" for r in mock.requests)


def test_create_partner_allows_the_number_in_another_category_or_client(cli, mock):
    assert cli("create-partner", "--name", "A", "--number", "70001", "--type", "AR").code == 0
    assert mock.requests[-1]["body"]["bookingCategory"] == "AR"
    # 70003 belongs to another client in the fixture.
    assert cli("create-partner", "--name", "B", "--number", "70003").code == 0
    assert mock.requests[-1]["body"]["partnerNo"] == "70003"


def test_create_partner_needs_name_and_number(cli, mock):
    assert cli("create-partner", "--name", "No Number").code != 0
    assert cli("create-partner", "--number", "1").code != 0
    result = cli("create-partner", "--name", "A", "--number", "1", "--set", "novalue")
    assert result.code == 1 and "name=value" in result.error["error"]
    assert mock.requests == []


def test_stats_sums_one_month_of_one_client(cli, mock):
    result = cli("stats", "--month", "2026-09")
    assert result.code == 0, result.err
    data = result.json
    assert data["client"] == CLIENT
    assert data["documents"] == 3
    assert data["verification_levels"] == {"10": 1, "20": 2}
    assert data["totals"] == [
        {
            "type": "AR",
            "currency": "EUR",
            "documents": 1,
            "net": 1000.0,
            "tax": 200.0,
            "gross": 1200.0,
            "documents_without": {"net": 0, "tax": 0, "gross": 0},
        },
        {
            "type": "ER",
            "currency": "EUR",
            "documents": 2,
            "net": 100.1,
            "tax": 30.12,
            "gross": 180.72,
            "documents_without": {"net": 1, "tax": 0, "gross": 0},
        },
    ]
    er = [r for r in data["by_partner"] if r["type"] == "ER"]
    assert [(r["partner"], r["gross"]) for r in er] == [
        ("Example Supplies Ltd", 120.12),
        ("Example Office KG", 60.6),
    ]
    sent = documents_requests(mock)[0]["query"]
    assert sent["invoiceDate__gte"] == "2026-09-01" and sent["client"] == CLIENT


def test_stats_of_an_empty_month(cli):
    result = cli("stats", "--month", "2026-03")
    assert result.code == 0, result.err
    assert result.json["documents"] == 0 and result.json["totals"] == []


def test_stats_has_no_sum_when_no_document_has_a_value(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "GET",
            "path": "/api/v1/documents/",
            "body": {
                "next": None,
                "results": [
                    {
                        "client": CLIENT,
                        "bookingName": "ER",
                        "currency": "EUR",
                        "invoiceDate": "2026-09-05",
                        "partnerName": "",
                        "totalNetAmount": None,
                        "totalTaxAmount": 0.0,
                        "totalGrossAmount": 10.0,
                    }
                ],
            },
        },
    )
    data = cli("stats", "--month", "2026-09").json
    assert data["totals"][0]["net"] is None
    assert data["totals"][0]["tax"] == 0.0
    assert data["totals"][0]["documents_without"]["net"] == 1
    assert data["by_partner"][0]["partner"] is None


def test_stats_of_several_clients_asks_for_one(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "GET",
            "path": "/api/v1/clients/",
            "body": {
                "next": None,
                "results": [
                    {"id": "c1", "clientName": "One", "clientNo": "1"},
                    {"id": "c2", "clientName": "Two", "clientNo": "2"},
                ],
            },
        },
    )
    result = cli("stats", "--month", "2026-09")
    assert result.code == 1
    assert "--client" in result.error["error"]
    assert [c["id"] for c in result.error["detail"]] == ["c1", "c2"]
    assert documents_requests(mock) == []


def test_bad_month_is_an_error(cli, mock):
    result = cli("stats", "--month", "2026-13", "--client", CLIENT)
    assert result.code == 1 and "YYYY-MM" in result.error["error"]
    assert mock.requests == []


def test_nothing_can_delete_a_document(cli, mock):
    assert cli("delete", DOC).code != 0
    assert all(r["method"] != "DELETE" for r in mock.requests)


def test_password_is_only_in_the_authorization_header(cli, mock):
    cli("get", DOC)
    request = mock.requests[0]
    expected = base64.b64encode(b"tester@example.com:test-password").decode()
    assert request["headers"]["authorization"] == f"Basic {expected}"
    assert "test-password" not in request["path"] + str(request["query"])


def test_a_placeholder_password_is_sent_as_it_is(cli, mock):
    """A proxy with a credential vault replaces the placeholder inside the Basic value."""
    placeholder = "vault-placeholder"
    cli("clients", extra={"FINMATICS_PASSWORD": placeholder})
    token = mock.requests[0]["headers"]["authorization"].removeprefix("Basic ")
    assert base64.b64decode(token).decode() == f"tester@example.com:{placeholder}"


@pytest.mark.parametrize("name", ["FINMATICS_USER", "FINMATICS_PASSWORD"])
def test_missing_credentials_are_a_json_error(cli, mock, name):
    result = cli("clients", extra={name: ""})
    assert result.code == 1
    assert name in result.error["error"]
    assert mock.requests == []


def test_http_error_is_a_json_error_without_the_password(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "GET",
            "path": "/api/v1/clients/",
            "status": 401,
            "body": {"detail": "Invalid username/password."},
        },
    )
    result = cli("clients")
    assert result.code == 1
    assert result.error["status"] == 401
    assert "Invalid username/password" in result.error["detail"]
    assert "test-password" not in result.err


@pytest.mark.real_api
def test_real_clients(real_cli):
    result = real_cli("clients")
    assert result.code == 0, result.err
    assert result.json["results"]


@pytest.mark.real_api
def test_real_stats_are_read_only(real_cli):
    result = real_cli("stats", "--month", "2026-01")
    assert result.code == 0, result.err
    assert "totals" in result.json
