#!/usr/bin/env python3
"""GitHub issues, pull requests, comments and files through the REST API.

Needs GITHUB_TOKEN (a personal access token or a fine-grained token). The API
address comes from GITHUB_BASE_URL and defaults to https://api.github.com.
Output is JSON on stdout. An error is JSON on stderr with exit code 1.
"""

from __future__ import annotations

import argparse
import base64
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


def token() -> str:
    value = os.environ.get("GITHUB_TOKEN", "").strip()
    if not value:
        fail("GITHUB_TOKEN is not set. See references/setup.md.")
    return value


def call(method: str, path: str, params: dict | None = None, body: dict | None = None):
    base = os.environ.get("GITHUB_BASE_URL", "").strip() or "https://api.github.com"
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = base.rstrip("/") + path + (f"?{query}" if query else "")
    headers = {
        "Authorization": f"Bearer {token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "geki-skills-github",
    }
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
        fail(f"GitHub answered {exc.code}", exc.code, detail)
    except urllib.error.URLError as exc:
        fail(f"cannot reach GitHub: {exc.reason}")


def repo_path(repo: str) -> str:
    owner, _, name = repo.partition("/")
    if not owner or not name or "/" in name:
        fail("the repository must look like owner/name")
    return f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}"


def user(item: dict | None) -> str | None:
    return (item or {}).get("login")


def issue_row(item: dict) -> dict:
    return {
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "author": user(item.get("user")),
        "labels": [label.get("name") for label in item.get("labels") or []],
        "assignees": [user(a) for a in item.get("assignees") or []],
        "comments": item.get("comments"),
        "url": item.get("html_url"),
        "updated_at": item.get("updated_at"),
        "is_pull_request": "pull_request" in item,
    }


def comment_row(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "author": user(item.get("user")),
        "body": item.get("body"),
        "created_at": item.get("created_at"),
        "url": item.get("html_url"),
    }


def per_page(limit: int) -> int:
    return max(1, min(limit, 100))


def read_text(args: argparse.Namespace) -> str | None:
    if getattr(args, "body_file", None):
        return (
            sys.stdin.read()
            if args.body_file == "-"
            else Path(args.body_file).read_text(encoding="utf-8")
        )
    return args.body


def csv(value: str | None) -> list[str] | None:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


def cmd_issues(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"{repo_path(args.repo)}/issues",
        {
            "state": args.state,
            "labels": args.labels,
            "assignee": args.assignee,
            "per_page": per_page(args.limit),
        },
    )
    rows = [issue_row(i) for i in data if args.include_prs or "pull_request" not in i]
    print(json.dumps({"results": rows[: args.limit]}))


def cmd_issue(args: argparse.Namespace) -> None:
    base = repo_path(args.repo)
    item = call("GET", f"{base}/issues/{args.number}")
    comments = call("GET", f"{base}/issues/{args.number}/comments", {"per_page": 100})
    print(
        json.dumps(
            {
                **issue_row(item),
                "body": item.get("body"),
                "comment_list": [comment_row(c) for c in comments],
            }
        )
    )


def cmd_issue_create(args: argparse.Namespace) -> None:
    body: dict = {"title": args.title}
    text = read_text(args)
    if text is not None:
        body["body"] = text
    if args.labels:
        body["labels"] = csv(args.labels)
    if args.assignees:
        body["assignees"] = csv(args.assignees)
    print(json.dumps(issue_row(call("POST", f"{repo_path(args.repo)}/issues", body=body))))


def cmd_issue_update(args: argparse.Namespace) -> None:
    body: dict = {}
    if args.state:
        body["state"] = args.state
    if args.title:
        body["title"] = args.title
    text = read_text(args)
    if text is not None:
        body["body"] = text
    if args.labels is not None:
        body["labels"] = csv(args.labels) or []
    if not body:
        fail("nothing to change: give --state, --title, --body or --labels")
    print(
        json.dumps(
            issue_row(call("PATCH", f"{repo_path(args.repo)}/issues/{args.number}", body=body))
        )
    )


def cmd_comment(args: argparse.Namespace) -> None:
    text = read_text(args)
    if text is None:
        fail("give the text with --body or --body-file")
    item = call(
        "POST", f"{repo_path(args.repo)}/issues/{args.number}/comments", body={"body": text}
    )
    print(json.dumps(comment_row(item)))


def pr_row(item: dict) -> dict:
    return {
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "draft": item.get("draft"),
        "merged": item.get("merged"),
        "author": user(item.get("user")),
        "head": (item.get("head") or {}).get("ref"),
        "base": (item.get("base") or {}).get("ref"),
        "url": item.get("html_url"),
        "updated_at": item.get("updated_at"),
    }


