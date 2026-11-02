Connect your Zammad instance in three steps.

1. In Zammad, open your profile, then "Token Access", and create a personal access token with the permission `ticket.agent`. The token has the rights of its user, so it can write in every group that user can write in. For a shared bot, create a separate Zammad user and give it only the groups the bot should work in. Install `zammad-read` instead if the agent only needs to read.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py states`. It prints the ticket states of your instance.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`. With "each person", tickets and messages are written under the name of that person.
