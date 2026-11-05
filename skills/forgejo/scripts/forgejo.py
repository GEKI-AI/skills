#!/usr/bin/env python3
"""Forgejo issues, pull requests, comments, files and commit status through the REST API.

Needs FORGEJO_URL (https://git.example.com) and FORGEJO_TOKEN (an access token).
Output is JSON on stdout. An error is JSON on stderr with exit code 1.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
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


def api_url() -> str:
    url = setting("FORGEJO_URL").rstrip("/")
    return url if url.endswith("/api/v1") else f"{url}/api/v1"


def send(
    method: str,
    path: str,
    params: dict | None = None,
    body: dict | None = None,
    accept: str = "application/json",
    optional: bool = False,
) -> bytes | None:
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = api_url() + path + (f"?{query}" if query else "")
    headers = {"Authorization": f"token {setting('FORGEJO_TOKEN')}", "Accept": accept}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if optional and exc.code in (403, 404):
            return None
        detail = exc.read().decode("utf-8", "replace")[:500]
        fail(f"Forgejo answered {exc.code}", exc.code, detail)
    except urllib.error.URLError as exc:
        fail(f"cannot reach Forgejo: {exc.reason}")
    return None


def call(method: str, path: str, params: dict | None = None, body: dict | None = None):
    return json.loads(send(method, path, params, body) or b"null")


def repo_path(repo: str) -> str:
    owner, _, name = repo.partition("/")
    if not owner or not name or "/" in name:
        fail("the repository must look like owner/name")
    return f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}"


def user(item: dict | None) -> str | None:
    return (item or {}).get("login")


def issue_row(item: dict) -> dict:
    row = {
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "author": user(item.get("user")),
        "labels": [label.get("name") for label in item.get("labels") or []],
        "assignees": [user(a) for a in item.get("assignees") or []],
        "comments": item.get("comments"),
        "url": item.get("html_url"),
        "updated_at": item.get("updated_at"),
        # Forgejo sends this key on every issue, with null when it is no pull request.
        "is_pull_request": bool(item.get("pull_request")),
    }
    repository = item.get("repository") or {}
    if repository.get("full_name"):
        row["repo"] = repository["full_name"]
    return row


def comment_row(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "author": user(item.get("user")),
        "body": item.get("body"),
        "created_at": item.get("created_at"),
        "url": item.get("html_url"),
    }


def read_text(args: argparse.Namespace) -> str | None:
    if getattr(args, "body_file", None):
        return (
            sys.stdin.read()
            if args.body_file == "-"
            else Path(args.body_file).read_text(encoding="utf-8")
        )
    return args.body


def csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def all_labels(path: str, optional: bool = False) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        data = send("GET", path, {"page": page, "limit": 50}, optional=optional)
        batch = json.loads(data or b"[]")
        rows += batch
        if not batch:
            return rows
        page += 1


def label_ids(repo: str, names: list[str]) -> list[int]:
    """Forgejo wants label ids. A repository can use its own labels and those of its organization."""
    if not names:
        return []
    owner = repo.partition("/")[0]
    known = all_labels(f"{repo_path(repo)}/labels")
    # The owner can be a person, or the token can lack the organization scope.
    known += all_labels(f"/orgs/{urllib.parse.quote(owner)}/labels", optional=True)
    by_name = {label.get("name"): label.get("id") for label in known}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        fail(f"unknown labels: {', '.join(unknown)}", detail=sorted(by_name))
    return [by_name[name] for name in names]


def cmd_issues(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"{repo_path(args.repo)}/issues",
        {
            "state": args.state,
            "labels": args.labels,
            "assigned_by": args.assignee,
            "created_by": args.author,
            "q": args.query,
            "type": None if args.include_prs else "issues",
            "limit": args.limit,
            "page": args.page,
        },
    )
    print(json.dumps({"results": [issue_row(i) for i in data][: args.limit]}))


def cmd_issue(args: argparse.Namespace) -> None:
    base = repo_path(args.repo)
    item = call("GET", f"{base}/issues/{args.number}")
    comments = call("GET", f"{base}/issues/{args.number}/comments")
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
    labels = label_ids(args.repo, csv(args.labels))
    if labels:
        body["labels"] = labels
    if args.assignees:
        body["assignees"] = csv(args.assignees)
    print(json.dumps(issue_row(call("POST", f"{repo_path(args.repo)}/issues", body=body))))


def cmd_issue_update(args: argparse.Namespace) -> None:
    path = f"{repo_path(args.repo)}/issues/{args.number}"
    body: dict = {}
    if args.state:
        body["state"] = args.state
    if args.title:
        body["title"] = args.title
    text = read_text(args)
    if text is not None:
        body["body"] = text
    if args.assignees is not None:
        body["assignees"] = csv(args.assignees)
    if not body and args.labels is None:
        fail("nothing to change: give --state, --title, --body, --assignees or --labels")
    # Unknown labels fail here, before anything has changed. The edit call takes no labels.
    labels = None if args.labels is None else label_ids(args.repo, csv(args.labels))
    item = call("PATCH", path, body=body) if body else call("GET", path)
    if labels is not None:
        item["labels"] = call("PUT", f"{path}/labels", body={"labels": labels})
    print(json.dumps(issue_row(item)))


def cmd_comment(args: argparse.Namespace) -> None:
    text = read_text(args)
    if text is None:
        fail("give the text with --body or --body-file")
    item = call(
        "POST", f"{repo_path(args.repo)}/issues/{args.number}/comments", body={"body": text}
    )
    print(json.dumps(comment_row(item)))


def pr_row(item: dict) -> dict:
    head = item.get("head") or {}
    return {
        "number": item.get("number"),
        "title": item.get("title"),
        "state": item.get("state"),
        "draft": item.get("draft"),
        "merged": item.get("merged"),
        "author": user(item.get("user")),
        "head": head.get("ref"),
        "head_sha": head.get("sha"),
        "base": (item.get("base") or {}).get("ref"),
        "labels": [label.get("name") for label in item.get("labels") or []],
        "url": item.get("html_url"),
        "updated_at": item.get("updated_at"),
    }


def cmd_prs(args: argparse.Namespace) -> None:
    data = call(
        "GET",
        f"{repo_path(args.repo)}/pulls",
        {"state": args.state, "limit": args.limit, "page": args.page},
    )
    print(json.dumps({"results": [pr_row(p) for p in data][: args.limit]}))


def cmd_pr(args: argparse.Namespace) -> None:
    item = call("GET", f"{repo_path(args.repo)}/pulls/{args.number}")
    print(
        json.dumps(
            {
                **pr_row(item),
                "body": item.get("body"),
                "mergeable": item.get("mergeable"),
                "changed_files": item.get("changed_files"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
            }
        )
    )


def header_names(header: str) -> str:
    """The first line of a file's diff, with the name as git writes it decoded."""
    if not header.endswith('"'):
        return header
    # Git quotes names with special characters and writes bytes as octal escapes.
    raw = header.encode("latin-1", "backslashreplace").decode("unicode_escape")
    return raw.encode("latin-1", "replace").decode("utf-8", "replace")


