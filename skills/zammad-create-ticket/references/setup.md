Connect your Zammad instance in three steps.

1. In Zammad, open your profile, then "Token Access", and create a personal access token. The permission `ticket.customer` is enough to create tickets for the owner of the token. To create tickets for other customers, the token needs `ticket.agent`, and the user must have access to the group. For a shared bot, create a separate Zammad user and give it only the groups the bot should create tickets in.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py me`. It prints the user of the token.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

The skill cannot list groups. If your users do not know the group names, name the right group in the instructions of the bot.

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`. With "each person", tickets are created under the name of that person.
