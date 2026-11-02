# Metadata convention

Skills are plain Agent Skills. The standard frontmatter fields are `name`, `description`, `license`, `compatibility` and `metadata`. A vanilla Pi ignores the `metadata` keys below. GEKI reads them to build the setup of a skill.

Rules for the standard fields:

- `name` equals the folder name. Lowercase letters, digits and single hyphens, at most 64 characters.
- `description` is one line, at most 1,024 characters. Say what the skill does and when to use it.
- `license` is `Apache-2.0` (or another permissive license that the license check allows).
- `compatibility` is one human sentence: "Python 3.11+, access to your Example site".

All values under `metadata` are strings. Write each key on one line. The keys start with `geki-`, except `version`.

| Key | Meaning |
| --- | --- |
| `version` | Integer. Raise it in the pull request. CI checks that it increases when the skill changed. |
| `geki-tool` | Tool id (`example`). The folder `tools/<id>/` holds the name, the logo and the website. |
| `geki-category` | `knowledge`, `tickets`, `crm`, `dev`, and so on. |
| `geki-access` | `read`, `write`, or `read, write`. |
| `geki-auth` | Any of `company` (one shared token), `person-token` (each person pastes a token), `person-oauth` (each person signs in). |
| `geki-credentials` | Secret variables, comma-separated. |
| `geki-settings` | Variables that are not secret, for example `EXAMPLE_URL`. |
| `geki-hosts` | Hosts the skill talks to, comma-separated, no scheme, port or path. An entry `$EXAMPLE_URL` means the host of that setting. |
| `geki-oauth-issuer`, `geki-oauth-authorize-url`, `geki-oauth-token-url`, `geki-oauth-scopes` | Optional. Pre-fill an OAuth app. |
| `geki-python`, `geki-npm`, `geki-system` | Packages the skill needs. Comma-separated. |
| `geki-image` | A guest image other than `default`, for example `browser`. |
| `geki-origin` | Set on copies: `example-read@3`. |

All skills of one `geki-tool` use the same `geki-credentials`, `geki-settings` and `geki-hosts`.

A credential name must be an environment variable name that is not reserved. The prefixes `OPENAI_`, `GEKI_`, `PI_`, `CODEX_`, `GIT_` and `AGENT_BROWSER_` are reserved (`GIT_TOKEN`, `GIT_PASSWORD` and `GIT_ACCESS_TOKEN` are allowed), and so are system names such as `PATH`, `HOME` and `USER`. A key takes at most 20 entries.

`ci/validate.py` checks all of this. It follows the rules that GEKI applies when it reads a skill, including how it reads `geki-hosts` and `geki-credentials`. Keep it in line with the parser in geki-api.

Example:

```yaml
---
name: example-read
description: Search and read Example. ...
license: Apache-2.0
compatibility: Python 3.11+, access to your Example site over HTTPS
metadata:
  version: "1"
  geki-tool: example
  geki-category: knowledge
  geki-access: read
  geki-auth: company, person-token
  geki-credentials: EXAMPLE_TOKEN
  geki-settings: EXAMPLE_URL
  geki-hosts: $EXAMPLE_URL
---
```
