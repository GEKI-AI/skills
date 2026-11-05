#!/usr/bin/env python3
"""Create tickets in Zammad. It cannot read or change existing tickets.

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


def request(method: str, path: str, body: dict | None = None):
    url = setting("ZAMMAD_URL").rstrip("/") + path
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


def cmd_create(args: argparse.Namespace) -> None:
    article = {
        "subject": args.title,
        "body": read_body(args),
        "type": "note",
        "internal": False,
        "content_type": "text/plain",
    }
    body = {"title": args.title, "group": args.group, "article": article}
    if args.customer:
        body["customer"] = args.customer
        # Zammad needs this on behalf of a customer. It cannot be changed later.
        article["sender"] = "Customer"
    if args.priority:
        body["priority"] = args.priority
    ticket = request("POST", "/api/v1/tickets", body)
    print(json.dumps({key: ticket.get(key) for key in ("id", "number", "title")}))


def cmd_me(_args: argparse.Namespace) -> None:
    user = request("GET", "/api/v1/users/me") or {}
    print(json.dumps({key: user.get(key) for key in ("id", "login", "firstname", "lastname")}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Create Zammad tickets. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create", help="create a ticket")
    p.add_argument("--title", required=True)
    p.add_argument("--group", required=True, help="group name, for example Users")
    p.add_argument("--customer", help="email or login, default: the owner of the token")
    p.add_argument("--priority", help="for example '3 high'")
    p.add_argument("--body", help="text of the first message")
    p.add_argument("--body-file", help="file with the text, or - for standard input")
    p.set_defaults(run=cmd_create)
    p = sub.add_parser("me", help="the user of the token, to check the connection")
    p.set_defaults(run=cmd_me)
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
