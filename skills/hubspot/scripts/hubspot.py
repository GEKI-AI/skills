#!/usr/bin/env python3
"""HubSpot CRM: search, read, create and update contacts, companies and deals, add notes.

Needs HUBSPOT_TOKEN (a private app access token). The API address comes from
HUBSPOT_BASE_URL and defaults to https://api.hubapi.com. Output is JSON on
stdout. An error is JSON on stderr with exit code 1.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

OBJECTS = ("contacts", "companies", "deals")
DEFAULT_PROPERTIES = {
    "contacts": [
        "firstname",
        "lastname",
        "email",
        "phone",
        "company",
        "lifecyclestage",
        "hs_lead_status",
    ],
    "companies": ["name", "domain", "industry", "phone", "city", "numberofemployees"],
    "deals": ["dealname", "amount", "dealstage", "pipeline", "closedate"],
}
NOTE_ASSOCIATION_TYPE = {"contacts": 202, "companies": 190, "deals": 214}
OPERATORS = (
    ("!=", "NEQ"),
    (">=", "GTE"),
    ("<=", "LTE"),
    (">", "GT"),
    ("<", "LT"),
    ("~", "CONTAINS_TOKEN"),
    ("=", "EQ"),
)


def fail(message: str, status: int | None = None, detail: object = None) -> None:
    print(json.dumps({"error": message, "status": status, "detail": detail}), file=sys.stderr)
    sys.exit(1)


def token() -> str:
    value = os.environ.get("HUBSPOT_TOKEN", "").strip()
    if not value:
        fail("HUBSPOT_TOKEN is not set. See references/setup.md.")
    return value


def call(method: str, path: str, params: dict | None = None, body: dict | None = None):
    base = os.environ.get("HUBSPOT_BASE_URL", "").strip() or "https://api.hubapi.com"
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = base.rstrip("/") + path + (f"?{query}" if query else "")
    headers = {"Authorization": f"Bearer {token()}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        fail(f"HubSpot answered {exc.code}", exc.code, detail)
    except urllib.error.URLError as exc:
        fail(f"cannot reach HubSpot: {exc.reason}")


def props_arg(kind: str, value: str | None) -> list[str]:
    if value:
        return [p.strip() for p in value.split(",") if p.strip()]
    return DEFAULT_PROPERTIES[kind]


def record(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "properties": {k: v for k, v in (item.get("properties") or {}).items() if v is not None},
        "updated_at": item.get("updatedAt"),
        "archived": item.get("archived", False),
    }


def parse_filter(text: str) -> dict:
    for symbol, operator in OPERATORS:
        name, sep, value = text.partition(symbol)
        if sep and name.strip():
            return {"propertyName": name.strip(), "operator": operator, "value": value.strip()}
    fail(f"cannot read the filter {text!r}: use name=value, name~word, name>5")
    return {}


def parse_props(pairs: list[str]) -> dict:
    found = {}
    for pair in pairs or []:
        name, sep, value = pair.partition("=")
        if not sep or not name.strip():
            fail(f"cannot read {pair!r}: use name=value")
        found[name.strip()] = value
    if not found:
        fail("give at least one --prop name=value")
    return found


def cmd_search(args: argparse.Namespace) -> None:
    body: dict = {
        "limit": max(1, min(args.limit, 100)),
        "after": args.after or "0",
        "properties": props_arg(args.object, args.properties),
        "sorts": [],
        "filterGroups": [{"filters": [parse_filter(f) for f in args.filter]}]
        if args.filter
        else [],
    }
    if args.query:
        body["query"] = args.query
    data = call("POST", f"/crm/v3/objects/{args.object}/search", body=body)
    after = ((data.get("paging") or {}).get("next") or {}).get("after")
    print(
        json.dumps(
            {
                "total": data.get("total"),
                "results": [record(i) for i in data.get("results") or []],
                "next": after,
            }
        )
    )


def cmd_get(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"/crm/v3/objects/{args.object}/{urllib.parse.quote(args.id)}",
        {"properties": ",".join(props_arg(args.object, args.properties))},
    )
    print(json.dumps(record(data)))


def cmd_create(args: argparse.Namespace) -> None:
    data = call(
        "POST",
        f"/crm/v3/objects/{args.object}",
        body={"properties": parse_props(args.prop), "associations": []},
    )
    print(json.dumps(record(data)))


def cmd_update(args: argparse.Namespace) -> None:
    data = call(
        "PATCH",
        f"/crm/v3/objects/{args.object}/{urllib.parse.quote(args.id)}",
        body={"properties": parse_props(args.prop)},
    )
    print(json.dumps(record(data)))


def cmd_note(args: argparse.Namespace) -> None:
    associations = []
    for target in args.to:
        kind, _, record_id = target.partition(":")
        if kind not in NOTE_ASSOCIATION_TYPE or not re.fullmatch(r"\d+", record_id):
            fail(f"cannot read {target!r}: use contacts:ID, companies:ID or deals:ID")
        associations.append(
            {
                "to": {"id": record_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": NOTE_ASSOCIATION_TYPE[kind],
                    }
                ],
            }
        )
    text = sys.stdin.read() if args.body_file == "-" else args.body
    if not text:
        fail("give the text with --body or --body-file -")
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    body = {
        "properties": {"hs_note_body": text, "hs_timestamp": stamp},
        "associations": associations,
    }
    print(json.dumps(record(call("POST", "/crm/v3/objects/notes", body=body))))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="HubSpot CRM. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)

    def add(name: str, run, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(run=run)
        return p

    p = add("search", cmd_search, "search records")
    p.add_argument("object", choices=OBJECTS)
    p.add_argument("--query", help="words to find")
    p.add_argument(
        "--filter",
        action="append",
        default=[],
        help="name=value, name~word, name>5; repeat for AND",
    )
    p.add_argument("--properties", help="comma-separated property names")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--after", help="the `next` value of the previous result")
    p = add("get", cmd_get, "read one record")
    p.add_argument("object", choices=OBJECTS)
    p.add_argument("id")
    p.add_argument("--properties", help="comma-separated property names")
    p = add("create", cmd_create, "create a record")
    p.add_argument("object", choices=OBJECTS)
    p.add_argument("--prop", action="append", default=[], help="name=value, repeat")
    p = add("update", cmd_update, "change a record")
    p.add_argument("object", choices=OBJECTS)
    p.add_argument("id")
    p.add_argument("--prop", action="append", default=[], help="name=value, repeat")
    p = add("note", cmd_note, "add a note to contacts, companies or deals")
    p.add_argument(
        "--to", action="append", required=True, help="contacts:ID, companies:ID or deals:ID; repeat"
    )
    p.add_argument("--body", help="text of the note")
    p.add_argument("--body-file", help="- to read the text from standard input")
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
