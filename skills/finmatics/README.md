# finmatics

Finmatics from your agent. Upload invoices and other documents, read them, change their fields when you ask, create business partners, and get the totals of a month. It does not check documents, does not delete them and does not book or export anything.

## Example requests

- "Upload invoice.pdf to Finmatics."
- "How much did we spend on incoming invoices in September 2026?"
- "Which documents from September come from Example Supplies?"
- "Set the invoice number of this document to RE-100."
- "Create the business partner Example Tools AG with number 70009 and assign it to this document."

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/finmatics ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill finmatics from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
| Name | Kind |
| --- | --- |
| `FINMATICS_PASSWORD` | secret |
| `FINMATICS_USER` | setting |

Hosts the skill talks to: `api.finmatics.com`.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
Connect Finmatics with a user of its own in three steps.

1. In Finmatics, create a user for the agent, without a second factor, and give it a role that can upload and edit documents for the clients it should work with. Reading alone is not enough for `upload` and `update`.
2. Set the user name as `FINMATICS_USER` and the password as `FINMATICS_PASSWORD`.
3. Check the connection: `python scripts/finmatics.py clients`.

The skill talks to `https://api.finmatics.com` and sends the user and password as HTTP Basic on every request, which Finmatics supports. The Finmatics documentation describes a login that returns a token. That login takes the password in the request body, which a credential vault with a proxy cannot fill in, so the skill does not use it.

In a GEKI bot, `FINMATICS_PASSWORD` is a shared credential of the company (an environment variable secret in a vault), and `FINMATICS_USER` is a plain setting. The password must be 8 or more printable ASCII characters without spaces.
<!-- /generated:setup -->

## Tests

<!-- generated:tests -->
- 31 script tests (pytest) run against a small mock with fixtures, on Python 3.11 with only the declared packages.
- 5 agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.
- An optional read-only run against a real account can be started by hand. It is not part of the checks.
<!-- /generated:tests -->

<!-- generated:tested -->
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
