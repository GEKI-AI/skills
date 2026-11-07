# forgejo

Code, issues, pull requests, comments, files and CI status on your Forgejo server from your agent. Find repositories, clone and push with git, list and read issues and pull requests, create and update issues, create pull requests, comment, see what a pull request changes, check whether CI is green, read a file or folder, search issues. It does not merge.

<!-- generated:geki -->
**On GEKI Companybots** this skill is in the skill catalog of every organization. [Register](https://console.geki.ai/register?landing=skill-forgejo&utm_source=github&utm_medium=readme&utm_campaign=skills&utm_content=forgejo) and get free starting credits.
<!-- /generated:geki -->

## Example requests

- "Which open bugs does acme/web have?"
- "Create an issue in acme/web: the login fails on Safari."
- "What does pull request 30 change, and is its CI green?"
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
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/forgejo ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill forgejo from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and these packages: system packages: `git`.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `FORGEJO_TOKEN` | secret |
| `FORGEJO_URL` | setting |

Hosts the skill talks to: the host of `FORGEJO_URL`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect Forgejo in three steps.

1. In Forgejo, open Settings, then Applications, and create an access token with the scopes `write:issue` and `read:repository`. Use `read:issue` instead if the agent should only read. Use `write:repository` instead of `read:repository` if the agent should push code and create pull requests. Add `read:organization` to use the labels of an organization, not only those of the repository. The token has the rights of its user, so for a shared bot create a separate Forgejo user and give it only the repositories it should work in.
2. Set `FORGEJO_TOKEN` to the token. Set `FORGEJO_URL` to the address of your server without a trailing slash, for example `https://git.company.com`.
3. Check the connection: `python scripts/forgejo.py repos --limit 1`. It prints a list with one repository.

In a GEKI bot, `FORGEJO_URL` is a skill setting of the bot. `FORGEJO_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `FORGEJO_URL`, and git over HTTPS to that host works with the same credential. With "each person", issues, comments and pushes are made under the name of that person.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 34 script tests (pytest) run against a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec, on Python 3.11 with only the declared packages.
- 5 agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.
- An optional read-only run against a real account can be started by hand. It is not part of the checks.
<!-- /generated:tests -->

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
