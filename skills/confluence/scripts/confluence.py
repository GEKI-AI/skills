#!/usr/bin/env python3
"""Confluence Cloud: search and read pages, create and update pages, add comments.

Needs CONFLUENCE_URL (https://your-site.atlassian.net) and CONFLUENCE_TOKEN
(an API token, or email:token in one value). Page text is Markdown by default
and is converted to and from Confluence storage format. Output is JSON on
stdout. An error is JSON on stderr with exit code 1.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
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


def site() -> str:
    url = setting("CONFLUENCE_URL").rstrip("/")
    return url[: -len("/wiki")] if url.endswith("/wiki") else url


def auth() -> str:
    token = setting("CONFLUENCE_TOKEN")
    email = os.environ.get("CONFLUENCE_EMAIL", "").strip()
    pair = f"{email}:{token}" if email else token
    return "Basic " + base64.b64encode(pair.encode()).decode()


def call(method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = f"{site()}{path}" + (f"?{query}" if query else "")
    headers = {"Authorization": auth(), "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        fail(f"Confluence answered {exc.code}", exc.code, detail)
    except urllib.error.URLError as exc:
        fail(f"cannot reach Confluence: {exc.reason}")
    return {}


def cursor_of(data: dict) -> str | None:
    link = (data.get("_links") or {}).get("next")
    if not link:
        return None
    return urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("cursor", [None])[0]


class Markdown(HTMLParser):
    """Confluence storage format to Markdown. Handles the common elements."""

    BLOCKS = {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "table",
        "tr",
        "pre",
        "blockquote",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.lists: list[str] = []
        self.href: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []
        self.cell: list[str] | None = None
        self.code_block = False
        self.macro: list[str] = []

    def put(self, text: str) -> None:
        (self.cell if self.cell is not None else self.out).append(text)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self.put("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in {"p", "div"}:
            self.put("\n\n")
        elif tag == "br":
            self.put("\n")
        elif tag in {"strong", "b"}:
            self.put("**")
        elif tag in {"em", "i"}:
            self.put("_")
        elif tag == "code":
            self.put("`")
        elif tag in {"ul", "ol"}:
            self.lists.append(tag)
            self.put("\n")
        elif tag == "li":
            indent = "  " * (len(self.lists) - 1)
            self.put(f"\n{indent}{'1.' if self.lists and self.lists[-1] == 'ol' else '-'} ")
        elif tag == "a":
            self.href.append(a.get("href") or "")
            self.put("[")
        elif tag == "table":
            self.rows = []
        elif tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell = []
        elif tag == "pre":
            self.put("\n\n```\n")
            self.code_block = True
        elif tag == "blockquote":
            self.put("\n\n> ")
        elif tag == "hr":
            self.put("\n\n---\n\n")
        elif tag == "ac:structured-macro":
            self.macro.append(a.get("ac:name") or "")
        elif tag == "ac:plain-text-body" and self.macro and self.macro[-1] == "code":
            self.put("\n\n```\n")
        elif tag == "ac:image":
            self.put("[image]")
        elif tag == "time":
            self.put(a.get("datetime") or "")

    def handle_endtag(self, tag: str) -> None:
        if re.fullmatch(r"h[1-6]", tag) or tag in {"p", "div"}:
            self.put("\n")
        elif tag in {"strong", "b"}:
            self.put("**")
        elif tag in {"em", "i"}:
            self.put("_")
        elif tag == "code":
            self.put("`")
        elif tag in {"ul", "ol"}:
            if self.lists:
                self.lists.pop()
            self.put("\n")
        elif tag == "a":
            href = self.href.pop() if self.href else ""
            self.put(f"]({href})" if href else "]")
        elif tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()).replace("|", "\\|"))
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)
        elif tag == "table":
            self.flush_table()
        elif tag == "pre":
            self.put("\n```\n")
            self.code_block = False
        elif tag == "ac:plain-text-body" and self.macro and self.macro[-1] == "code":
            self.put("\n```\n")
        elif tag == "ac:structured-macro" and self.macro:
            self.macro.pop()

    def flush_table(self) -> None:
        rows = [r for r in self.rows if r]
        if rows:
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
            lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
            self.out.append("\n\n" + "\n".join(lines) + "\n")
        self.rows = []

    def handle_data(self, data: str) -> None:
        if self.code_block or (self.macro and self.macro[-1] == "code"):
            self.put(data)
        else:
            self.put(re.sub(r"\s+", " ", data))

    def unknown_decl(self, data: str) -> None:
        if data.startswith("CDATA["):
            self.put(data[len("CDATA[") :])

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.out)).strip() + "\n"


def to_markdown(storage: str) -> str:
    parser = Markdown()
    parser.feed(storage)
    parser.close()
    return parser.text()


def page_view(page: dict, body_format: str) -> dict:
    storage = ((page.get("body") or {}).get("storage") or {}).get("value", "")
    links = page.get("_links") or {}
    body = storage if body_format == "storage" else to_markdown(storage)
    return {
        "id": page.get("id"),
        "title": page.get("title"),
        "spaceId": page.get("spaceId"),
        "parentId": page.get("parentId"),
        "version": (page.get("version") or {}).get("number"),
        "url": (links.get("base", "") + links.get("webui", "")) or None,
        "body": body,
        "bodyFormat": body_format,
    }


def inline(text: str) -> str:
    """Bold, italic, code and links inside one line of Markdown."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        part = html.escape(part, quote=False)
        part = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f'<a href="{html.escape(m[2])}">{m[1]}</a>',
            part,
        )
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])", r"<em>\1</em>", part)
        out.append(part)
    return "".join(out)


