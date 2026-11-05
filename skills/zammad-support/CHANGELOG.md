# Changelog

## 1

- One skill for support work. It replaces `zammad-read` and `zammad-write` with all their commands, except `set-state`: use `update ID --state NAME`.
- New: change priority, owner, group, title and pending time, attachments in both directions, copies of emails, time accounting, tags, links, look up users, list priorities, open a ticket from a phone call.
- An email without recipient or marked internal is refused, because Zammad would send an internal email anyway.
