# zammad-create-ticket

Create tickets in Zammad from your agent, and nothing else. It cannot read, answer or change existing tickets and it sends no email. Use it where people should reach the support team through the agent. To work on tickets, use [`zammad-support`](../zammad-support).

## Example requests

- "Open a ticket in the group Users: the printer in room 2 is offline."
- "Report to support that anna@example.com cannot log in."

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/zammad-create-ticket ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill zammad-create-ticket from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
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

1. In Zammad, open your profile, then "Token Access", and create a personal access token. The permission `ticket.customer` is enough to create tickets for the owner of the token. To create tickets for other customers, the token needs `ticket.agent`, and the user must have access to the group. For a shared bot, create a separate Zammad user and give it only the groups the bot should create tickets in.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py me`. It prints the user of the token.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

The skill cannot list groups. If your users do not know the group names, name the right group in the instructions of the bot.

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`. With "each person", tickets are created under the name of that person.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 10 script tests (pytest) run against a small mock with fixtures, on Python 3.11 with only the declared packages.
- 2 agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.
- An optional read-only run against a real account can be started by hand. It is not part of the checks.
<!-- /generated:tests -->

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