def code_macro(language: str, lines: list[str]) -> str:
    lang = (
        f'<ac:parameter ac:name="language">{html.escape(language)}</ac:parameter>'
        if language
        else ""
    )
    text = "\n".join(lines).replace("]]>", "]]]]><![CDATA[>")
    return (
        f'<ac:structured-macro ac:name="code">{lang}'
        f"<ac:plain-text-body><![CDATA[{text}]]></ac:plain-text-body></ac:structured-macro>"
    )


def table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]
    head, *body = cells
    out = "<table><tbody><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
    for row in body:
        out += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>"
    return out + "</tbody></table>"


def list_html(items: list[tuple[int, str, str]]) -> str:
    """Nested lists from (indent, kind, text) rows. Kind is ul or ol."""
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    for indent, kind, text in items:
        while stack and indent < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if stack and indent == stack[-1][0]:
            out.append("</li>")
        elif not stack or indent > stack[-1][0]:
            stack.append((indent, kind))
            out.append(f"<{kind}>")
        out.append(f"<li>{inline(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def to_storage(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = re.match(r"^```(\w*)\s*$", line)
        if fence:
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            out.append(code_macro(fence.group(1), block))
            i += 1
        elif re.match(r"^#{1,6} ", line):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
            i += 1
        elif (
            line.strip().startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1])
        ):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows))
        elif re.match(r"^\s*([-*]|\d+\.) ", line):
            found = []
            while i < len(lines) and (m := re.match(r"^(\s*)([-*]|\d+\.) (.*)$", lines[i])):
                found.append(
                    (len(m[1].replace("\t", "  ")), "ol" if m[2][0].isdigit() else "ul", m[3])
                )
                i += 1
            out.append(list_html(found))
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote><p>{inline(' '.join(quote))}</p></blockquote>")
        elif re.fullmatch(r"-{3,}|\*{3,}", line.strip()):
            out.append("<hr/>")
            i += 1
        elif not line.strip():
            i += 1
        else:
            para = []
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#{1,6} |```|\s*([-*]|\d+\.) |>|\|)", lines[i])
            ):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "".join(out)


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        text = (
            sys.stdin.read()
            if args.body_file == "-"
            else Path(args.body_file).read_text(encoding="utf-8")
        )
    elif args.body is not None:
        text = args.body
    else:
        fail("give the text with --body or --body-file")
    return text if args.format == "storage" else to_storage(text)


def space_id(key_or_id: str) -> str:
    if key_or_id.isdigit():
        return key_or_id
    data = call("GET", "/wiki/api/v2/spaces", {"keys": key_or_id, "limit": 1})
    results = data.get("results") or []
    if not results:
        fail(f"no space with key {key_or_id}")
    return str(results[0]["id"])


def listing(data: dict, fields: tuple[str, ...]) -> dict:
    rows = [{f: item.get(f) for f in fields} for item in data.get("results") or []]
    return {"results": rows, "next": cursor_of(data)}


def cmd_spaces(args: argparse.Namespace) -> None:
    data = call("GET", "/wiki/api/v2/spaces", {"limit": args.limit, "cursor": args.cursor})
    print(json.dumps(listing(data, ("id", "key", "name", "type", "status"))))


def cmd_pages(args: argparse.Namespace) -> None:
    sid = space_id(args.space)
    data = call(
        "GET",
        f"/wiki/api/v2/spaces/{sid}/pages",
        {"limit": args.limit, "cursor": args.cursor, "title": args.title, "status": "current"},
    )
    print(json.dumps(listing(data, ("id", "title", "parentId", "status"))))


def cmd_children(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"/wiki/api/v2/pages/{args.id}/children",
        {"limit": args.limit, "cursor": args.cursor},
    )
    print(json.dumps(listing(data, ("id", "title", "status"))))


def cmd_page(args: argparse.Namespace) -> None:
    page = call("GET", f"/wiki/api/v2/pages/{args.id}", {"body-format": "storage"})
    print(json.dumps(page_view(page, args.format)))


