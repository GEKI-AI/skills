This repository is a mirror. A maintainer applies the pull request on GEKI's Forgejo, where the CI runs.

## What changes

<!-- One change per pull request. -->

## Checklist

- [ ] `metadata.version` is raised and `CHANGELOG.md` has an entry (when a skill changed)
- [ ] `python ci/catalog.py` was run
- [ ] Tests cover the change (script tests, and an agent task for new behaviour)
- [ ] Secrets go only into request headers and are never printed
