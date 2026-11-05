---
name: zammad-create-ticket
description: Create a ticket in Zammad. Use when the user wants to report a problem, open a support ticket or hand a request to the support team. It only creates tickets. It cannot read, answer or change existing tickets and it sends no email. To work on tickets, use zammad-support.
license: Apache-2.0
compatibility: Python 3.11+, access to your Zammad instance over HTTPS
metadata:
  version: "1"
  geki-tags: zammad, tickets, support
  geki-category: tickets
  geki-access: write
  geki-auth: company, person-token
  geki-credentials: ZAMMAD_TOKEN
  geki-settings: ZAMMAD_URL
  geki-hosts: $ZAMMAD_URL
---

# Zammad, create a ticket

Creates tickets in Zammad through one script. Output is JSON.

Needs the variables `ZAMMAD_URL` (for example `https://support.example.com`) and `ZAMMAD_TOKEN`. If one is missing, tell the user which one and point to `references/setup.md`. Never print the token.

```
python scripts/zammad.py create --title "Printer offline" --group Users --body "The printer in room 2 is offline."
python scripts/zammad.py create --title "Printer offline" --group Users --customer anna@example.com --body-file text.md --priority "3 high"
```

- `--title`, `--group` and the text are required. `--group` is the name of a Zammad group. The script cannot list the groups.
- `--customer` (email or login) opens the ticket for that person. Without it, the ticket belongs to the owner of the token. A token with only the permission `ticket.customer` always creates tickets for its owner.
- `--priority` only when the user asks for it.
- Messages are plain text. Use `--body-file -` to read from standard input.

## How to work

1. Write a clear title and put everything the user told you about the problem into the text.
2. If you do not know the group, ask. Do not guess. A 422 error carries the reason in `detail`, for example an unknown group or customer.
3. After creating, tell the user the ticket `number` from the result.
4. A 401 or 403 error means the token is wrong or the person may not create tickets there. Say so. Do not try other credentials.
