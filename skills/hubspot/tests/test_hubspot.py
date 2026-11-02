import pytest


def test_search_sends_query_filters_and_paging(cli, mock):
    result = cli(
        "search",
        "contacts",
        "--query",
        "anna",
        "--filter",
        "lifecyclestage=lead",
        "--filter",
        "createdate>2026-01-01",
        "--limit",
        "5",
    )
    assert result.code == 0, result.err
    data = result.json
    assert data["total"] == 2 and data["next"] == "2"
    assert data["results"][0]["id"] == "301"
    assert data["results"][0]["properties"]["email"] == "anna@example.com"
    assert "phone" not in data["results"][0]["properties"]
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/crm/v3/objects/contacts/search")
    body = sent["body"]
    assert body["query"] == "anna"
    assert body["limit"] == 5
    assert body["filterGroups"] == [
        {
            "filters": [
                {"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"},
                {"propertyName": "createdate", "operator": "GT", "value": "2026-01-01"},
            ]
        }
    ]
    assert "email" in body["properties"]


def test_search_deals_with_properties(cli, mock):
    result = cli("search", "deals", "--filter", "amount>10000", "--properties", "dealname,amount")
    assert result.json["results"][0]["properties"]["dealname"] == "Berger GmbH renewal"
    assert mock.requests[0]["body"]["properties"] == ["dealname", "amount"]


def test_get_asks_for_default_properties(cli, mock):
    result = cli("get", "companies", "5123")
    assert result.json["properties"]["name"] == "Berger GmbH"
    sent = mock.requests[0]
    assert sent["path"] == "/crm/v3/objects/companies/5123"
    assert "domain" in sent["query"]["properties"].split(",")


def test_create(cli, mock):
    result = cli(
        "create", "contacts", "--prop", "email=carla@example.com", "--prop", "firstname=Carla"
    )
    assert result.code == 0, result.err
    assert result.json["id"] == "303"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/crm/v3/objects/contacts")
    assert sent["body"]["properties"] == {"email": "carla@example.com", "firstname": "Carla"}


def test_update(cli, mock):
    result = cli("update", "deals", "8801", "--prop", "dealstage=closedwon")
    assert result.json["properties"]["dealstage"] == "closedwon"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("PATCH", "/crm/v3/objects/deals/8801")
    assert sent["body"] == {"properties": {"dealstage": "closedwon"}}


def test_note_is_associated_with_records(cli, mock):
    result = cli(
        "note", "--to", "contacts:301", "--to", "companies:5123", "--body", "Called, wants a quote."
    )
    assert result.code == 0, result.err
    assert result.json["id"] == "9001"
    body = mock.requests[0]["body"]
    assert mock.requests[0]["path"] == "/crm/v3/objects/notes"
    assert body["properties"]["hs_note_body"] == "Called, wants a quote."
    assert body["properties"]["hs_timestamp"].endswith("Z")
    assert [(a["to"]["id"], a["types"][0]["associationTypeId"]) for a in body["associations"]] == [
        ("301", 202),
        ("5123", 190),
    ]
    assert body["associations"][0]["types"][0]["associationCategory"] == "HUBSPOT_DEFINED"


def test_bad_filter_and_prop_are_errors(cli):
    assert cli("search", "contacts", "--filter", "nonsense").code == 1
    result = cli("create", "contacts", "--prop", "novalue")
    assert result.code == 1 and "name=value" in result.error["error"]
    result = cli("note", "--to", "tickets:1", "--body", "x")
    assert result.code == 1 and "contacts:ID" in result.error["error"]


def test_token_is_only_in_the_authorization_header(cli, mock):
    cli("get", "contacts", "301")
    request = mock.requests[0]
    assert request["headers"]["authorization"] == "Bearer test-token"
    assert "test-token" not in request["path"] + str(request["query"])


def test_missing_token_is_a_json_error(cli):
    result = cli("get", "contacts", "1", extra={"HUBSPOT_TOKEN": ""})
    assert result.code == 1
    assert "HUBSPOT_TOKEN is not set" in result.error["error"]


def test_http_error_is_a_json_error(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "GET",
            "path": "/crm/v3/objects/contacts/{id}",
            "status": 403,
            "body": {"message": "missing scope crm.objects.contacts.read"},
        },
    )
    result = cli("get", "contacts", "301")
    assert result.code == 1
    assert result.error["status"] == 403
    assert "crm.objects.contacts.read" in result.error["detail"]


@pytest.mark.real_api
def test_real_search(real_cli):
    result = real_cli("search", "contacts", "--limit", "1")
    assert result.code == 0, result.err
    assert "results" in result.json