def cmd_prs(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"{repo_path(args.repo)}/pulls",
        {"state": args.state, "per_page": per_page(args.limit)},
    )
    print(json.dumps({"results": [pr_row(p) for p in data][: args.limit]}))


def cmd_pr(args: argparse.Namespace) -> None:
    item = call("GET", f"{repo_path(args.repo)}/pulls/{args.number}")
    print(
        json.dumps(
            {
                **pr_row(item),
                "body": item.get("body"),
                "changed_files": item.get("changed_files"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
            }
        )
    )


def cmd_pr_create(args: argparse.Namespace) -> None:
    body = {"head": args.head, "base": args.base, "title": args.title}
    text = read_text(args)
    if text is not None:
        body["body"] = text
    print(json.dumps(pr_row(call("POST", f"{repo_path(args.repo)}/pulls", body=body))))


def cmd_pr_files(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"{repo_path(args.repo)}/pulls/{args.number}/files",
        {"per_page": per_page(args.limit)},
    )
    rows = []
    for item in data:
        patch = item.get("patch") or ""
        rows.append(
            {
                "filename": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
                "patch": patch[: args.max_patch],
                "patch_cut": len(patch) > args.max_patch,
            }
        )
    print(json.dumps({"results": rows}))


def cmd_file(args: argparse.Namespace) -> None:
    path = "/".join(urllib.parse.quote(part) for part in args.path.strip("/").split("/"))
    data = call("GET", f"{repo_path(args.repo)}/contents/{path}", {"ref": args.ref})
    if isinstance(data, list):
        rows = [
            {
                "name": i.get("name"),
                "path": i.get("path"),
                "type": i.get("type"),
                "size": i.get("size"),
            }
            for i in data
        ]
        print(json.dumps({"type": "dir", "entries": rows}))
        return
    content = data.get("content") or ""
    if data.get("encoding") == "base64":
        content = base64.b64decode(content).decode("utf-8", "replace")
    print(
        json.dumps(
            {
                "type": "file",
                "path": data.get("path"),
                "sha": data.get("sha"),
                "size": data.get("size"),
                "content": content,
            }
        )
    )


def cmd_search(args: argparse.Namespace) -> None:
    data = call("GET", "/search/issues", {"q": args.query, "per_page": per_page(args.limit)})
    print(
        json.dumps(
            {
                "total": data.get("total_count"),
                "results": [issue_row(i) for i in data.get("items") or []],
            }
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="GitHub issues, pull requests, comments, files. JSON output."
    )
    sub = root.add_subparsers(dest="command", required=True)

    def add(name: str, run, help_text: str, repo: bool = True, number: bool = False):
        p = sub.add_parser(name, help=help_text)
        if repo:
            p.add_argument("repo", help="owner/name")
        if number:
            p.add_argument("number", type=int)
        p.set_defaults(run=run)
        return p

    def text(p: argparse.ArgumentParser) -> None:
        p.add_argument("--body", help="text")
        p.add_argument("--body-file", help="file with the text, or - for standard input")

    p = add("issues", cmd_issues, "list issues")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p.add_argument("--labels", help="comma-separated")
    p.add_argument("--assignee")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--include-prs", action="store_true")
    add("issue", cmd_issue, "read an issue with its comments", number=True)
    p = add("issue-create", cmd_issue_create, "create an issue")
    p.add_argument("--title", required=True)
    p.add_argument("--labels", help="comma-separated")
    p.add_argument("--assignees", help="comma-separated logins")
    text(p)
    p = add("issue-update", cmd_issue_update, "change an issue", number=True)
    p.add_argument("--state", choices=["open", "closed"])
    p.add_argument("--title")
    p.add_argument("--labels", help="comma-separated, replaces all labels")
    text(p)
    p = add("comment", cmd_comment, "comment on an issue or pull request", number=True)
    text(p)
    p = add("prs", cmd_prs, "list pull requests")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p.add_argument("--limit", type=int, default=20)
    add("pr", cmd_pr, "read a pull request", number=True)
    p = add("pr-create", cmd_pr_create, "create a pull request from a pushed branch")
    p.add_argument("--head", required=True, help="the pushed branch")
    p.add_argument("--base", required=True, help="the branch to merge into")
    p.add_argument("--title", required=True)
    text(p)
    p = add("pr-files", cmd_pr_files, "files changed by a pull request", number=True)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--max-patch", type=int, default=4000, help="characters of diff per file")
    p = add("file", cmd_file, "read a file or list a folder")
    p.add_argument("path")
    p.add_argument("--ref", help="branch, tag or commit")
    p = add("search", cmd_search, "search issues and pull requests", repo=False)
    p.add_argument("query", help="for example: repo:owner/name is:open label:bug")
    p.add_argument("--limit", type=int, default=20)
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