def cmd_search(args: argparse.Namespace) -> None:
    if args.cql:
        cql = args.cql
    else:
        words = args.text.replace('"', " ").strip()
        cql = f'type = page AND text ~ "{words}"'
    data = call(
        "GET", "/wiki/rest/api/search", {"cql": cql, "limit": args.limit, "start": args.start}
    )
    rows = []
    for item in data.get("results") or []:
        content = item.get("content") or {}
        rows.append(
            {
                "id": content.get("id"),
                "type": content.get("type") or item.get("entityType"),
                "title": html.unescape(re.sub(r"@@@(?:end)?hl@@@", "", item.get("title") or "")),
                "excerpt": html.unescape(
                    re.sub(r"@@@(?:end)?hl@@@", "", item.get("excerpt") or "")
                ),
                "space": (item.get("resultGlobalContainer") or {}).get("title"),
                "url": item.get("url"),
                "lastModified": item.get("friendlyLastModified"),
            }
        )
    print(json.dumps({"results": rows, "total": data.get("totalSize"), "cql": cql}))


def result_view(page: dict) -> dict:
    links = page.get("_links") or {}
    return {
        "id": page.get("id"),
        "title": page.get("title"),
        "version": (page.get("version") or {}).get("number"),
        "url": (links.get("base", "") + links.get("webui", "")) or None,
    }


def cmd_create(args: argparse.Namespace) -> None:
    body: dict = {
        "spaceId": space_id(args.space),
        "status": "draft" if args.draft else "current",
        "title": args.title,
        "body": {"representation": "storage", "value": read_body(args)},
    }
    if args.parent:
        body["parentId"] = args.parent
    print(json.dumps(result_view(call("POST", "/wiki/api/v2/pages", body=body))))


def cmd_update(args: argparse.Namespace) -> None:
    current = call("GET", f"/wiki/api/v2/pages/{args.id}")
    number = (current.get("version") or {}).get("number") or 0
    version: dict = {"number": number + 1}
    if args.message:
        version["message"] = args.message
    body = {
        "id": args.id,
        "status": "current",
        "title": args.title or current.get("title"),
        "body": {"representation": "storage", "value": read_body(args)},
        "version": version,
    }
    print(json.dumps(result_view(call("PUT", f"/wiki/api/v2/pages/{args.id}", body=body))))


def cmd_comment(args: argparse.Namespace) -> None:
    body = {"pageId": args.id, "body": {"representation": "storage", "value": read_body(args)}}
    data = call("POST", "/wiki/api/v2/footer-comments", body=body)
    print(json.dumps({"id": data.get("id"), "pageId": data.get("pageId") or args.id}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Confluence Cloud pages. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)

    def paging(p: argparse.ArgumentParser) -> None:
        p.add_argument("--limit", type=int, default=25)
        p.add_argument("--cursor", help="the `next` value of the previous result")

    def text(p: argparse.ArgumentParser) -> None:
        p.add_argument("--body", help="text of the page")
        p.add_argument("--body-file", help="file with the text, or - for standard input")
        p.add_argument("--format", choices=["markdown", "storage"], default="markdown")

    p = sub.add_parser("spaces", help="list spaces")
    paging(p)
    p.set_defaults(run=cmd_spaces)
    p = sub.add_parser("pages", help="list the pages of a space")
    p.add_argument("--space", required=True, help="space key or id")
    p.add_argument("--title", help="exact page title")
    paging(p)
    p.set_defaults(run=cmd_pages)
    p = sub.add_parser("children", help="list the child pages of a page")
    p.add_argument("id")
    paging(p)
    p.set_defaults(run=cmd_children)
    p = sub.add_parser("page", help="read one page")
    p.add_argument("id")
    p.add_argument("--format", choices=["markdown", "storage"], default="markdown")
    p.set_defaults(run=cmd_page)
    p = sub.add_parser("search", help="search with CQL or plain text")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--cql", help='for example: space = DOCS AND title ~ "onboarding"')
    group.add_argument("--text", help="words to find in pages")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--start", type=int, default=0)
    p.set_defaults(run=cmd_search)
    p = sub.add_parser("create", help="create a page")
    p.add_argument("--space", required=True, help="space key or id")
    p.add_argument("--title", required=True)
    p.add_argument("--parent", help="id of the parent page")
    p.add_argument("--draft", action="store_true", help="save as draft, not published")
    text(p)
    p.set_defaults(run=cmd_create)
    p = sub.add_parser("update", help="replace the text of a page")
    p.add_argument("id")
    p.add_argument("--title", help="new title, default: keep")
    p.add_argument("--message", help="version message")
    text(p)
    p.set_defaults(run=cmd_update)
    p = sub.add_parser("comment", help="add a comment at the bottom of a page")
    p.add_argument("id")
    text(p)
    p.set_defaults(run=cmd_comment)
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
