# GEKI Skills

[![CI](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml/badge.svg)](https://github.com/GEKI-AI/skills/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Tested [Agent Skills](https://agentskills.io) for [Pi](https://pi.dev) and for other agents that read the Agent Skills format. A skill is a folder with a `SKILL.md` that tells the agent how to do a task, and a small script that does the work. These skills connect an agent to the tools a company already uses: Confluence, Zammad, GitHub, HubSpot.

Every skill is tested twice. Its script runs against a mock of the vendor's API, built from the vendor's OpenAPI spec where one exists. And a vanilla Pi has to finish example tasks with it, checked by the requests the mock saw. You do not need GEKI to use them.

## Skills

<!-- generated:catalog -->
| Tool | Skill | What it does | Access | Sign-in |
| --- | --- | --- | --- | --- |
| <img src="tools/confluence/logo.svg" alt="" width="20" height="20"> [Confluence](https://www.atlassian.com/software/confluence) | [`confluence-read`](skills/confluence-read) | Search and read Confluence Cloud. | read | company token, personal token |
| <img src="tools/confluence/logo.svg" alt="" width="20" height="20"> [Confluence](https://www.atlassian.com/software/confluence) | [`confluence-write`](skills/confluence-write) | Create and update pages in Confluence Cloud and add comments. | write | company token, personal token |
| <img src="tools/github/logo.svg" alt="" width="20" height="20"> [GitHub](https://github.com) | [`github`](skills/github) | Work with GitHub issues, pull requests, comments and files. | read, write | company token, personal token |
| <img src="tools/hubspot/logo.svg" alt="" width="20" height="20"> [HubSpot](https://www.hubspot.com) | [`hubspot`](skills/hubspot) | Work with HubSpot CRM contacts, companies and deals. | read, write | company token |
| <img src="tools/zammad/logo.svg" alt="" width="20" height="20"> [Zammad](https://zammad.com) | [`zammad-read`](skills/zammad-read) | Search and read tickets and knowledge base answers in Zammad. | read | company token, personal token |
| <img src="tools/zammad/logo.svg" alt="" width="20" height="20"> [Zammad](https://zammad.com) | [`zammad-write`](skills/zammad-write) | Create tickets, reply to tickets and set the ticket state in Zammad. | write | company token, personal token |
<!-- /generated:catalog -->

Tool names and logos belong to their owners. They are used only to identify the tool.

Each skill folder has a `README.md` with example requests, the variables it needs, the setup steps and the test status.

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
cp -r /tmp/geki-skills/skills/confluence-read ~/.agents/skills/
```

**Or tell Pi in one sentence.** Copy the sentence of the skill you want:

<!-- generated:ask-pi -->
**confluence-read**

```text
Install the skill confluence-read from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

**confluence-write**

```text
Install the skill confluence-write from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

**github**

```text
Install the skill github from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

**hubspot**

```text
Install the skill hubspot from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

**zammad-read**

```text
Install the skill zammad-read from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

**zammad-write**

```text
Install the skill zammad-write from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```
<!-- /generated:ask-pi -->

Other agents that read Agent Skills can use the same folders. Check where your agent looks for skills.

## Credentials

A skill reads its secrets from environment variables and sends them only in request headers. It never prints them and never writes them to a file. Set the variables in the shell where you start Pi:

```sh
export CONFLUENCE_URL=https://company.atlassian.net
export CONFLUENCE_TOKEN='you@company.com:your-api-token'
```

All skills of one tool use the same variable names, so one setting serves `confluence-read` and `confluence-write`. The README of each skill lists its variables and says how to get the token. Give each token only the rights the agent needs. That is why some tools have a `-read` skill and a `-write` skill: you can run an agent with a token that cannot write.

Do not paste tokens into the chat with the agent.

## How skills are tested

- **Static checks** on every pull request: the Agent Skills reference validator (`skills-ref`), a check of the metadata rules, a secret scan, lint, a license check, and a check that a changed skill has a higher `version` and a changelog entry.
- **Script tests** with pytest against a mock. Where the vendor publishes an OpenAPI spec, the mock is [Prism](https://github.com/stoplightio/prism) built from that spec, which rejects requests that do not match it. For Zammad the mock is a small server with fixtures. The tests run on `python:3.11-slim` with only the packages the skill declares.
- **Agent tests**: a vanilla Pi with a model runs each task in `tests/tasks/` against the mock, three times. A task passes with two of three runs. The check reads the requests the mock logged: the right calls with the right fields on writes, and no forbidden calls.
- **Weekly real-API run**, read only, against test accounts. It finds drift between the real API and the fixtures.

How to run them locally is in [CONTRIBUTING.md](CONTRIBUTING.md).

## GEKI

[GEKI](https://geki.ai) offers these skills in its managed agent API and in its products: Companybots, the Console and Chat. There you pick a skill from the catalog and connect it without environment variables: the setup comes from the skill's metadata (the address, the kind of sign-in, the allowed hosts). The skills in the catalog are published from this repository. The documentation is at [docs.geki.ai](https://docs.geki.ai).

## Contributing

Pull requests and new tool requests are welcome. For now the GEKI team writes the skills and reviews every pull request. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. To report a security problem, read [SECURITY.md](SECURITY.md). Everyone follows the [Code of Conduct](CODE_OF_CONDUCT.md).

The repository changes are listed in [CHANGELOG.md](CHANGELOG.md). Licensed under [Apache 2.0](LICENSE).
