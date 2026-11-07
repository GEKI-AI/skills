Connect your Zammad instance in three steps.

1. In Zammad, open your profile, then "Token Access", and create a personal access token with the permission `ticket.agent`. Add `knowledge_base.reader` for the knowledge base commands. The token has the rights of its user, so it can read and write in every group that user can. For a shared bot, create a separate Zammad user and give it only the groups the bot should work in. Install `zammad-create-ticket` instead if the agent should only create tickets.
2. Set `ZAMMAD_TOKEN` to the token. Set `ZAMMAD_URL` to the address of your instance without a trailing slash, for example `https://support.company.com`.
3. Check the connection: `python scripts/zammad.py states`. It prints the ticket states of your instance.

Optional: set `ZAMMAD_EMAIL` to `off` when the agent must never send email. The script then refuses replies of type `email`, and the agent can only write notes. Without it, email is on.

The Zammad API must be enabled: Settings, System, API, "API Token Access".

In a GEKI bot, `ZAMMAD_URL` is a skill setting of the bot. `ZAMMAD_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `ZAMMAD_URL`. With "each person", tickets and messages are written under the name of that person.

### Start a GEKI bot for each new ticket

A Zammad webhook can start a bot for every new ticket.

1. In GEKI, add an on-demand trigger to the bot. Copy its URL and its token.
2. In Zammad, open Admin, Manage, Webhook, and add a webhook. Endpoint: the URL of the trigger. Bearer token: the token of the trigger. Turn on the custom payload and send the ticket id, for example `{"ticket_id": "#{ticket.id}", "title": "#{ticket.title}"}`.
3. Open Admin, Manage, Trigger, and add a trigger. Conditions: action is created, and tags do not contain a guard tag such as `ai-done`. Action: the webhook from step 2.
4. In the bot's instructions, read the ticket with `ticket ID --internal`, do the work, and add the guard tag last with `tag-add ID ai-done`. The same webhook can fire twice. The guard tag keeps the bot from working on a ticket twice.
