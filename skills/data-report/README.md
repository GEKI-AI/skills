# data-report

Advice and a check for an agent that builds a report from data: findings, charts and tables as one standalone HTML file. It is not a template. The agent decides structure and look, the skill keeps the numbers right, the charts honest and the work short.

The data can come from anywhere: CSV, Excel or JSON files, a database, an API. The skill is about what comes out.

<!-- generated:geki -->
**On GEKI Companybots** this skill is in the skill catalog of every organization. [Register](https://console.geki.ai/register?landing=skill-data-report&utm_source=github&utm_medium=readme&utm_campaign=skills&utm_content=data-report) and get free starting credits.
<!-- /generated:geki -->

## Example requests

- "Here are the orders of the last 12 months. Make a report as standalone HTML: revenue, regions, returns, and what else stands out."
- "Build a report for the team meeting from the support tickets and the SLA targets."
- "One page for the management: the three most important things, each with a chart."

## What is in it

- `SKILL.md`: how to work, and rules for numbers, charts, the file and the check. Every number comes out of one script. Parts must add up. A total can hide a part that moved. Bars start at zero. The file opens offline and reads on a phone.
- `scripts/report_check.py`: checks a finished report and prints JSON.

```sh
python scripts/report_check.py report.html --shots shots
python scripts/report_check.py report.html --shots shots --part 1280,2500,3200
```

| It finds | How |
| --- | --- |
| An address outside the file, a missing value shown as `nan` or `None`, a placeholder left in the text | From the file |
| Chart shapes drawn outside the chart area: a wrong scale, the chart looks empty | From the file, and measured in a browser |
| Sideways scrolling, chart labels that overlap or are cut off, charts too small to read | Measured in a browser at 1280 px and 390 px |

With `--shots` it writes one overview picture per width: the whole page as columns, scaled down, with the distance from the top marked every 500 px. `--part` writes one full-size picture between two marks. An agent then looks at two or three pictures and not at thirty.

## With and without a browser

The check looks for a Chrome: `REPORT_CHROME`, `AGENT_BROWSER_EXECUTABLE_PATH`, `CHROME_PATH`, `PUPPETEER_EXECUTABLE_PATH`, then `chrome-headless-shell`, `chromium` or `google-chrome` on the path, then a browser that Playwright installed. `--no-browser` skips it.

Without a Chrome nothing is measured. The check still reads the file, and it draws the pictures with `weasyprint` and `pdftoppm` when both are installed. A PDF engine draws inline SVG and tables like a browser, but not every CSS layout, and it shows no phone. So give the agent a browser when you can. In our test runs the reports made without one were fine on a desktop but sometimes scrolled sideways on a phone.

## Install

<!-- generated:install -->
All skills of the repo as a Pi package (`-l` installs for the current project only):

```sh
pi install git:github.com/GEKI-AI/skills
```

Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):

```sh
git clone --depth 1 https://github.com/GEKI-AI/skills.git /tmp/geki-skills
mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/data-report ~/.agents/skills/
```

Or tell Pi in one sentence:

```text
Install the skill data-report from https://github.com/GEKI-AI/skills into ~/.agents/skills, install what its SKILL.md needs, and tell me which environment variables to set.
```

The skill needs Python 3.11+ and nothing else. It uses the standard library only.
<!-- /generated:install -->

## Variables

<!-- generated:variables -->
The skill needs no variables.
<!-- /generated:variables -->

## Setup

<!-- generated:setup -->
No setup needed.
<!-- /generated:setup -->

In a GEKI bot the skill needs a workspace. Use the `browser` image for the bot when you can: the check then measures the page.

## Tests

<!-- generated:tests -->
- 7 script tests (pytest), on Python 3.11 with only the declared packages.
- 2 agent tasks: a vanilla Pi with a model runs each task on files from the fixtures, up to three times. A task passes with two passing runs, judged by the answer and by the files the agent left.
<!-- /generated:tests -->

<!-- generated:tested -->
No test result is recorded yet.
<!-- /generated:tested -->

See [CHANGELOG.md](CHANGELOG.md) for versions.
