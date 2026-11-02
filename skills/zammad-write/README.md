# zammad-write

Create tickets, reply to tickets and change the ticket state in Zammad from your agent. A reply of type `email` sends a real email to the customer, so the skill tells the agent to ask first. To search and read tickets, use [`zammad-read`](../zammad-read).

## Example requests

- "Open a ticket for anna@example.com: the printer in room 2 is offline."
- "Add an internal note to ticket 42: toner replaced."
- "Close ticket 42."

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/zammad-write ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill zammad-write from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `ZAMMAD_TOKEN` | secret |
| `ZAMMAD_URL` | setting |

Hosts the skill talks to: the host of `ZAMMAD_URL`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect your Zammad instance in three steps.

1. In Zammad, open your profile, then "Token Access", and create a personal access token with the permission `ticket.agent`. The token has the rights of its user, so it can write in every group that user can write in. For a shared bot, create a separate Zammad user and give it only the groups the bot should work in. Install `zammad-read` instead if the agent only needs to read.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py states`. It prints the ticket states of your instance.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`. With "each person", tickets and messages are written under the name of that person.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 10 script tests (pytest) run against a small mock with fixtures, on Python 3.11 with only the declared packages.
- 3 agent tasks: a vanilla Pi with a model runs each task against the mock, three times. A task passes with two of three runs, judged by the requests the mock saw.
- A weekly read-only run against a real account finds drift between the real API and the fixtures.

[![CI](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml/badge.svg)](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml)
<!-- /generated:tests -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
