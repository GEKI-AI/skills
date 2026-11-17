# web-app-automation

Advice for an agent that works through a web app in a browser on its own: test the app and report the bugs, write end-to-end tests for it, or carry out a process with many steps in it. It is not a procedure and it has no script. The agent decides how it goes through the app. The skill keeps the work short and the result true.

The skill names no tool. It fits any browser the agent can drive from the shell.

<!-- generated:geki -->
**On GEKI Companybots** this skill is in the skill catalog of every organization. [Register](https://console.geki.ai/register?landing=skill-web-app-automation&utm_source=github&utm_medium=readme&utm_campaign=skills&utm_content=web-app-automation) and get free starting credits.
<!-- /generated:geki -->

## Example requests

- "Test our stock app thoroughly and write me a bug report: what does not work, and how can I reproduce it?"
- "Write end-to-end tests for sign-in, creating and deleting an item, the search, and an order. I want to run them after every update."
- "orders.csv has this week's orders. Enter them in the app and give me the export of the orders afterwards."

## What is in it

`SKILL.md` only:

- How to work: look around first, put steps that belong together into one call, script a flow the second time, read little, wait for a thing and not for a time.
- Check the state, not the message: read the result where a user looks for it, open a saved record again, take the cancel path too, count the numbers the page states.
- Testing an app: what to try on lists, input and the session, and what a finding needs before it goes into the report.
- Writing end-to-end tests: tests that make their own data and assert the stored state, a known bug as an expected failure, and what to hand over.
- Carrying out a process: read all the input first, ask once, never guess a record, keep a log, and compare both sides at the end.

## What it changes

We ran three tasks on a small practice app with eleven planted bugs, each twice without the skill and twice with it. The skill did not make the agent faster. It made the result better:

| Task | Without the skill | With the skill |
| --- | --- | --- |
| Find the bugs | 8 and 9 of 11 | 10 and 10 of 11 |
| Write end-to-end tests | 7 bugs kept as expected failures | 8 |
| Enter orders from a file | correct | correct, and every order read back |

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/web-app-automation ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill web-app-automation from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill is a `SKILL.md` without a script. It needs no packages.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
The skill needs no variables.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
No setup needed.
<!-- /generated:setup -->

The agent needs a browser. In a GEKI bot use the `browser` image.

## Tests

<!-- generated:tests -->
- No script tests: the skill has no script.
- 2 agent tasks: a vanilla Pi with a model runs each task on files from the fixtures, up to three times. A task passes with two passing runs, judged by the answer and by the files the agent left.
<!-- /generated:tests -->

The agent tasks run without a browser: the agent reviews an end-to-end test, and it says which rows of a file it would enter in an app when nobody can answer. The work in a browser is not part of the checks. We tested it by hand, see above.

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
