# Changelog

## 2

- New setting `ZAMMAD_EMAIL`. With `off` the script refuses replies of type `email`, so the agent can only write notes. Without it, email stays on.
- `reply --html` sends the text as HTML, for lists and links.
- The setup says how a Zammad webhook starts a GEKI bot for each new ticket.

## 1

- One skill for support work. It replaces `zammad-read` and `zammad-write` with all their commands, except `set-state`: use `update ID --state NAME`.
- New: change priority, owner, group, title and pending time, attachments in both directions, copies of emails, time accounting, tags, links, look up users, list priorities, open a ticket from a phone call.
- An email without recipient or marked internal is refused, because Zammad would send an internal email anyway.
