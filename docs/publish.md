# Publishing to the GEKI catalog

A merge to `main` starts the workflow `publish.yml`. It finds the skills whose `metadata.version` is higher than before the merge, or that are new. Then a job in the GitHub environment `publish` runs `ci/publish.py`. The environment needs approval by a reviewer before every run.

For each skill the script builds a zip with the folder `<name>/` (without `tests/`) plus `assets/logo.svg` from `tools/<tool>/`, and calls the GEKI API with the key `GEKI_PUBLISH_KEY`:

- the skill is not in the GEKI org yet: `POST /v1/skills` with the zip, `description`, `tags` and `shared_with=all`.
- it exists: `POST /v1/skills/{id}` with `mode=new_version`. It never sends `overwrite`, so a shared version is never replaced.
- the platform already has a version number equal to or higher than the repo `version`: skip. This makes a re-run safe.

Nothing is sent unless the repository variable `PUBLISH_ENABLED` is `true` and the key exists. Otherwise the job is skipped or prints a dry run.

## Assumptions about the API

The shared-skills API of geki-api is in development. The script assumes:

- `GET /v1/skills?scope=own&q=<name>&limit=100` returns `{"data": [...]}` with rows that have `id`, `name` and the current `version` (or `current_version`).
- `POST /v1/skills` takes the multipart fields `files` (the zip), `name`, `description`, `tags` (a JSON list) and `shared_with` (`none` or `all`). Only a staff or system key may set `all`.
- `POST /v1/skills/{id}` takes `mode=new_version`, `files`, `description` and `tags`.
- The key may write only skills of the GEKI org.

Change `ci/publish.py` and its tests when the API differs.
