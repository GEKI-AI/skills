# github

Code, issues, pull requests, comments and files of GitHub repositories from your agent. Clone and push with git, list and read issues and pull requests, create and update issues, create pull requests, comment, see what a pull request changes, read a file or folder, search issues. It does not merge.

## Example requests

- "Which open bugs does acme/web have?"
- "Create an issue in acme/web: the login fails on Safari."
- "What does pull request 30 change?"
- "Comment on issue 12 that it is fixed, and close it."
- "Fix the typo in the README of acme/web and open a pull request."

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

The skill needs Python 3.11+ and these packages: system packages: `git`.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `GITHUB_TOKEN` | secret |

Hosts the skill talks to: `api.github.com`, `github.com`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect GitHub in two steps.

1. Create a token. Prefer a fine-grained personal access token (GitHub, Settings, Developer settings, Personal access tokens, Fine-grained tokens). Choose only the repositories the agent should use. Give it the repository permissions "Issues: Read and write", "Pull requests: Read and write" and "Contents: Read-only". Drop the write permissions if the agent should only read. If the agent should push code, use "Contents: Read and write", and add "Workflows: Read and write" if it should also change GitHub Actions workflow files. A classic token needs the scope `repo` (or `public_repo` for public repositories only) and gives much wider rights. It needs the scope `workflow` for workflow files.
2. Set `GITHUB_TOKEN` to the token. The skill talks to `https://api.github.com`. To use it with GitHub Enterprise, set `GITHUB_BASE_URL` to the API address of your server, and clone from the address of your server.

Check the connection: `python scripts/github.py prs OWNER/NAME --limit 1`.

In a GEKI bot, `GITHUB_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed hosts are `api.github.com` and `github.com`, and git over HTTPS to `github.com` works with the same credential. With "each person", issues, comments and pushes are made under the name of that person.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 19 script tests (pytest) run against a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec, on Python 3.11 with only the declared packages.
- 5 agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.
- An optional read-only run against a real account can be started by hand. It is not part of the checks.
<!-- /generated:tests -->

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
