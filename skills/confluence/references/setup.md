Connect your Confluence Cloud site in four steps.

1. Create an API token without scopes at https://id.atlassian.com/manage-profile/security/api-tokens ("Create API token"). The token has the same rights as the Atlassian account that creates it, so the agent can read and edit everything that account can. Use an account that can only view the spaces the agent may see and edit only the spaces it should write to. An account with view rights only makes the agent read-only: its writes fail with a 403. For a shared bot, create a separate Atlassian account for it.
2. Set `CONFLUENCE_TOKEN` to your email and the token in one value, joined by a colon: `you@company.com:ATATT3x...`. Alternatively set `CONFLUENCE_EMAIL` to the email and `CONFLUENCE_TOKEN` to the token alone.
3. Set `CONFLUENCE_URL` to the address of your site, for example `https://company.atlassian.net`. Do not add `/wiki`.
4. Check the connection: `python scripts/confluence.py spaces --limit 1`. It prints a list with one space.

In a GEKI bot, `CONFLUENCE_URL` is a skill setting of the bot. `CONFLUENCE_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `CONFLUENCE_URL`. With "each person", pages are written under the name of that person.

Scoped API tokens use another address (`api.atlassian.com`) and are not supported yet.
