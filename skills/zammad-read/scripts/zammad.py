#!/usr/bin/env python3
"""Read Zammad: search and read tickets, search the knowledge base. Read only.

Needs ZAMMAD_URL (https://support.example.com) and ZAMMAD_TOKEN (a personal
access token). Output is JSON on stdout. An error is JSON on stderr with exit
code 1.
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
from html.parser import HTMLParser


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


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Read Zammad. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)
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
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
