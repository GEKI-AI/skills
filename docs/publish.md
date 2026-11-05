# Publishing to the GEKI catalog

Publishing is a tag. Push a tag that starts with `publish-` on a commit of `main`, for example `publish-2026-11-03`. The workflow `publish.yml` then runs `ci/publish.py`. A merge to `main` publishes nothing. You can also start the workflow by hand on `main`. Its inputs are `only` (skill names) and `dry_run`.

Protect the tag pattern `publish-*` in the repository settings, so only maintainers can create it. The tag is the approval: a maintainer sets it, or an agent on the word of a maintainer.

## Needs

- The repository variable `PUBLISH_ENABLED` is `true`.
- The repository secret `GEKI_PUBLISH_KEY` is a key of the platform org (`GEKI_PLATFORM_ORG_ID` in geki-api), an internal org without users. Only such a key may set `shared_with`. Other keys get `403 staff_only`.
- Optional variable `GEKI_API_URL` (default `https://api.geki.ai`).
- Unless the variable `PUBLISH_REQUIRE_VERIFIED` is `false`, every skill must have a green test result for its current files on the branch `test-results` (see [testing.md](testing.md)). Otherwise nothing is published.

Without `PUBLISH_ENABLED` or the key, the run fails with a message. It is never silently green. Only `dry_run` works without them.

## An agent publishes

A maintainer decides when to publish. An agent takes these steps once a maintainer says so for this release. A green pipeline or an earlier yes is not enough.

1. Start a dry run on `main`: `POST /api/v1/repos/geki/geki-skills/actions/workflows/publish.yml/dispatches` with the JSON body `{"ref": "main", "inputs": {"dry_run": "true"}}`. The token of the maintainer goes into the header `Authorization: token ...`.
2. Read the log: `GET /api/v1/repos/geki/geki-skills/actions/runs/{id}/jobs`, then `GET /api/v1/repos/geki/geki-skills/actions/jobs/{id}/logs`. Its lines say what a real run would do. If a skill would be hidden that nobody expects, stop and ask.
3. Push the tag `publish-YYYY-MM-DD` on the newest commit of `main`, with `-2` at the end if that name is taken.
4. Read the log of that run the same way, and report each line to the maintainer. A failed run published what comes before the error and hid nothing.

## What it does

For each skill the script builds a zip with the folder `<name>/` (without `tests/`). It includes `assets/logo.svg`. In the zipped `SKILL.md` it sets `metadata.geki-tested` (the date of the green result). The `tags` field of the API call is the list in `metadata.geki-tags`. The files in the repo stay as they are. Then it calls the GEKI API:

- The skill is not in the platform org yet: `POST /v1/skills` with the zip, `description`, `tags` and `shared_with=all`.
- It exists: `POST /v1/skills/{id}` with `mode=new_version`. It never sends `overwrite`, so a shared version is never replaced. If the skill is not shared with `all`, the call also sets `shared_with=all`.
- The current version on the platform has `meta.version` equal to or higher than the repo `metadata.version`: skip. The platform's own `current_version` counts uploads and is not compared. A second run does nothing.

So a tag publishes every skill whose version the platform does not have yet. There is no base commit to choose.

## A skill leaves the repo

A run never deletes a skill. After all uploads, it looks for skills of the platform org that are shared with `all`, are not deprecated, and have no folder in the repo. It sets `deprecated=true` on them:

- The catalog hides the skill. Existing pins keep working, and their bots show the warning `skill_deprecated`.
- A skill that is not shared with `all` stays as it is.
- A skill that comes back to the repo gets `deprecated=false` in the next run.
- A run with `only` hides nothing, because it is about the named skills.
- `dry_run` prints which skills it would hide, if the key is there. With the key, its upload lines also compare with the platform: `would create`, `would new_version after N`, or `skip`. Without the key it cannot read the platform and says so.

The API has no call for the flag alone: `deprecated` is a field of `POST /v1/skills/{id}`, and that call needs a `mode`. So the run sends `mode=new_version` without a zip, which adds a version with the same files. `overwrite` is not an option, because it is refused while another org pins the skill.

## The API

The API is described in `services/geki-api/docs/skills.md` in geki-core, section Shared skills. The script uses:

- `GET /v1/skills?scope=own&q=<name>&limit=100`, with `after=<last_id>` while `has_more` is true. Rows have `id`, `name`, `meta.version` and `shared_with`. The script matches the exact name.
- `POST /v1/skills` with the multipart fields `files` (the zip), `name`, `description`, `tags` (a JSON list) and `shared_with`.
- `POST /v1/skills/{id}` with `mode=new_version`, `files`, `description` and `tags`, or with `mode=new_version` and `deprecated` alone.
- The zip keeps one folder `<name>/` with `SKILL.md`. geki-api rewrites the frontmatter only when `name` or `description` is missing.

Change `ci/publish.py` and its tests when the API changes.
