# Publishing to the GEKI catalog

Publishing is a tag. Push a tag that starts with `publish-` on a commit of `main`, for example `publish-2026-11-03`. The workflow `publish.yml` then runs `ci/publish.py`. A merge to `main` publishes nothing. You can also start the workflow by hand on `main`. Its inputs are `only` (skill names) and `dry_run`.

Protect the tag pattern `publish-*` in the repository settings, so only maintainers can create it. The tag is the approval.

## Needs

- The repository variable `PUBLISH_ENABLED` is `true`.
- The repository secret `GEKI_PUBLISH_KEY` is a key of the platform org (`GEKI_PLATFORM_ORG_ID` in geki-api), an internal org without users. Only such a key may set `shared_with`. Other keys get `403 staff_only`.
- Optional variable `GEKI_API_URL` (default `https://api.geki.ai`).
- Unless the variable `PUBLISH_REQUIRE_VERIFIED` is `false`, every skill must have a green test result for its current files on the branch `test-results` (see [testing.md](testing.md)). Otherwise nothing is published.

Without `PUBLISH_ENABLED` or the key, the run fails with a message. It is never silently green. Only `dry_run` works without them.

## What it does

For each skill the script builds a zip with the folder `<name>/` (without `tests/`). It includes `assets/logo.svg`. In the zipped `SKILL.md` it sets `metadata.geki-tested` (the date of the green result). The `tags` field of the API call is the list in `metadata.geki-tags`. The files in the repo stay as they are. Then it calls the GEKI API:

- The skill is not in the platform org yet: `POST /v1/skills` with the zip, `description`, `tags` and `shared_with=all`.
- It exists: `POST /v1/skills/{id}` with `mode=new_version`. It never sends `overwrite`, so a shared version is never replaced. If the skill is not shared with `all`, the call also sets `shared_with=all`.
- The current version on the platform has `meta.version` equal to or higher than the repo `metadata.version`: skip. The platform's own `current_version` counts uploads and is not compared. A second run does nothing.

So a tag publishes every skill whose version the platform does not have yet. There is no base commit to choose.

## The API

The API is described in `services/geki-api/docs/skills.md` in geki-core, section Shared skills. The script uses:

- `GET /v1/skills?scope=own&q=<name>&limit=100`, with `after=<last_id>` while `has_more` is true. Rows have `id`, `name`, `meta.version` and `shared_with`. The script matches the exact name.
- `POST /v1/skills` with the multipart fields `files` (the zip), `name`, `description`, `tags` (a JSON list) and `shared_with`.
- `POST /v1/skills/{id}` with `mode=new_version`, `files`, `description` and `tags`.
- The zip keeps one folder `<name>/` with `SKILL.md`. geki-api rewrites the frontmatter only when `name` or `description` is missing.

Change `ci/publish.py` and its tests when the API changes.
