#!/usr/bin/env python3
"""Support work in Zammad: find, read and answer tickets, change them, use the knowledge base.

Needs ZAMMAD_URL (https://support.example.com) and ZAMMAD_TOKEN (a personal
access token). Output is JSON on stdout. An error is JSON on stderr with exit
code 1.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


def fail(message: str, status: int | None = None, detail: object = None) -> None:
    print(json.dumps({"error": message, "status": status, "detail": detail}), file=sys.stderr)
    sys.exit(1)


def setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"{name} is not set. See references/setup.md.")
    return value


def send(method: str, path: str, params: dict | None = None, body: dict | None = None) -> bytes:
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
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        fail(f"Zammad answered {exc.code}", exc.code, exc.read().decode("utf-8", "replace")[:500])
    except urllib.error.URLError as exc:
        fail(f"cannot reach Zammad: {exc.reason}")
    return b""


def request(method: str, path: str, params: dict | None = None, body: dict | None = None):
    return json.loads(send(method, path, params, body) or b"null")


class Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain(text: str | None, content_type: str = "text/html") -> str:
    if not text:
        return ""
    if "html" in content_type or re.search(r"<(p|div|br|span|a)\b", text):
        parser = Text()
        parser.feed(text)
        text = "".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ticket_row(ticket: dict) -> dict:
    keys = (
        "id",
        "number",
        "title",
        "state",
        "priority",
        "group",
        "customer",
        "owner",
        "organization",
        "pending_time",
        "time_unit",
        "created_at",
        "updated_at",
    )
    return {key: ticket.get(key) for key in keys}


def article_row(article: dict) -> dict:
    return {
        "id": article.get("id"),
        "from": article.get("from"),
        "to": article.get("to"),
        "type": article.get("type"),
        "sender": article.get("sender"),
        "internal": article.get("internal"),
        "created_at": article.get("created_at"),
        "subject": article.get("subject"),
        "body": plain(article.get("body"), article.get("content_type") or "text/plain"),
        "attachments": [
            {"id": a.get("id"), "filename": a.get("filename"), "size": a.get("size")}
            for a in article.get("attachments") or []
        ],
    }


def cmd_search(args: argparse.Namespace) -> None:
    data = request(
        "GET",
        "/api/v1/tickets/search",
        {
            "query": args.query,
            "limit": args.limit,
            "expand": "true",
            "sort_by": "updated_at",
            "order_by": "desc",
        },
    )
    rows = data if isinstance(data, list) else (data or {}).get("tickets", [])
    print(json.dumps({"results": [ticket_row(t) for t in rows if isinstance(t, dict)]}))


def cmd_ticket(args: argparse.Namespace) -> None:
    ticket = request("GET", f"/api/v1/tickets/{args.id}", {"expand": "true"})
    articles = (
        request("GET", f"/api/v1/ticket_articles/by_ticket/{args.id}", {"expand": "true"}) or []
    )
    rows = [article_row(a) for a in articles if args.internal or not a.get("internal")]
    print(json.dumps({**ticket_row(ticket), "articles": rows}))


def cmd_kb_search(args: argparse.Namespace) -> None:
    body = {"query": args.query, "flavor": "agent", "limit": args.limit}
    if args.kb:
        body["knowledge_base_id"] = args.kb
    if args.locale:
        body["locale"] = args.locale
    data = request("POST", "/api/v1/knowledge_bases/search", body=body) or {}
    rows = []
    for item in data.get("details") or []:
        rows.append(
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "title": plain(item.get("title")),
                "subtitle": plain(item.get("subtitle")),
                "url": item.get("url"),
            }
        )
    print(json.dumps({"results": rows}))


def cmd_kb_answer(args: argparse.Namespace) -> None:
    data = (
        request("GET", f"/api/v1/knowledge_bases/{args.kb}/answers/{args.id}", {"full": "true"})
        or {}
    )
    assets = data.get("assets") or {}
    translations = (assets.get("KnowledgeBaseAnswerTranslation") or {}).values()
    contents = assets.get("KnowledgeBaseAnswerTranslationContent") or {}
    answers = []
    for item in translations:
        content = contents.get(str(item.get("content_id"))) or {}
        answers.append(
            {
                "title": item.get("title"),
                "locale_id": item.get("kb_locale_id"),
                "body": plain(content.get("body")),
            }
        )
    print(json.dumps({"id": args.id, "translations": answers}))


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


def changed_ticket(ticket: dict) -> dict:
    keys = ("id", "number", "title", "state", "priority", "group", "customer", "owner")
    return {key: ticket.get(key) for key in keys if key in ticket}


def cmd_attachment(args: argparse.Namespace) -> None:
    path = f"/api/v1/ticket_attachment/{args.ticket}/{args.article}/{args.attachment}"
    data = send("GET", path)
    Path(args.output).write_bytes(data)
    print(json.dumps({"saved": args.output, "size": len(data)}))


def cmd_users(args: argparse.Namespace) -> None:
    rows = request(
        "GET", "/api/v1/users/search", {"query": args.query, "limit": args.limit, "expand": "true"}
    )
    keys = ("id", "login", "firstname", "lastname", "email", "phone", "organization", "active")
    print(json.dumps({"results": [{k: u.get(k) for k in keys} for u in rows or []]}))


def named_list(path: str) -> None:
    rows = request("GET", path) or []
    print(json.dumps({"results": [{k: r.get(k) for k in ("id", "name", "active")} for r in rows]}))


def cmd_states(_args: argparse.Namespace) -> None:
    named_list("/api/v1/ticket_states")


def cmd_priorities(_args: argparse.Namespace) -> None:
    named_list("/api/v1/ticket_priorities")


def cmd_create(args: argparse.Namespace) -> None:
    article = {
        "subject": args.title,
        "body": read_body(args),
        "type": args.type,
        "internal": False,
        "content_type": "text/plain",
    }
    if args.from_customer:
        article["sender"] = "Customer"
    body = {"title": args.title, "group": args.group, "customer": args.customer, "article": article}
    for key in ("state", "priority", "owner"):
        if getattr(args, key):
            body[key] = getattr(args, key)
    print(json.dumps(changed_ticket(request("POST", "/api/v1/tickets", {"expand": "true"}, body))))


def attachment_rows(paths: list[str]) -> list[dict]:
    rows = []
    for name in paths:
        path = Path(name)
        if not path.is_file():
            fail(f"no such file: {name}")
        rows.append(
            {
                "filename": path.name,
                "data": base64.b64encode(path.read_bytes()).decode(),
                "mime-type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            }
        )
    return rows


def cmd_reply(args: argparse.Namespace) -> None:
    if args.type == "email" and not args.to:
        fail("an email needs a recipient: give --to")
    if args.type == "email" and args.internal:
        fail("Zammad sends an internal email to its recipient anyway: drop --internal")
    body = {
        "ticket_id": int(args.id),
        "body": read_body(args),
        "type": args.type,
        "internal": args.internal,
        "sender": "Agent",
        "content_type": "text/plain",
    }
    for key in ("subject", "to", "cc"):
        if getattr(args, key):
            body[key] = getattr(args, key)
    if args.time is not None:
        body["time_unit"] = args.time
    if args.attach:
        body["attachments"] = attachment_rows(args.attach)
    article = request("POST", "/api/v1/ticket_articles", body=body)
    keys = ("id", "ticket_id", "type", "internal", "to", "cc")
    print(json.dumps({key: article.get(key) for key in keys}))


def cmd_update(args: argparse.Namespace) -> None:
    fields = {
        "title": args.title,
        "state": args.state,
        "priority": args.priority,
        "group": args.group,
        "owner": args.owner,
        "pending_time": args.pending_time,
    }
    body = {key: value for key, value in fields.items() if value is not None}
    if not body:
        fail(
            "nothing to change: give --state, --priority, --owner, --group, --title or --pending-time"
        )
    ticket = request("PUT", f"/api/v1/tickets/{args.id}", {"expand": "true"}, body)
    print(json.dumps(changed_ticket(ticket)))


def cmd_tags(args: argparse.Namespace) -> None:
    data = request("GET", "/api/v1/tags", {"object": "Ticket", "o_id": args.id}) or {}
    print(json.dumps({"tags": data.get("tags") or []}))


def tag_body(args: argparse.Namespace) -> dict:
    return {"item": args.tag, "object": "Ticket", "o_id": int(args.id)}


def cmd_tag_add(args: argparse.Namespace) -> None:
    request("POST", "/api/v1/tags/add", body=tag_body(args))
    print(json.dumps({"ticket_id": int(args.id), "added": args.tag}))


def cmd_tag_remove(args: argparse.Namespace) -> None:
    request("DELETE", "/api/v1/tags/remove", body=tag_body(args))
    print(json.dumps({"ticket_id": int(args.id), "removed": args.tag}))


def cmd_links(args: argparse.Namespace) -> None:
    data = (
        request("GET", "/api/v1/links", {"link_object": "Ticket", "link_object_value": args.id})
        or {}
    )
    tickets = (data.get("assets") or {}).get("Ticket") or {}
    rows = []
    for link in data.get("links") or []:
        other = tickets.get(str(link.get("link_object_value"))) or {}
        rows.append(
            {
                "type": link.get("link_type"),
                "id": link.get("link_object_value"),
                "number": other.get("number"),
                "title": other.get("title"),
            }
        )
    print(json.dumps({"results": rows}))


def cmd_link_add(args: argparse.Namespace) -> None:
    body = {
        "link_type": args.type,
        "link_object_target": "Ticket",
        "link_object_target_value": int(args.id),
        "link_object_source": "Ticket",
        "link_object_source_number": args.number,
    }
    link = request("POST", "/api/v1/links/add", body=body) or {}
    print(json.dumps({"id": link.get("id"), "ticket_id": int(args.id), "linked": args.number}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Support work in Zammad. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)

    def text(p: argparse.ArgumentParser) -> None:
        p.add_argument("--body", help="text of the message")
        p.add_argument("--body-file", help="file with the text, or - for standard input")

    p = sub.add_parser("search", help="search tickets")
    p.add_argument("query", help='for example: state.name:open AND title:"printer"')
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(run=cmd_search)
    p = sub.add_parser("ticket", help="read a ticket with its articles")
    p.add_argument("id")
    p.add_argument("--internal", action="store_true", help="include internal notes")
    p.set_defaults(run=cmd_ticket)
    p = sub.add_parser("kb-search", help="search the knowledge base")
    p.add_argument("query")
    p.add_argument("--kb", help="knowledge base id")
    p.add_argument("--locale", help="for example en-us")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(run=cmd_kb_search)
    p = sub.add_parser("kb-answer", help="read one knowledge base answer")
    p.add_argument("id")
    p.add_argument("--kb", required=True, help="knowledge base id")
    p.set_defaults(run=cmd_kb_answer)
    p = sub.add_parser("attachment", help="save an attachment of an article to a file")
    p.add_argument("ticket")
    p.add_argument("article")
    p.add_argument("attachment")
    p.add_argument("--output", required=True, help="file to write")
    p.set_defaults(run=cmd_attachment)
    p = sub.add_parser("users", help="find customers and colleagues")
    p.add_argument("query", help="name, email or login")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(run=cmd_users)
    p = sub.add_parser("states", help="list the ticket states")
    p.set_defaults(run=cmd_states)
    p = sub.add_parser("priorities", help="list the ticket priorities")
    p.set_defaults(run=cmd_priorities)
    p = sub.add_parser("create", help="create a ticket")
    p.add_argument("--title", required=True)
    p.add_argument("--group", required=True, help="group name, for example Users")
    p.add_argument("--customer", required=True, help="email or login of the customer")
    p.add_argument("--type", choices=["note", "phone"], default="note")
    p.add_argument("--from-customer", action="store_true", help="the text comes from the customer")
    p.add_argument("--state", help="for example new or open")
    p.add_argument("--priority", help="for example '2 normal'")
    p.add_argument("--owner", help="email or login of the agent")
    text(p)
    p.set_defaults(run=cmd_create)
    p = sub.add_parser("reply", help="add a message to a ticket")
    p.add_argument("id")
    p.add_argument("--type", choices=["note", "email", "phone"], default="note")
    p.add_argument("--to", help="recipient for type email")
    p.add_argument("--cc", help="copy for type email")
    p.add_argument("--subject")
    p.add_argument("--internal", action="store_true", help="hidden from the customer")
    p.add_argument("--time", help="time spent, in the unit of your instance, for example 15")
    p.add_argument("--attach", action="append", metavar="FILE", help="file to attach, repeatable")
    text(p)
    p.set_defaults(run=cmd_reply)
    p = sub.add_parser("update", help="change the fields of a ticket")
    p.add_argument("id")
    p.add_argument("--title")
    p.add_argument("--state", help="state name, see the states command")
    p.add_argument("--priority", help="priority name, see the priorities command")
    p.add_argument("--group", help="group name")
    p.add_argument("--owner", help="email or login of the agent")
    p.add_argument("--pending-time", help="for pending states, for example 2026-12-01T09:00:00Z")
    p.set_defaults(run=cmd_update)
    p = sub.add_parser("tags", help="list the tags of a ticket")
    p.add_argument("id")
    p.set_defaults(run=cmd_tags)
    p = sub.add_parser("tag-add", help="add a tag to a ticket")
    p.add_argument("id")
    p.add_argument("tag")
    p.set_defaults(run=cmd_tag_add)
    p = sub.add_parser("tag-remove", help="remove a tag from a ticket")
    p.add_argument("id")
    p.add_argument("tag")
    p.set_defaults(run=cmd_tag_remove)
    p = sub.add_parser("links", help="list the tickets linked to a ticket")
    p.add_argument("id")
    p.set_defaults(run=cmd_links)
    p = sub.add_parser("link-add", help="link another ticket to a ticket")
    p.add_argument("id", help="id of the ticket")
    p.add_argument("number", help="number of the other ticket")
    p.add_argument("--type", choices=["normal", "parent", "child"], default="normal")
    p.set_defaults(run=cmd_link_add)
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
