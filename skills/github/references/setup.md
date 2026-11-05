Connect GitHub in two steps.

1. Create a token. Prefer a fine-grained personal access token (GitHub, Settings, Developer settings, Personal access tokens, Fine-grained tokens). Choose only the repositories the agent should use. Give it the repository permissions "Issues: Read and write", "Pull requests: Read and write" and "Contents: Read-only". Drop the write permissions if the agent should only read. If the agent should push code, use "Contents: Read and write", and add "Workflows: Read and write" if it should also change GitHub Actions workflow files. A classic token needs the scope `repo` (or `public_repo` for public repositories only) and gives much wider rights. It needs the scope `workflow` for workflow files.
2. Set `GITHUB_TOKEN` to the token. The skill talks to `https://api.github.com`. To use it with GitHub Enterprise, set `GITHUB_BASE_URL` to the API address of your server, and clone from the address of your server.

Check the connection: `python scripts/github.py prs OWNER/NAME --limit 1`.

In a GEKI bot, `GITHUB_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed hosts are `api.github.com` and `github.com`, and git over HTTPS to `github.com` works with the same credential. With "each person", issues, comments and pushes are made under the name of that person.
