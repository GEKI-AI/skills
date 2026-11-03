# Testing

The source of truth of this repository is `geki/geki-skills` on GEKI's Forgejo. The CI runs there (`.forgejo/workflows/`). The repository on GitHub is a mirror without Actions.

## What runs

One workflow, `Skills` (`skills.yml`), on every pull request, on every push to `main`, every night, and by hand.

| Job | What it does |
| --- | --- |
| `plan` | Decides which skills need a test run. |
| `static` | Metadata rules, `skills-ref`, generated READMEs, lint, license check, version and changelog check, secret scan, tests of the CI code. |
| `scripts` | The script tests of the planned skills, against the mocks. |
| `agents` | The agent tasks of the planned skills, with a vanilla Pi and a model. |
| `tests` | The one check that sums up all jobs. Branch protection requires only this check. |

The check name on Forgejo is `Skills / tests (pull_request)` for pull requests and `Skills / tests (push)` for `main`.

The workflow never reports green without a test. A missing `GEKI_API_KEY` fails the `agents` job. A skill without tests fails. The GEKI image job that cannot run is listed as "NOT RUN" in the report of the `tests` job, not as a pass.

## Test only what changed

`ci/affected.py` maps the changed files to skills:

- `skills/<name>/...` is that skill.
- `ci/specs.json` is every skill whose entries in it changed.
- Documentation (`*.md` in the root, `docs/`, `.github/`, `LICENSE`, `NOTICE`, `package.json`) is nothing.
- Everything else (`ci/`, `.forgejo/`, `conftest.py`, new files) is every skill.

The skills come from the folders of the repo. There is no list in the workflows.

## Results are remembered by fingerprint

`ci/fingerprint.py` hashes everything a test result depends on:

- the skill folder, without `README.md` and `CHANGELOG.md`
- the mock specs of the skill in `ci/specs.json`
- the versions of Pi and Prism (`ci/pins.env`), and the Python version of the empty environment
- the test model, the judge model and the model base URL
- the runner code (`RUNNER_FILES` in `ci/fingerprint.py`)

When all tests of a skill are green, CI saves a small JSON file for the skill on the branch `test-results`: the fingerprint, the date, the run URL, the model and the pass counts. A skill whose current fingerprint has a green result is reported as "already verified in run N" and is not tested again. A pull request that is merged unchanged therefore costs nothing on `main`.

The branch `test-results` is written only by CI. `TESTED.md` on that branch lists the last results. To put the dates into the READMEs, copy the results and regenerate:

```sh
python ci/results.py export .cache/results
python ci/catalog.py --results .cache/results
```

Commit the changed READMEs in a normal pull request. CI cannot push to `main`.

CI pushes the branch with the built-in token (`contents: write`). If Forgejo does not allow that for a run, add the secret `RESULTS_TOKEN` (a token of a CI user with write access to this repository). When a push fails, CI prints a warning and the next run tests the skill again. The nightly run fails in that case, so someone notices.

## Nightly run

The schedule tests every skill without a green result for its fingerprint, plus the `N` skills whose last verification is oldest. `N` is the repository variable `NIGHTLY_SKILLS` (default 10). A skill that fails in the nightly refresh keeps its old result and is picked again the next night.

## By hand

Start the workflow `Skills` by hand to test one branch. The input `skills` takes names separated by commas (empty: all). The input `force` tests skills that already have a green result.

## Pull requests from forks

On GitHub only the mirror exists, so there are no pull requests from forks on Forgejo. A maintainer applies a GitHub pull request by hand as a branch in the Forgejo repository. That branch gets the secrets and the full tests.

## Setup on Forgejo

Secrets: `GEKI_API_KEY` (a key with the Models preset, a short expiry and a budget). Optional: `RESULTS_TOKEN`. Variables, all optional: `AGENT_TEST_MODEL`, `AGENT_TEST_BASE_URL`, `AGENT_JUDGE_MODEL`, `NIGHTLY_SKILLS`. Branch protection on `main` requires the check `Skills / tests (pull_request)`.

The runner label is `datenhof-ci`. It has Python, uv, Node and Docker. `ci/setup.sh` adds only what the repo needs (Pi, Prism, gitleaks, `skills-ref`) and the workflows cache it. The versions are in `ci/pins.env`.

## The mock

