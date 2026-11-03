---
name: zammad-write
description: Create tickets, reply to tickets and set the ticket state in Zammad. Use when the user asks to open a support ticket, answer a customer, add an internal note, or close, reopen or change the state of a ticket. Changes real tickets and can send email to customers, so confirm before you send. To search and read tickets, use zammad-read.
license: Apache-2.0
compatibility: Python 3.11+, access to your Zammad instance over HTTPS
metadata:
  version: "2"
  geki-tags: zammad, tickets, support
  geki-category: tickets
  geki-access: write
  geki-auth: company, person-token
  geki-credentials: ZAMMAD_TOKEN
  geki-settings: ZAMMAD_URL
  geki-hosts: $ZAMMAD_URL
---

# Zammad, write

Creates and changes tickets in Zammad through one script. Output is JSON.

Needs the variables `ZAMMAD_URL` (for example `https://support.example.com`) and `ZAMMAD_TOKEN`. If one is missing, tell the user which one and point to `references/setup.md`. Never print the token.

```
python scripts/zammad.py create --title "Printer offline" --group Users --customer anna@example.com --body "The printer in room 2 is offline."
python scripts/zammad.py reply 42 --body "We replaced the toner." --internal
python scripts/zammad.py reply 42 --type email --to anna@example.com --body "Your printer works again."
python scripts/zammad.py states
python scripts/zammad.py set-state 42 --state closed
```

- `create` opens a ticket for a customer (email or login) in a group. The first message is the article. Add `--state` or `--priority` only if the user asks.
- `reply` adds a message to a ticket. The default type `note` stays in Zammad. Add `--internal` for a note the customer must not see. With `--type email` and `--to`, Zammad sends an email to the customer.
- `set-state` changes the state by name. Run `states` to see the names your instance uses.
- Messages are plain text.

## How to work

1. Writing changes real tickets. If the user did not name the ticket, group or customer, ask. Do not guess.
2. Sending an email to a customer cannot be undone. Show the user the text and the recipient, and send only after they agree. A `note` is safe by comparison.
3. Use `--internal` for your own comments and anything about colleagues.
4. After a write, tell the user the ticket `id` and `number` from the result.
5. A 401 or 403 error means the token is wrong or the person may not do this. Say so. Do not try other credentials. A 422 error carries the reason in `detail`, for example an unknown group.
6. The script cannot delete tickets or change the owner.
