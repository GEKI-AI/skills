Connect HubSpot with a private app in three steps.

1. In HubSpot, open Settings, Integrations, Private Apps, and create a private app. Under Scopes, add `crm.objects.contacts.read`, `crm.objects.companies.read` and `crm.objects.deals.read`. For writing, also add `crm.objects.contacts.write`, `crm.objects.companies.write` and `crm.objects.deals.write`. Notes need `crm.objects.contacts.write` (or the write scope of the record you attach them to). Leave out the write scopes if the agent should only read.
2. Copy the access token of the app and set it as `HUBSPOT_TOKEN`.
3. Check the connection: `python scripts/hubspot.py search contacts --limit 1`.

The skill talks to `https://api.hubapi.com`. HubSpot developer test accounts use the same address.

In a GEKI bot, `HUBSPOT_TOKEN` is a shared credential of the company (an environment variable secret in a vault). A private app token belongs to the app, not to a person, so there is no "each person" sign-in for this skill.
