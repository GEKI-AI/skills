import os
import shlex
import subprocess
from pathlib import Path

import pytest


def test_issues_leave_out_pull_requests(cli, mock):
    result = cli("issues", "acme/web", "--labels", "bug", "--limit", "5")
    assert result.code == 0, result.err
    numbers = [r["number"] for r in result.json["results"]]
    assert numbers == [12, 9]
    first = result.json["results"][0]
    assert first["labels"] == ["bug"]
    assert first["assignees"] == ["ben"]
    sent = mock.requests[0]
    assert sent["path"] == "/repos/acme/web/issues"
    assert sent["query"]["state"] == "open"
    assert sent["query"]["labels"] == "bug"
    assert sent["query"]["per_page"] == "5"


def test_issues_can_include_pull_requests(cli):
    numbers = [r["number"] for r in cli("issues", "acme/web", "--include-prs").json["results"]]
    assert numbers == [12, 30, 9]


def test_issue_with_comments(cli, mock):
    data = cli("issue", "acme/web", "12").json
    assert data["title"] == "Login fails on Safari"
    assert data["body"] == "Clicking Login does nothing on Safari 18."
    assert [c["author"] for c in data["comment_list"]] == ["ben", "anna"]
    assert [r["path"] for r in mock.requests] == [
        "/repos/acme/web/issues/12",
        "/repos/acme/web/issues/12/comments",
    ]


def test_issue_create(cli, mock):
    result = cli(
        "issue-create",
        "acme/web",
        "--title",
        "Login fails",
        "--labels",
        "bug,urgent",
        "--body-file",
        "-",
        stdin="Steps to reproduce",
    )
    assert result.code == 0, result.err
    assert result.json["number"] == 31
    assert result.json["url"] == "https://github.com/acme/web/issues/31"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/repos/acme/web/issues")
    assert sent["body"] == {
        "title": "Login fails",
        "body": "Steps to reproduce",
        "labels": ["bug", "urgent"],
    }


def test_issue_update_close(cli, mock):
    result = cli("issue-update", "acme/web", "12", "--state", "closed")
    assert result.json["state"] == "closed"
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("PATCH", "/repos/acme/web/issues/12")
    assert sent["body"] == {"state": "closed"}


def test_issue_update_needs_a_change(cli):
    result = cli("issue-update", "acme/web", "12")
    assert result.code == 1
    assert "nothing to change" in result.error["error"]


def test_comment(cli, mock):
    result = cli("comment", "acme/web", "12", "--body", "Fixed in the next release.")
    assert result.code == 0, result.err
    assert result.json["id"] == 1003
    sent = mock.requests[0]
    assert (sent["method"], sent["path"]) == ("POST", "/repos/acme/web/issues/12/comments")
    assert sent["body"] == {"body": "Fixed in the next release."}


def test_prs_and_pr(cli):
    prs = cli("prs", "acme/web").json["results"]
    assert prs[0]["head"] == "fix-login" and prs[0]["base"] == "main"
    pr = cli("pr", "acme/web", "30").json
    assert pr["changed_files"] == 2 and pr["body"].startswith("Redirects")


def test_pr_files_cut_long_diffs(cli):
    rows = cli("pr-files", "acme/web", "30", "--max-patch", "10").json["results"]
    assert rows[0]["filename"] == "src/login.js"
    assert len(rows[0]["patch"]) == 10 and rows[0]["patch_cut"] is True


def test_file_is_decoded(cli, mock):
    data = cli("file", "acme/web", "README.md", "--ref", "main").json
    assert data["content"] == "# Acme Web\n\nThe company website.\n"
    assert mock.requests[0]["query"] == {"ref": "main"}


def test_folder_is_listed(cli):
    data = cli("file", "acme/web", "docs").json
    assert data["type"] == "dir"
    assert [e["name"] for e in data["entries"]] == ["setup.md", "api"]


def test_search(cli, mock):
    data = cli("search", "repo:acme/web is:open label:bug").json
    assert data["total"] == 1
    assert mock.requests[0]["query"]["q"] == "repo:acme/web is:open label:bug"


def test_token_is_only_in_the_authorization_header(cli, mock):
    cli("prs", "acme/web")
    request = mock.requests[0]
    assert request["headers"]["authorization"] == "Bearer test-token"
    assert request["headers"]["accept"] == "application/vnd.github+json"
    assert "test-token" not in request["path"]


def test_repo_must_have_owner_and_name(cli):
    result = cli("issues", "acme")
    assert result.code == 1
    assert "owner/name" in result.error["error"]


def test_missing_token_is_a_json_error(cli):
    result = cli("prs", "acme/web", extra={"GITHUB_TOKEN": ""})
    assert result.code == 1
    assert "GITHUB_TOKEN is not set" in result.error["error"]


@pytest.mark.real_api
def test_real_read_of_a_public_repo(real_cli):
    result = real_cli("file", "octocat/Hello-World", "README")
    assert result.code == 0, result.err
    assert "Hello World" in result.json["content"]
    issues = real_cli("issues", "octocat/Hello-World", "--limit", "1")
    assert issues.code == 0, issues.err
    assert "results" in issues.json


def test_pr_create_sends_branches_title_and_text(cli, mock):
    result = cli(
        "pr-create",
        "acme/web",
        "--head",
        "fix/login",
        "--base",
        "main",
        "--title",
        "Fix the login",
        "--body",
        "Line one\n\nLine two",
    )
    assert result.code == 0, result.err
    assert result.json["number"] == 31
    assert result.json["url"].endswith("/pull/31")
    post = mock.requests[-1]
    assert (post["method"], post["path"]) == ("POST", "/repos/acme/web/pulls")
    assert post["body"] == {
        "head": "fix/login",
        "base": "main",
        "title": "Fix the login",
        "body": "Line one\n\nLine two",
    }


def test_pr_create_without_text_sends_no_body(cli, mock):
    args = ("pr-create", "acme/web", "--head", "fix/login", "--base", "main", "--title", "x")
    assert cli(*args).code == 0
    assert "body" not in mock.requests[-1]["body"]


def test_the_clone_line_gives_git_the_token_and_keeps_it_out_of_the_config(tmp_path):
    skill = Path(__file__).resolve().parents[1] / "SKILL.md"
    line = next(x for x in skill.read_text().splitlines() if x.startswith("git clone "))
    bare = tmp_path / "web.git"
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "GITHUB_TOKEN": "test-token"}
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=env)
    clone = tmp_path / "web"
    subprocess.run([*shlex.split(line)[:-1], str(bare), str(clone)], check=True, env=env)
    assert "test-token" not in (clone / ".git" / "config").read_text()
    filled = subprocess.run(
        ["git", "credential", "fill"],
        cwd=clone,
        input="protocol=https\nhost=github.com\n\n",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "password=test-token\n" in filled.stdout
