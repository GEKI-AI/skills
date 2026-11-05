# GEKI Skills

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Tested [Agent Skills](https://agentskills.io) for [Pi](https://pi.dev) and for other agents that read the Agent Skills format. A skill is a folder with a `SKILL.md` that tells the agent how to do a task, and a small script that does the work. These skills are integrations for the products a company already uses.

Every skill is tested twice. Its script runs against a mock of the product's API, built from the vendor's OpenAPI spec where one exists. And a vanilla Pi has to finish example tasks with it, checked by the requests the mock saw. You do not need GEKI to use them.

## Skills

<!-- generated:catalog -->
### Knowledge

- [`confluence`](skills/confluence): Search, read and change Confluence Cloud.

### Tickets

- [`zammad-read`](skills/zammad-read): Search and read tickets and knowledge base answers in Zammad.
- [`zammad-write`](skills/zammad-write): Create tickets, reply to tickets and set the ticket state in Zammad.

### CRM

- [`hubspot`](skills/hubspot): Work with HubSpot CRM contacts, companies and deals.

### Development

- [`github`](skills/github): Work with GitHub issues, pull requests, comments and files.
<!-- /generated:catalog -->

Product names and logos belong to their owners. They are used only to identify the products.

Each skill folder has a `README.md` with example requests, the variables it needs, the setup steps, the install line for Pi and the test status.

## Install

You need Pi, and Python 3.11 or newer on the machine where Pi runs.

**All skills, as a Pi package:**

```sh
pi install git:github.com/GEKI-AI/skills
```

Add `-l` to install for the current project only. Add `@ref` (a tag or a commit) to pin a version. `pi list` shows what is installed and `pi update` updates it.

**One skill:** copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills
cp -r /tmp/geki-skills/skills/<skill-name> ~/.agents/skills/
```

**Or tell Pi in one sentence.** Replace `<skill-name>` with the name of the skill:

```text
Install the skill <skill-name> from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

Other agents that read Agent Skills can use the same folders. Check where your agent looks for skills.

## Credentials

A skill reads its secrets from environment variables and sends them only in request headers. It never prints them and never writes them to a file. Set the variables in the shell where you start Pi:

```sh
export EXAMPLE_URL=https://example.com
export EXAMPLE_TOKEN='your-api-token'
```

Skills for the same product use the same variable names, so one setting serves all of them. The README of each skill lists its variables and says how to get the token. Give each token only the rights the agent needs. That is why some products have a `-read` skill and a `-write` skill: you can run an agent with a token that cannot write.

Do not paste tokens into the chat with the agent.

## How skills are tested

- **Static checks**: the Agent Skills reference validator (`skills-ref`), a check of the metadata rules, a secret scan, lint, a license check, and a check that a changed skill has a higher `version` and a changelog entry.
- **Script tests** with pytest against a mock. Where the vendor publishes an OpenAPI spec, the mock is [Prism](https://github.com/stoplightio/prism) built from that spec, which rejects requests that do not match it. Without a spec, the skill brings a small mock server with fixtures. The scripts run on Python 3.11 with only the packages the skill declares.
- **Agent tests**: a vanilla Pi with a model runs each task in `tests/tasks/` against the mock, up to three times. A task passes with two passing runs. The check reads the requests the mock logged: the right calls with the right fields on writes, and no forbidden calls.
- **Real-API run** (optional, by hand, read only, against test accounts). It finds drift between the real API and the fixtures. It is not part of the checks above.

The tests run in CI on every change, and only for the skills the change touches. A skill whose files and test setup have a green result is not tested again. The oldest results are refreshed every night. A skill is never reported as tested without a test run. The README of each skill shows when it was last verified and with which model.

How to run them locally is in [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/testing.md](docs/testing.md).

## GEKI

[GEKI](https://geki.ai) offers these skills in its managed agent API and in its products: Companybots, the Console and Chat. There you pick a skill from the catalog and connect it without environment variables: the setup comes from the skill's metadata (the address, the kind of sign-in, the allowed hosts). The skills in the catalog are published from this repository. The documentation is at [docs.geki.ai](https://docs.geki.ai).

## Contributing

Issues and pull requests here on GitHub are welcome. This repository is a mirror: the development and the CI run on GEKI's own Forgejo, and we apply pull requests from GitHub there by hand. For now the GEKI team writes the skills and reviews every pull request. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. To report a security problem, read [SECURITY.md](SECURITY.md). Everyone follows the [Code of Conduct](CODE_OF_CONDUCT.md).

The repository changes are listed in [CHANGELOG.md](CHANGELOG.md). Licensed under [Apache 2.0](LICENSE).
