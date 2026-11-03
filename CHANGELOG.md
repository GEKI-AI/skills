# Changelog

Changes to the repository. Each skill has its own `CHANGELOG.md`.

## Unreleased

- First skills, grouped by category in the README. Each skill has free tags and an optional logo.
- CI on GEKI's Forgejo (this repository on GitHub is a mirror): skill validator, `skills-ref`, secret scan, lint, license check, version check, script tests against Prism mocks and fixture mocks, agent tests with a vanilla Pi, a real-API run started by hand.
- Only the skills a change touches are tested. Green results are remembered by a fingerprint of the files and the test setup. The nightly run refreshes the oldest results. One check, `Skills / tests`, sums everything up. A run without a model key or without tests fails.
- Publish to the GEKI skills catalog on a `publish-*` tag.
