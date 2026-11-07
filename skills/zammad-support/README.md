# zammad-support

Do support work in Zammad from your agent. Find and read tickets, answer customers, add internal notes, change state, priority, owner and group, set tags, link tickets, look up customers and use the knowledge base. A reply of type `email` sends a real email to the customer, so the skill tells the agent to ask first. Set `ZAMMAD_EMAIL` to `off` for an agent that must only write notes. If people should only be able to report problems, use [`zammad-create-ticket`](../zammad-create-ticket).

<!-- generated:geki -->
**On GEKI Companybots** this skill is in the skill catalog of every organization. Skill page (in German): [geki.ai/skills/zammad](https://geki.ai/skills/zammad/). [Register](https://console.geki.ai/register?landing=skill-zammad&utm_source=github&utm_medium=readme&utm_campaign=skills&utm_content=zammad-support) and get free starting credits.
<!-- /generated:geki -->

## Example requests

- "Which open tickets mention the printer in room 2?"
- "Summarise ticket 42 and what we told the customer."
- "Is there a knowledge base answer for password resets?"
- "Answer ticket 42: the printer works again. Show me the text first."
- "Give ticket 42 to Ben, set it to high and tag it with hardware."
- "Add an internal note to ticket 42: toner replaced, 15 minutes."
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
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/zammad-support ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill zammad-support from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `ZAMMAD_TOKEN` | secret |
| `ZAMMAD_URL` | setting |
| `ZAMMAD_EMAIL` | setting |

Hosts the skill talks to: the host of `ZAMMAD_URL`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect your Zammad instance in three steps.

1. In Zammad, open your profile, then "Token Access", and create a personal access token with the permission `ticket.agent`. Add `knowledge_base.reader` for the knowledge base commands. The token has the rights of its user, so it can read and write in every group that user can. For a shared bot, create a separate Zammad user and give it only the groups the bot should work in. Install `zammad-create-ticket` instead if the agent should only create tickets.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py states`. It prints the ticket states of your instance.

Optional: set `ZAMMAD_EMAIL` to `off` when the agent must never send email. The script then refuses replies of type `email`, and the agent can only write notes. Without it, email is on.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`. With "each person", tickets and messages are written under the name of that person.

### Start a GEKI bot for each new ticket

A Zammad webhook can start a bot for every new ticket.

1. In GEKI, add an on-demand trigger to the bot. Copy its URL and its token.
2. In Zammad, open Admin, Manage, Webhook, and add a webhook. Endpoint: the URL of the trigger. Bearer token: the token of the trigger. Turn on the custom payload and send the ticket id, for example `{"ticket_id": "#{ticket.id}", "title": "#{ticket.title}"}`.
3. Open Admin, Manage, Trigger, and add a trigger. Conditions: action is created, and tags do not contain a guard tag such as `ai-done`. Action: the webhook from step 2.
4. In the bot's instructions, read the ticket with `ticket ID --internal`, do the work, and add the guard tag last with `tag-add ID ai-done`. The same webhook can fire twice. The guard tag keeps the bot from working on a ticket twice.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 33 script tests (pytest) run against a small mock with fixtures, on Python 3.11 with only the declared packages.
- 6 agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.
- An optional read-only run against a real account can be started by hand. It is not part of the checks.
<!-- /generated:tests -->

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
