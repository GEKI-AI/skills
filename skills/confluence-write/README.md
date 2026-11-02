# confluence-write

Create and update pages in Confluence Cloud from your agent, and add comments. You give the text as Markdown and the script converts it. It changes real content. To search and read, use [`confluence-read`](../confluence-read).

## Example requests

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
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/confluence-write ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill confluence-write from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
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

1. Create an API token without scopes at https://id.atlassian.com/manage-profile/security/api-tokens ("Create API token"). The token has the same rights as the Atlassian account that creates it, so it can edit every page that account can edit. Use an account that may edit only the spaces the agent should write to. For a shared bot, create a separate Atlassian account for it. Install `confluence-read` instead if the agent only needs to read.
2. Set `CONFLUENCE_TOKEN` to your email and the token in one value, joined by a colon: `you@company.com:ATATT3x...`. Alternatively set `CONFLUENCE_EMAIL` to the email and `CONFLUENCE_TOKEN` to the token alone.
3. Set `CONFLUENCE_URL` to the address of your site, for example `https://company.atlassian.net`. Do not add `/wiki`.
4. Check the connection with a read: `python scripts/confluence.py show PAGE_ID`, with the id of any page you can see (the number in the page address).

In a GEKI bot, `CONFLUENCE_URL` is a skill setting of the bot. `CONFLUENCE_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `CONFLUENCE_URL`. With "each person", pages are written under the name of that person.

Scoped API tokens use another address (`api.atlassian.com`) and are not supported yet.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 11 script tests (pytest) run against a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec, on Python 3.11 with only the declared packages.
- 2 agent tasks: a vanilla Pi with a model runs each task against the mock, three times. A task passes with two of three runs, judged by the requests the mock saw.
- A weekly read-only run against a real account finds drift between the real API and the fixtures.

[![CI](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml/badge.svg)](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml)
<!-- /generated:tests -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