`ci/mockserver.py` is a small HTTP server. It answers from `skills/<name>/tests/fixtures/routes.json` and logs every request (method, path, query, headers, JSON body). Each route has `method`, `path` (with `{name}` parts), optional `query` and `json` conditions, `status` and a `body` or a `file`. The first route that matches wins, so put the specific ones first.

For skills with a vendor OpenAPI spec, the mock first passes each request to a [Prism](https://github.com/stoplightio/prism) mock built from that spec. Prism rejects a request that does not match the spec, and the test fails with the reason. When Prism accepts the request, the answer comes from the fixture, so the script sees realistic data. The specs are listed with pinned URLs in `ci/specs.json`, a list where each entry names the skills that use it (`"skills": ["confluence-read", "confluence-write"]`). `ci/mocks.py start <skill>` downloads the specs of that skill, starts Prism and prints `MOCK_UPSTREAM=...`. Export that line before `pytest`, or let `python ci/run_scripts.py --skills <names>` do it.

Prism checks the request against the spec, not against the real service. A spec can be stricter or looser than the real API. Examples we met: a search spec that requires paging fields the real API does not need, and a spec that lists a body as `oneOf` two schemas that both match. `ci/specs.json` has a `fixups` field for the rare cases where the spec is wrong. A real-API run, started by hand, finds the rest.

Skills without a spec use the fixtures only.

## Script tests

`skills/<name>/tests/test_*.py`, with the fixtures `cli` and `mock` from the root `conftest.py`:

```python
def test_search(cli, mock):
    result = cli("search", "printer")
    assert result.code == 0
    assert result.json["results"][0]["id"] == 42
    assert mock.requests[0]["query"]["query"] == "printer"
```

`cli` runs the script of the skill in a clean environment with the variables of the skill pointing to the mock (see `TEST_ENV` in `ci/common.py`, one entry per skill). Set `SKILL_PYTHON` to run the script with another interpreter.

`python ci/run_scripts.py --skills a,b` is what CI runs. For each skill it starts the Prism mocks, builds a fresh venv of Python 3.11 that holds only the packages the skill declares, and runs its tests with `SKILL_PYTHON` set to that venv. An undeclared import fails. A skill is green only when no test failed and at least one test passed.

Test what the script sends (path, fields, headers), what it prints, and the error cases. Mark a read-only test against the real service with `@pytest.mark.real_api`: it uses the `real_cli` fixture and runs only with `REAL_API=1` and the real variables.

The real-API run is the workflow `Real API`. It is manual and optional: it runs only when someone starts it, with an optional `skills` input (names, comma-separated). It never affects `Skills / tests`, publishing, the saved test results or the READMEs. Started without the variables of a skill, it fails loudly. Normal testing uses only the specs, the mocks and the agent tasks.

## The GEKI image

The GEKI sandbox image is built by `geki-core` as a Firecracker root filesystem (`rootfs.ext4`) and stored in an object store. It is not a Docker image in the registry, so CI cannot run a job in it yet. Once a Docker image of the guest exists, a job runs the script tests inside it (`ci/run_scripts.py --env image`) and reports declared packages that the image lacks. Until then the report of the `tests` job says "GEKI image: NOT RUN". `ci/image_report.py` still compares the declared packages with a copy of the image's package list (`ci/geki-image-python.txt`).

## Agent tasks

`skills/<name>/tests/tasks/*.yaml`:

```yaml
name: create-ticket
prompt: Open a ticket "Printer offline" in group Users for anna@example.com.
expect:
  requests:            # each needs a match in the mock log
    - method: POST
      path: /api/v1/tickets
      json: {title: Printer offline, group: Users}
  forbidden:           # none may match
    - method: [DELETE]
  answer_contains: ["52043"]
```

A value that starts with `re:` is a regular expression. A `json` condition is a subset of the logged body. Optional `judge:` is a sentence that a cheap model (`AGENT_JUDGE_MODEL`) checks against the answer.

`python ci/agent_test.py` runs every task with a vanilla Pi and a GEKI model (`GEKI_API_KEY`, default model `deepseek-v4.1-flash`, base URL `https://api.geki.ai/v1`). A task passes with two passing runs out of three. It stops as soon as it has two passes, and as soon as it has two failures. Without `GEKI_API_KEY` the script fails. The skill is installed like a user would do it: copied to `~/.agents/skills` of an empty home. Write tasks the way a user asks, not the way the script works.

`ci/tests/` tests the runner itself with a scripted fake model, so it runs without a key. It also tests the change detection, the fingerprint, the result store and the verdict of the `tests` job.
