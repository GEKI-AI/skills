import importlib.util
import os
import shlex
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "forgejo.py"
spec = importlib.util.spec_from_file_location("forgejo", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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
    assert result.json["url"].endswith("/pulls/31")
    post = mock.requests[-1]
    assert (post["method"], post["path"]) == ("POST", "/api/v1/repos/acme/web/pulls")
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
    skill = SCRIPT.parents[1] / "SKILL.md"
    line = next(x for x in skill.read_text().splitlines() if x.startswith("git clone "))
    bare = tmp_path / "web.git"
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "FORGEJO_TOKEN": "test-token"}
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=env)
    clone = tmp_path / "web"
    subprocess.run([*shlex.split(line)[:-1], str(bare), str(clone)], check=True, env=env)
    assert "test-token" not in (clone / ".git" / "config").read_text()
    filled = subprocess.run(
        ["git", "credential", "fill"],
        cwd=clone,
        input="protocol=https\nhost=git.example.com\n\n",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "password=test-token\n" in filled.stdout


def test_repos_finds_by_name(cli, mock):
    rows = cli("repos", "web").json["results"]
    assert rows[0]["repo"] == "acme/web"
    assert rows[0]["default_branch"] == "main"
    assert mock.requests[0]["path"] == "/api/v1/repos/search"
    assert mock.requests[0]["query"]["q"] == "web"


def test_issues_asks_only_for_issues(cli, mock):
    rows = cli("issues", "acme/web", "--labels", "bug", "--assignee", "anna").json["results"]
    assert [r["number"] for r in rows] == [12, 11]
    assert all(r["is_pull_request"] is False for r in rows)
    assert rows[0]["labels"] == ["bug"]
    query = mock.requests[0]["query"]
    assert query["type"] == "issues"
    assert query["state"] == "open"
    assert query["labels"] == "bug"
    assert query["assigned_by"] == "anna"


def test_a_null_pull_request_key_is_no_pull_request(cli, mock):
    rows = cli("issues", "acme/web", "--include-prs").json["results"]
    assert [r["is_pull_request"] for r in rows] == [True, False]
    assert "type" not in mock.requests[0]["query"]


def test_limit_and_page_are_sent(cli, mock):
    cli("issues", "acme/web", "--limit", "1", "--page", "2")
    assert mock.requests[0]["query"]["limit"] == "1"
    assert mock.requests[0]["query"]["page"] == "2"


def test_issue_has_its_comments(cli, mock):
    data = cli("issue", "acme/web", "12").json
    assert data["body"] == "Body of Login fails on Safari."
    assert data["comment_list"][0]["body"] == "I see this too."
    assert [r["path"] for r in mock.requests] == [
        "/api/v1/repos/acme/web/issues/12",
        "/api/v1/repos/acme/web/issues/12/comments",
    ]


def test_create_issue_sends_label_ids(cli, mock):
    result = cli(
        "issue-create",
        "acme/web",
        "--title",
        "Login fails",
        "--body",
        "Text",
        "--labels",
        "bug,urgent",
    )
    assert result.code == 0, result.err
    assert result.json["number"] == 13
    post = mock.requests[-1]
    assert (post["method"], post["path"]) == ("POST", "/api/v1/repos/acme/web/issues")
    assert post["body"] == {"title": "Login fails", "body": "Text", "labels": [1, 9]}


def test_create_issue_without_labels_reads_no_labels(cli, mock):
    assert cli("issue-create", "acme/web", "--title", "Login fails").code == 0
    assert [r["method"] for r in mock.requests] == ["POST"]
    assert mock.requests[0]["body"] == {"title": "Login fails"}


def test_unknown_label_stops_before_anything_is_written(cli, mock):
    result = cli("issue-create", "acme/web", "--title", "x", "--labels", "nope")
    assert result.code == 1
    assert "nope" in result.error["error"]
    assert result.error["detail"] == ["bug", "ui", "urgent"]
    assert {r["method"] for r in mock.requests} == {"GET"}


def test_owner_without_organization_uses_repository_labels(cli, mock):
    result = cli("issue-create", "anna/notes", "--title", "x", "--labels", "bug")
    assert result.code == 0, result.err
    assert mock.requests[-1]["body"]["labels"] == [1]


def test_token_without_organization_scope_uses_repository_labels(cli, mock):
    mock.routes.insert(
        0, {"method": "GET", "path": "/api/v1/orgs/acme/labels", "status": 403, "body": {}}
    )
    result = cli("issue-create", "acme/web", "--title", "x", "--labels", "ui")
    assert result.code == 0, result.err
    assert mock.requests[-1]["body"]["labels"] == [2]


def test_update_state_and_labels_are_two_calls(cli, mock):
    result = cli("issue-update", "acme/web", "12", "--state", "closed", "--labels", "bug")
    assert result.code == 0, result.err
    writes = [r for r in mock.requests if r["method"] != "GET"]
    assert [(r["method"], r["path"]) for r in writes] == [
        ("PATCH", "/api/v1/repos/acme/web/issues/12"),
        ("PUT", "/api/v1/repos/acme/web/issues/12/labels"),
    ]
    assert writes[0]["body"] == {"state": "closed"}
    assert writes[1]["body"] == {"labels": [1]}
    assert result.json["state"] == "closed"
    assert result.json["labels"] == ["bug"]


def test_empty_labels_remove_all(cli, mock):
    assert cli("issue-update", "acme/web", "12", "--labels", "").code == 0
    writes = [r for r in mock.requests if r["method"] != "GET"]
    assert [r["body"] for r in writes] == [{"labels": []}]


def test_update_with_unknown_label_changes_nothing(cli, mock):
    result = cli("issue-update", "acme/web", "12", "--state", "closed", "--labels", "nope")
    assert result.code == 1
    assert {r["method"] for r in mock.requests} == {"GET"}


def test_update_without_a_field_is_an_error(cli, mock):
    assert cli("issue-update", "acme/web", "12").code == 1
    assert mock.requests == []


def test_comment(cli, mock):
    result = cli("comment", "acme/web", "12", "--body-file", "-", stdin="Fixed.")
    assert result.code == 0, result.err
    assert result.json["id"] == 502
    assert mock.requests[0]["path"] == "/api/v1/repos/acme/web/issues/12/comments"
    assert mock.requests[0]["body"] == {"body": "Fixed."}


def test_comment_without_text_is_an_error(cli, mock):
    assert cli("comment", "acme/web", "12").code == 1
    assert mock.requests == []


def test_prs(cli, mock):
    row = cli("prs", "acme/web").json["results"][0]
    assert (row["head"], row["base"], row["head_sha"]) == ("fix/login", "main", "abc123def456")
    assert mock.requests[0]["query"]["state"] == "open"


def test_pr_has_the_details(cli):
    data = cli("pr", "acme/web", "30").json
    assert data["mergeable"] is True
    assert data["changed_files"] == 2
    assert data["body"] == "Fixes the cookie flag."


def test_pr_files_joins_the_list_and_the_diff(cli, mock):
    result = cli("pr-files", "acme/web", "30")
    assert result.code == 0, result.err
    rows = result.json["results"]
    assert [r["filename"] for r in rows] == ["src/login.py", "docs/änderung.md"]
    assert "+secure = True" in rows[0]["patch"]
    assert "Safari" not in rows[0]["patch"]
    assert "+Safari" in rows[1]["patch"]
    assert mock.requests[1]["path"] == "/api/v1/repos/acme/web/pulls/30.diff"
    assert mock.requests[1]["headers"]["accept"] == "text/plain"


def test_pr_files_cuts_long_diffs(cli):
    row = cli("pr-files", "acme/web", "30", "--max-patch", "10").json["results"][0]
    assert len(row["patch"]) == 10
    assert row["patch_cut"] is True


def test_names_that_contain_the_marker_of_the_next_name():
    diff = "diff --git a/a b/c b/a b/c\n+one\n"
    assert module.patches_by_file(diff, ["c", "a b/c"]) == {"c": diff}
    assert module.patches_by_file(diff, ["a b/c"]) == {"a b/c": diff}


def test_status_of_a_branch_with_a_slash(cli, mock):
    data = cli("status", "acme/web", "fix/login").json
    assert data["state"] == "failure"
    assert data["checks"][1]["context"] == "ci / tests"
    assert data["checks"][1]["status"] == "failure"
    assert mock.requests[0]["path"] == "/api/v1/repos/acme/web/commits/fix%2Flogin/status"


def test_file_decodes_the_content(cli, mock):
    data = cli("file", "acme/web", "README.md", "--ref", "main").json
    assert data["type"] == "file"
    assert data["content"] == "Hello acme\n"
    assert mock.requests[0]["query"]["ref"] == "main"


def test_folder_and_top_folder(cli, mock):
    assert cli("file", "acme/web", "docs").json["entries"][0]["path"] == "docs/setup.md"
    assert cli("file", "acme/web").json["entries"][1]["type"] == "dir"
    assert mock.requests[1]["path"] == "/api/v1/repos/acme/web/contents"


def test_search_names_the_repository(cli, mock):
    row = cli("search", "login", "--owner", "acme", "--type", "issues").json["results"][0]
    assert row["repo"] == "acme/web"
    query = mock.requests[0]["query"]
    assert (query["q"], query["owner"], query["type"]) == ("login", "acme", "issues")


def test_token_is_only_in_the_authorization_header(cli, mock):
    cli("prs", "acme/web")
    request = mock.requests[0]
    assert request["headers"]["authorization"] == "token test-token"
    assert "test-token" not in request["path"]
    assert "test-token" not in str(request["query"])


def test_url_with_the_api_path_works_too(cli, mock):
    url = mock.url + "/api/v1/"
    assert cli("prs", "acme/web", extra={"FORGEJO_URL": url}).code == 0
    assert mock.requests[0]["path"] == "/api/v1/repos/acme/web/pulls"


def test_repo_must_have_owner_and_name(cli):
    result = cli("issues", "acme")
    assert result.code == 1
    assert "owner/name" in result.error["error"]


@pytest.mark.parametrize("name", ["FORGEJO_TOKEN", "FORGEJO_URL"])
def test_missing_variable_is_a_json_error(cli, name):
    result = cli("prs", "acme/web", extra={name: ""})
    assert result.code == 1
    assert f"{name} is not set" in result.error["error"]


def test_http_error_is_a_json_error(cli, mock):
    mock.routes.insert(
        0,
        {
            "method": "GET",
            "path": "/api/v1/repos/{owner}/{repo}/pulls",
            "status": 403,
            "body": {"message": "token does not have the required scope"},
        },
    )
    result = cli("prs", "acme/web")
    assert result.code == 1
    assert result.error["status"] == 403
    assert "scope" in result.error["detail"]


@pytest.mark.real_api
def test_real_read(real_cli):
    repos = real_cli("repos", "--limit", "1")
    assert repos.code == 0, repos.err
    if not repos.json["results"]:
        pytest.skip("the token sees no repository")
    repo = repos.json["results"][0]["repo"]
    assert real_cli("issues", repo, "--limit", "1").code == 0
    assert real_cli("prs", repo, "--limit", "1").code == 0
    assert real_cli("file", repo).json["type"] == "dir"