def patches_by_file(diff: str, names: list[str]) -> dict[str, str]:
    """Split a whole diff by file. The file list says where one name ends."""
    out: dict[str, str] = {}
    for part in re.split(r"(?m)^(?=diff --git )", diff):
        header = header_names(part.partition("\n")[0])
        for name in names:
            if header.endswith((f" b/{name}", f' "b/{name}"')):
                out[name] = part
                break
    return out


def cmd_pr_create(args: argparse.Namespace) -> None:
    body = {"head": args.head, "base": args.base, "title": args.title}
    text = read_text(args)
    if text is not None:
        body["body"] = text
    print(json.dumps(pr_row(call("POST", f"{repo_path(args.repo)}/pulls", body=body))))


def cmd_pr_files(args: argparse.Namespace) -> None:
    path = f"{repo_path(args.repo)}/pulls/{args.number}"
    files = call("GET", f"{path}/files", {"limit": args.limit})
    # The file list of Forgejo has no diff. It comes in one text for the whole pull request.
    diff = (send("GET", f"{path}.diff", accept="text/plain") or b"").decode("utf-8", "replace")
    patches = patches_by_file(diff, [item.get("filename") or "" for item in files])
    rows = []
    for item in files:
        patch = patches.get(item.get("filename") or "", "")
        rows.append(
            {
                "filename": item.get("filename"),
                "previous_filename": item.get("previous_filename"),
                "status": item.get("status"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
                "patch": patch[: args.max_patch],
                "patch_cut": len(patch) > args.max_patch,
            }
        )
    print(json.dumps({"results": rows}))


def cmd_status(args: argparse.Namespace) -> None:
    ref = urllib.parse.quote(args.ref, safe="")
    data = call("GET", f"{repo_path(args.repo)}/commits/{ref}/status")
    rows = [
        {
            "context": item.get("context"),
            "status": item.get("status"),
            "description": item.get("description"),
            "url": item.get("target_url"),
        }
        for item in data.get("statuses") or []
    ]
    print(json.dumps({"state": data.get("state"), "sha": data.get("sha"), "checks": rows}))


def cmd_file(args: argparse.Namespace) -> None:
    path = "/".join(urllib.parse.quote(part) for part in args.path.strip("/").split("/") if part)
    target = f"{repo_path(args.repo)}/contents" + (f"/{path}" if path else "")
    data = call("GET", target, {"ref": args.ref})
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
    data = call(
        "GET",
        "/repos/issues/search",
        {
            "q": args.query,
            "state": args.state,
            "type": args.type,
            "labels": args.labels,
            "owner": args.owner,
            "limit": args.limit,
            "page": args.page,
        },
    )
    print(json.dumps({"results": [issue_row(i) for i in data][: args.limit]}))


def cmd_repos(args: argparse.Namespace) -> None:
    data = call("GET", "/repos/search", {"q": args.query, "limit": args.limit, "page": args.page})
    rows = [
        {
            "repo": item.get("full_name"),
            "description": item.get("description"),
            "private": item.get("private"),
            "archived": item.get("archived"),
            "default_branch": item.get("default_branch"),
            "url": item.get("html_url"),
            "updated_at": item.get("updated_at"),
        }
        for item in (data or {}).get("data") or []
    ]
    print(json.dumps({"results": rows}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Forgejo issues, pull requests, comments, files, commit status. JSON output."
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

    def paging(p: argparse.ArgumentParser) -> None:
        p.add_argument("--limit", type=int, default=20)
        p.add_argument("--page", type=int, help="page of the results, from 1")

    p = add("repos", cmd_repos, "find repositories", repo=False)
    p.add_argument("query", nargs="?", help="words in the name")
    paging(p)
    p = add("issues", cmd_issues, "list issues")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p.add_argument("--labels", help="comma-separated names")
    p.add_argument("--assignee", help="login")
    p.add_argument("--author", help="login")
    p.add_argument("--query", help="words to find")
    p.add_argument("--include-prs", action="store_true")
    paging(p)
    add("issue", cmd_issue, "read an issue with its comments", number=True)
    p = add("issue-create", cmd_issue_create, "create an issue")
    p.add_argument("--title", required=True)
    p.add_argument("--labels", help="comma-separated names")
    p.add_argument("--assignees", help="comma-separated logins")
    text(p)
    p = add("issue-update", cmd_issue_update, "change an issue", number=True)
    p.add_argument("--state", choices=["open", "closed"])
    p.add_argument("--title")
    p.add_argument("--labels", help="comma-separated names, replaces all labels")
    p.add_argument("--assignees", help="comma-separated logins, replaces all assignees")
    text(p)
    p = add("comment", cmd_comment, "comment on an issue or pull request", number=True)
    text(p)
    p = add("prs", cmd_prs, "list pull requests")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    paging(p)
    add("pr", cmd_pr, "read a pull request", number=True)
    p = add("pr-create", cmd_pr_create, "create a pull request from a pushed branch")
    p.add_argument("--head", required=True, help="the pushed branch")
    p.add_argument("--base", required=True, help="the branch to merge into")
    p.add_argument("--title", required=True)
    text(p)
    p = add("pr-files", cmd_pr_files, "files changed by a pull request", number=True)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--max-patch", type=int, default=4000, help="characters of diff per file")
    p = add("status", cmd_status, "CI status of a branch, tag or commit")
    p.add_argument("ref")
    p = add("file", cmd_file, "read a file or list a folder")
    p.add_argument("path", nargs="?", default="", help="default: the top folder")
    p.add_argument("--ref", help="branch, tag or commit")
    p = add("search", cmd_search, "search issues and pull requests in all repositories", repo=False)
    p.add_argument("query")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p.add_argument("--type", choices=["issues", "pulls"])
    p.add_argument("--labels", help="comma-separated names")
    p.add_argument("--owner", help="only repositories of this owner")
    paging(p)
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
