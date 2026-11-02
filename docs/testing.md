# Testing

## The mock

`ci/mockserver.py` is a small HTTP server. It answers from `skills/<name>/tests/fixtures/routes.json` and logs every request (method, path, query, headers, JSON body). Each route has `method`, `path` (with `{name}` parts), optional `query` and `json` conditions, `status` and a `body` or a `file`. The first route that matches wins, so put the specific ones first.

For tools with a vendor OpenAPI spec, the mock first passes each request to a [Prism](https://github.com/stoplightio/prism) mock built from that spec. Prism rejects a request that does not match the spec, and the test fails with the reason. When Prism accepts the request, the answer comes from the fixture, so the script sees realistic data. The specs are listed with pinned URLs in `ci/specs.json`. `ci/mocks.py start <tool>` downloads them, starts Prism and prints `MOCK_UPSTREAM_<TOOL>=...`. Export that line before `pytest`.

Prism checks the request against the spec, not against the real service. A spec can be stricter or looser than the real API. Examples we met: the HubSpot search spec requires `after` and `sorts`, and the Confluence v2 spec lists a page body as `oneOf` two schemas that both match. `ci/specs.json` has a `fixups` field for the rare cases where the spec is wrong. The weekly real-API run finds the rest.

Tools without a spec (Zammad) use the fixtures only.

## Script tests

`skills/<name>/tests/test_*.py`, with the fixtures `cli` and `mock` from the root `conftest.py`:

```python
def test_search(cli, mock):
    result = cli("search", "printer")
    assert result.code == 0
    assert result.json["results"][0]["id"] == 42
    assert mock.requests[0]["query"]["query"] == "printer"
```

`cli` runs the script of the skill in a clean environment with the variables of the tool pointing to the mock (see `TEST_ENV` in `ci/common.py`). Set `SKILL_PYTHON` to run the script with another interpreter, as CI does for the "declared packages only" environment.

Test what the script sends (path, fields, headers), what it prints, and the error cases. Mark a read-only test against the real service with `@pytest.mark.real_api`: it uses the `real_cli` fixture and runs only with `REAL_API=1` and the real variables.

## Agent tasks

`skills/<name>/tests/tasks/*.yaml`:

```yaml
name: create-ticket
prompt: Open a Zammad ticket "Printer offline" in group Users for anna@example.com.
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

`python ci/agent_test.py` runs every task three times with a vanilla Pi and a GEKI model (`GEKI_API_KEY`, default model `deepseek-v4.1-flash`, base URL `https://api.geki.ai/v1`). A task passes with two of three runs. The skill is installed like a user would do it: copied to `~/.agents/skills` of an empty home. Write tasks the way a user asks, not the way the script works.

`ci/tests/` tests the runner itself with a scripted fake model, so it runs without a key.
