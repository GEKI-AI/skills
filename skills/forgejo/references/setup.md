Connect Forgejo in three steps.

1. In Forgejo, open Settings, then Applications, and create an access token with the scopes `write:issue` and `read:repository`. Use `read:issue` instead if the agent should only read. Add `read:organization` to use the labels of an organization, not only those of the repository. The token has the rights of its user, so for a shared bot create a separate Forgejo user and give it only the repositories it should work in.
2. Set `FORGEJO_TOKEN` to the token. Set `FORGEJO_URL` to the address of your server without a trailing slash, for example `https://git.company.com`.
3. Check the connection: `python scripts/forgejo.py repos --limit 1`. It prints a list with one repository.

In a GEKI bot, `FORGEJO_URL` is a skill setting of the bot. `FORGEJO_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `FORGEJO_URL`. With "each person", issues and comments are written under the name of that person.
