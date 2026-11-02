# github

Issues, pull requests, comments and files of GitHub repositories from your agent. List and read issues and pull requests, create and update issues, comment, see what a pull request changes, read a file or folder, search issues. It does not push code or merge.

## Example requests

- "Which open bugs does acme/web have?"
- "Create an issue in acme/web: the login fails on Safari."
- "What does pull request 30 change?"
- "Comment on issue 12 that it is fixed, and close it."

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/github ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill github from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `GITHUB_TOKEN` | secret |

Hosts the skill talks to: `api.github.com`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect GitHub in two steps.

1. Create a token. Prefer a fine-grained personal access token (GitHub, Settings, Developer settings, Personal access tokens, Fine-grained tokens). Choose only the repositories the agent should use. Give it the repository permissions "Issues: Read and write", "Pull requests: Read and write" and "Contents: Read-only". Drop the write permissions if the agent should only read. A classic token needs the scope `repo` (or `public_repo` for public repositories only) and gives much wider rights.
2. Set `GITHUB_TOKEN` to the token. The skill talks to `https://api.github.com`. To use it with GitHub Enterprise, set `GITHUB_BASE_URL` to the API address of your server.

Check the connection: `python scripts/github.py prs OWNER/NAME --limit 1`.

In a GEKI bot, `GITHUB_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is `api.github.com`. With "each person", issues and comments are written under the name of that person.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 16 script tests (pytest) run against a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec, on Python 3.11 with only the declared packages.
- 4 agent tasks: a vanilla Pi with a model runs each task against the mock, three times. A task passes with two of three runs, judged by the requests the mock saw.
- A weekly read-only run against a real account finds drift between the real API and the fixtures.

[![CI](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml/badge.svg)](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml)
<!-- /generated:tests -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
