# hubspot

HubSpot CRM from your agent. Search and read contacts, companies and deals, create and update them, and log notes on records. It does not send email and does not delete records.

## Example requests

- "Look up Anna Berger in HubSpot and tell me which deals her company has."
- "Create a contact for carla@example.com."
- "Move the Berger renewal deal to closed won."
- "Log a note on contact 301: called, wants a quote."

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/hubspot ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill hubspot from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `HUBSPOT_TOKEN` | secret |

Hosts the skill talks to: `api.hubapi.com`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect HubSpot with a private app in three steps.

1. In HubSpot, open Settings, Integrations, Private Apps, and create a private app. Under Scopes, add `crm.objects.contacts.read`, `crm.objects.companies.read` and `crm.objects.deals.read`. For writing, also add `crm.objects.contacts.write`, `crm.objects.companies.write` and `crm.objects.deals.write`. Notes need `crm.objects.contacts.write` (or the write scope of the record you attach them to). Leave out the write scopes if the agent should only read.
2. Copy the access token of the app and set it as `HUBSPOT_TOKEN`.
3. Check the connection: `python scripts/hubspot.py search contacts --limit 1`.

The skill talks to `https://api.hubapi.com`. HubSpot developer test accounts use the same address.

In a GEKI bot, `HUBSPOT_TOKEN` is a shared credential of the company (an environment variable secret in a vault). A private app token belongs to the app, not to a person, so there is no "each person" sign-in for this skill.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 11 script tests (pytest) run against a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec, on Python 3.11 with only the declared packages.
- 3 agent tasks: a vanilla Pi with a model runs each task against the mock, three times. A task passes with two of three runs, judged by the requests the mock saw.
- A weekly read-only run against a real account finds drift between the real API and the fixtures.

[![CI](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml/badge.svg)](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml)
<!-- /generated:tests -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
