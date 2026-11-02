Connect your Zammad instance in three steps.

1. In Zammad, open your profile, then "Token Access", and create a personal access token. Give it the permission `ticket.agent` (read and write tickets) or `ticket.customer`. The token has the rights of its user. This skill only reads, but the token does not enforce that. Use a user with read access only to the groups the agent may see. For a shared bot, create a separate Zammad user for it.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py search '*' --limit 1`. It prints a list with one ticket.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`.
