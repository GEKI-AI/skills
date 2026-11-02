# Contributing

Thanks for helping. This guide is short for now. It gets its final form, with a skill template, after the first tools have proven the pattern.

At first the GEKI team writes the skills. Every pull request gets a review. Bug reports, ideas for tools and small fixes are welcome from everyone.

## What belongs here

A skill that connects an agent to a tool through its API: one folder in `skills/`, one folder for the tool in `tools/`. Name a skill by tool and task, for example `confluence-read`. Make a `-read` and a `-write` skill only when the split matters for access rights. Otherwise make one skill.

Skills that need features of one product (workspace files, chat cards) do not belong here.

## A skill folder

```
skills/<name>/
  SKILL.md           short, under about 5,000 tokens
  README.md          for people: what it does, examples, install, variables, setup, tests
  CHANGELOG.md       one entry per version
  scripts/           one CLI with subcommands and JSON output
  references/        setup.md is required when the skill needs credentials
  tests/             script tests, fixtures, agent tasks
tools/<tool>/
  tool.yaml          name, category, website
  logo.svg
```

The rules for `SKILL.md` and its `metadata` are in [docs/metadata.md](docs/metadata.md). The skill folder is what users install, so it must not depend on anything outside it.

## Scripts

- Python 3.11 or newer. The standard library plus packages that you declare in `metadata.geki-python`. Use JavaScript only when it is clearly better, for example a vendor SDK that exists only for Node.
- No install at run time inside the script.
- The base URL comes from an environment variable with a default (`HUBSPOT_BASE_URL`). For a tool with its own instance the URL is a required setting (`ZAMMAD_URL`). Tests point it at the mock.
- Secrets come only from environment variables and go only into request headers. Never print them, never put them in a URL, a file or an error message.
- Subcommands print JSON on stdout. An error is JSON on stderr and exit code 1.
- All skills of one tool use the same variable names.

## Tests

Each skill needs script tests and agent tasks. [docs/testing.md](docs/testing.md) explains the mocks, the fixtures and the task format.

Run everything that does not need a secret:

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r ci/requirements.txt
python ci/validate.py
python ci/catalog.py --check
ruff check . && ruff format --check .
pytest
```

`pytest` runs the script tests against the fixture mock. To also check requests against the vendor spec, install Prism (`npm install --prefix .cache/prism @stoplight/prism-cli@5.16.0`), start it with `python ci/mocks.py start <tool>` and export the `MOCK_UPSTREAM_...` line it prints.

`python ci/catalog.py` rewrites the generated parts of the READMEs. Run it after you change metadata, `references/setup.md` or tests.

## Pull requests

1. One change per pull request. Conventional Commit titles (`feat(zammad-read): ...`, `fix(github): ...`).
2. When a skill changes, raise `metadata.version` by one and add an entry to its `CHANGELOG.md`. Changes only to `tests/` or the skill `README.md` do not need a new version.
3. CI must be green. Pull requests from forks get the static checks and script tests. A maintainer moves the branch into this repository to run the agent tests.
4. A maintainer reviews every pull request. The review looks at what the script sends, where the secret goes, and whether the tests would catch a wrong call.

New tool? Open an issue with the "New tool" template first.
