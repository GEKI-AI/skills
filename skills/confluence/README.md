# confluence

Search, read and change Confluence Cloud from your agent. Find pages with CQL or plain text, read a page as Markdown, browse spaces and child pages, create and update pages, add comments. You give new text as Markdown and the script converts it. Writing changes real content.

<!-- generated:geki -->
**On GEKI Companybots** this skill is in the skill catalog of every organization. Skill page (in German): [geki.ai/skills/confluence-mit-ki-automatisieren](https://geki.ai/skills/confluence-mit-ki-automatisieren/). [Register](https://console.geki.ai/register?landing=skill-confluence-mit-ki-automatisieren&utm_source=github&utm_medium=readme&utm_campaign=skills&utm_content=confluence) and get free starting credits.
<!-- /generated:geki -->

## Example requests

- "Find our onboarding guide in Confluence and summarise the first week."
- "What does the expense policy say about train tickets?"
- "List the pages in the DOCS space."
- "Put these meeting notes into Confluence under the DOCS space."
- "Add a row for the new VPN profile to the onboarding table."
- "Comment on the expense policy page that the limit changed."

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/confluence ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill confluence from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `CONFLUENCE_TOKEN` | secret |
| `CONFLUENCE_URL` | setting |

Hosts the skill talks to: the host of `CONFLUENCE_URL`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect your Confluence Cloud site in four steps.

1. Create an API token without scopes at https://id.atlassian.com/manage-profile/security/api-tokens ("Create API token"). The token has the same rights as the Atlassian account that creates it, so the agent can read and edit everything that account can. Use an account that can only view the spaces the agent may see and edit only the spaces it should write to. An account with view rights only makes the agent read-only: its writes fail with a 403. For a shared bot, create a separate Atlassian account for it.
2. Set `CONFLUENCE_TOKEN` to your email and the token in one value, joined by a colon: `you@company.com:ATATT3x...`. Alternatively set `CONFLUENCE_EMAIL` to the email and `CONFLUENCE_TOKEN` to the token alone.
3. Set `CONFLUENCE_URL` to the address of your site, for example `https://company.atlassian.net`. Do not add `/wiki`.
4. Check the connection: `python scripts/confluence.py spaces --limit 1`. It prints a list with one space.

In a GEKI bot, `CONFLUENCE_URL` is a skill setting of the bot. `CONFLUENCE_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `CONFLUENCE_URL`. With "each person", pages are written under the name of that person.

Scoped API tokens use another address (`api.atlassian.com`) and are not supported yet.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 21 script tests (pytest) run against a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec, on Python 3.11 with only the declared packages.
- 4 agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.
- An optional read-only run against a real account can be started by hand. It is not part of the checks.
<!-- /generated:tests -->

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
