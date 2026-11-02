#!/usr/bin/env python3
"""Write Zammad tickets: create, reply, set the state.

Needs ZAMMAD_URL (https://support.example.com) and ZAMMAD_TOKEN (a personal
access token). Output is JSON on stdout. An error is JSON on stderr with exit
code 1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def fail(message: str, status: int | None = None, detail: object = None) -> None:
    print(json.dumps({"error": message, "status": status, "detail": detail}), file=sys.stderr)
    sys.exit(1)


def setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"{name} is not set. See references/setup.md.")
    return value


def request(method: str, path: str, params: dict | None = None, body: dict | None = None):
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = setting("ZAMMAD_URL").rstrip("/") + path + (f"?{query}" if query else "")
    headers = {
        "Authorization": f"Token token={setting('ZAMMAD_TOKEN')}",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        fail(f"Zammad answered {exc.code}", exc.code, exc.read().decode("utf-8", "replace")[:500])
    except urllib.error.URLError as exc:
        fail(f"cannot reach Zammad: {exc.reason}")


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return (
            sys.stdin.read()
            if args.body_file == "-"
            else Path(args.body_file).read_text(encoding="utf-8")
        )
    if args.body is not None:
        return args.body
    fail("give the text with --body or --body-file")
    return ""


def ticket_view(ticket: dict) -> dict:
    keys = ("id", "number", "title", "state_id", "priority_id", "group_id", "customer_id")
    view = {key: ticket.get(key) for key in keys}
    for key in ("state", "priority", "group", "customer"):
        if key in ticket:
            view[key] = ticket[key]
    return view


def cmd_create(args: argparse.Namespace) -> None:
    body = {
        "title": args.title,
        "group": args.group,
        "customer": args.customer,
        "article": {
            "subject": args.subject or args.title,
            "body": read_body(args),
            "type": args.type,
            "internal": args.internal,
            "content_type": "text/plain",
        },
    }
    if args.state:
        body["state"] = args.state
    if args.priority:
        body["priority"] = args.priority
    print(json.dumps(ticket_view(request("POST", "/api/v1/tickets", body=body))))


def cmd_reply(args: argparse.Namespace) -> None:
    body = {
        "ticket_id": int(args.id),
        "body": read_body(args),
        "type": args.type,
        "internal": args.internal,
        "sender": "Agent",
        "content_type": "text/plain",
    }
    if args.subject:
        body["subject"] = args.subject
    if args.to:
        body["to"] = args.to
    article = request("POST", "/api/v1/ticket_articles", body=body)
    print(
        json.dumps(
            {
                "id": article.get("id"),
                "ticket_id": article.get("ticket_id"),
                "type": article.get("type"),
                "internal": article.get("internal"),
            }
        )
    )


def cmd_set_state(args: argparse.Namespace) -> None:
    body = {"state": args.state}
    print(
        json.dumps(
            ticket_view(request("PUT", f"/api/v1/tickets/{args.id}", {"expand": "true"}, body))
        )
    )


def cmd_states(_args: argparse.Namespace) -> None:
    rows = request("GET", "/api/v1/ticket_states") or []
    print(
        json.dumps(
            {
                "results": [
                    {"id": r.get("id"), "name": r.get("name"), "active": r.get("active")}
                    for r in rows
                ]
            }
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Write Zammad tickets. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)

    def text(p: argparse.ArgumentParser) -> None:
        p.add_argument("--body", help="text of the message")
        p.add_argument("--body-file", help="file with the text, or - for standard input")
        p.add_argument("--subject")
        p.add_argument(
            "--internal", action="store_true", help="internal note, hidden from the customer"
        )

    p = sub.add_parser("create", help="create a ticket")
    p.add_argument("--title", required=True)
    p.add_argument("--group", required=True, help="group name, for example Users")
    p.add_argument("--customer", required=True, help="email or login of the customer")
    p.add_argument("--type", default="note", help="article type: note, email, phone, web")
    p.add_argument("--state", help="for example new or open")
    p.add_argument("--priority", help="for example '2 normal'")
    text(p)
    p.set_defaults(run=cmd_create)
    p = sub.add_parser("reply", help="add a message to a ticket")
    p.add_argument("id")
    p.add_argument("--type", default="note", help="note (default), email, phone")
    p.add_argument("--to", help="recipient for type email")
    text(p)
    p.set_defaults(run=cmd_reply)
    p = sub.add_parser("set-state", help="set the state of a ticket")
    p.add_argument("id")
    p.add_argument("--state", required=True, help="state name, see the states command")
    p.set_defaults(run=cmd_set_state)
    p = sub.add_parser("states", help="list the ticket states")
    p.set_defaults(run=cmd_states)
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
