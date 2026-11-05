# AGENTS.md — GEKI Skills

Instructions for agents that work on this repository. People start with [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md). This file says where things are and what to watch.

## Where to read

| Topic | File |
| --- | --- |
| What a skill folder holds, script rules, local checks, PR rules | [CONTRIBUTING.md](CONTRIBUTING.md) |
| `SKILL.md` frontmatter and every `metadata` key | [docs/metadata.md](docs/metadata.md) |
| CI jobs, mocks, fixtures, agent tasks, test results | [docs/testing.md](docs/testing.md) |
| Publishing to the GEKI catalog | [docs/publish.md](docs/publish.md) |
| The skills API on the GEKI side | `services/geki-api/docs/skills.md` in geki-core |

## The repository

- The source is `geki/geki-skills` on GEKI's Forgejo. Work, CI, and publishing happen there. `GEKI-AI/skills` on GitHub is a push mirror without Actions.
- `skills/<name>/` is one skill. It is what users install, so it depends on nothing outside its folder.
- `ci/` holds the checks, the mock server, the test runners, and the publish script. `ci/tests/` tests them.
- `conftest.py` gives the script tests the `cli` and `mock` fixtures.
- The branch `test-results` is written only by CI.

## Change a skill

1. Change the files in `skills/<name>/`. Keep `SKILL.md` short and the script one CLI with JSON output.
2. Raise `metadata.version` by one and add an entry to the skill's `CHANGELOG.md`. Changes only to `tests/` or the skill `README.md` need no new version. CI fails otherwise.
3. Add or adapt script tests and agent tasks in `skills/<name>/tests/`. Test what the script sends, not only what it prints.
4. Run `python ci/catalog.py` when you changed metadata, `references/setup.md`, or tests. It rewrites the generated parts of the READMEs. Never edit between the `generated:` markers by hand.
5. Run the local checks of CONTRIBUTING.md.

A new skill copies the folder layout of an existing one, sets its test variables in `tests/env.json`, and adds its spec to `ci/specs.json` when the vendor publishes an OpenAPI spec.

## Rules

- Secrets come only from environment variables and go only into request headers. Never into a URL, a file, a log, or an error message.
- No real tokens, hosts of customers, or personal data in fixtures. Use `example.com` hosts and made-up data.
- No names of real companies or people in skills, fixtures, tests, or examples: no customer, partner, employer, or person. The tool and its vendor are fine. No check finds names, so leave them out before you commit. The reviewer checks every name in the PR.
- Facts about a product's API come from the vendor documentation or its spec. Do not invent endpoints or fields.
- `metadata` must stay readable by a vanilla Pi and by geki-api. `ci/validate.py` follows the parser in geki-api. Change both together.
- Skills that need GEKI features (workspace files, Knowledge Bases, chat cards) do not belong here.
- The repo is public under Apache 2.0. Write nothing internal: no internal host names, no customer or partner names.

## Commits and pull requests

- Conventional Commits: `feat(<skill>): ...`, `fix(<skill>): ...`, `fix(ci): ...`, `docs: ...`. One change per PR.
- No tool attribution in commits or PR descriptions: no co-author trailers of AI tools and no "Generated with" lines. The mirror makes them public.
- A squash merge uses the PR title and description as the commit message (`.forgejo/default_merge_message/SQUASH_TEMPLATE.md`). Write both as the final commit.
- `main` requires the check `Skills / tests (pull_request)`, no approval. A maintainer merges when it is green, or an agent when a maintainer says so for this pull request.
- A merge publishes nothing. Publishing is its own step, a `publish-*` tag. A maintainer decides when it happens. Never publish on your own. When a maintainer says so for this release, follow [An agent publishes](docs/publish.md#an-agent-publishes).
