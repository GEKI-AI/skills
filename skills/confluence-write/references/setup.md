Connect your Confluence Cloud site in four steps.

1. Create an API token without scopes at https://id.atlassian.com/manage-profile/security/api-tokens ("Create API token"). The token has the same rights as the Atlassian account that creates it, so it can edit every page that account can edit. Use an account that may edit only the spaces the agent should write to. For a shared bot, create a separate Atlassian account for it. Install `confluence-read` instead if the agent only needs to read.
2. Set `CONFLUENCE_TOKEN` to your email and the token in one value, joined by a colon: `you@company.com:ATATT3x...`. Alternatively set `CONFLUENCE_EMAIL` to the email and `CONFLUENCE_TOKEN` to the token alone.
3. Set `CONFLUENCE_URL` to the address of your site, for example `https://company.atlassian.net`. Do not add `/wiki`.
4. Check the connection with a read: `python scripts/confluence.py show PAGE_ID`, with the id of any page you can see (the number in the page address).

In a GEKI bot, `CONFLUENCE_URL` is a skill setting of the bot. `CONFLUENCE_TOKEN` is either a shared credential of the company (an environment variable secret in a vault) or, with "each person", a token that every person pastes once. The allowed host is the host of `CONFLUENCE_URL`. With "each person", pages are written under the name of that person.

Scoped API tokens use another address (`api.atlassian.com`) and are not supported yet.
