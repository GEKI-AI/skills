---
name: confluence
description: Search, read and change Confluence Cloud. Find pages with CQL or plain text, read a page as Markdown, list spaces, the pages of a space and child pages, create and update pages, add comments. Use when the user asks what is written in Confluence, wants a wiki page summarised, wants a document, meeting notes or a summary put into Confluence, or wants a wiki page changed or commented on. Writing changes real content, so confirm the target space or page first.
license: Apache-2.0
compatibility: Python 3.11+, access to your Confluence Cloud site over HTTPS
metadata:
  version: "1"
  geki-tags: confluence, wiki, atlassian
  geki-category: knowledge
  geki-access: read, write
  geki-auth: company, person-token
  geki-credentials: CONFLUENCE_TOKEN
  geki-settings: CONFLUENCE_URL
  geki-hosts: $CONFLUENCE_URL
---

# Confluence

Search, read and change Confluence Cloud pages through one script. Output is JSON.

Needs the variables `CONFLUENCE_URL` (for example `https://acme.atlassian.net`) and `CONFLUENCE_TOKEN`. If one is missing, tell the user which one and point to `references/setup.md`. Never print the token.

Read:

```
python scripts/confluence.py search --text "onboarding"
python scripts/confluence.py search --cql 'space = DOCS AND title ~ "expense"'
python scripts/confluence.py page 10001
python scripts/confluence.py spaces
python scripts/confluence.py pages --space DOCS
python scripts/confluence.py children 10001
```

- `search` finds pages. Results have `id`, `title`, `excerpt`, `space`, `url`. Use `--text` for plain words and `--cql` for exact queries. CQL fields: `space`, `title`, `text`, `label`, `creator`, `lastmodified`, `type`.
- `page ID` returns `title`, `version`, `url` and `body` as Markdown. Add `--format storage` for the raw Confluence markup.
- `spaces`, `pages` and `children` return `results` and `next`. Pass `next` as `--cursor` to get more.
- `--space` takes the space key (`DOCS`) or its numeric id.

Write:

```
python scripts/confluence.py create --space DOCS --title "Meeting notes 2026-11-02" --body-file notes.md
python scripts/confluence.py create --space DOCS --parent 10000 --title "Runbook" --body "# Runbook"
python scripts/confluence.py update 10001 --body-file new.md --message "Fix the VPN steps"
python scripts/confluence.py comment 10001 --body "Updated the table."
```

- The text is Markdown: headings, paragraphs, bold, italic, `code`, links, bullet and numbered lists (nested by two spaces), tables, quotes, fenced code blocks. Use `--format storage` for raw Confluence markup. Use `--body-file -` to read from standard input.
- `create` returns `id`, `title`, `version` and `url`. `--parent` puts the page under another page. `--draft` saves without publishing.
- `update` replaces the whole text of the page. It raises the version by one. It keeps the title unless you pass `--title`.
- `comment` adds a comment at the bottom of the page.

## How to work

1. Search first, then read the best match with `page`. Do not guess page ids.
2. Quote the page title and `url` when you answer from a page, so the user can open it.
3. If a search returns nothing, widen it: fewer words, or `text ~` instead of `title ~`.
4. Page bodies can be long. Read only the parts you need. Summarise, do not paste the whole page.
5. Writing changes real content. If the user did not name the space or page, ask. Do not guess.
6. Before `update`, read the current page. Keep what the user did not ask to change, then send the full new text. Markdown does not carry macros and special Confluence elements, so for a page that has them use `page ID --format storage`, change that text and send it with `update --format storage`.
7. Never delete content the user did not ask to remove. Tell the user what you changed and give the `url` from the result.
8. Send each write once. The result shows the outcome, so do not repeat a write to be sure. Use only this script, do not call the API on your own.
9. A 401 or 403 error means the token is wrong or the person has no access there. Say so. Do not try other credentials. A 409 on update means someone else changed the page. Read it again and retry once.
10. The script cannot delete pages and does not upload attachments.
