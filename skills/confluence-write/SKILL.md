---
name: confluence-write
description: Create and update pages in Confluence Cloud and add comments. Write the page text in Markdown, the script converts it. Use when the user asks to put a document, meeting notes or a summary into Confluence, to change a wiki page, or to comment on one. Changes real content, so confirm the target space or page before writing. To search and read, use confluence-read.
license: Apache-2.0
compatibility: Python 3.11+, access to your Confluence Cloud site over HTTPS
metadata:
  version: "2"
  geki-tags: confluence, wiki, atlassian
  geki-category: knowledge
  geki-access: write
  geki-auth: company, person-token
  geki-credentials: CONFLUENCE_TOKEN
  geki-settings: CONFLUENCE_URL
  geki-hosts: $CONFLUENCE_URL
---

# Confluence, write

Creates and changes Confluence Cloud pages through one script. Output is JSON.

Needs the variables `CONFLUENCE_URL` (for example `https://acme.atlassian.net`) and `CONFLUENCE_TOKEN`. If one is missing, tell the user which one and point to `references/setup.md`. Never print the token.

```
python scripts/confluence.py create --space DOCS --title "Meeting notes 2026-11-02" --body-file notes.md
python scripts/confluence.py create --space DOCS --parent 10000 --title "Runbook" --body "# Runbook"
python scripts/confluence.py show 10001
python scripts/confluence.py update 10001 --body-file new.md --message "Fix the VPN steps"
python scripts/confluence.py comment 10001 --body "Updated the table."
```

- The text is Markdown: headings, paragraphs, bold, italic, `code`, links, bullet and numbered lists (nested by two spaces), tables, quotes, fenced code blocks. Use `--format storage` for raw Confluence markup. Use `--body-file -` to read from standard input.
- `create` returns `id`, `title`, `version` and `url`. `--space` takes the space key or id. `--parent` puts the page under another page. `--draft` saves without publishing.
- `update` replaces the whole text of the page. It raises the version by one. It keeps the title unless you pass `--title`.
- `comment` adds a comment at the bottom of the page.

## How to work

1. Writing changes real content. If the user did not name the space or page, ask. Do not guess.
2. Before `update`, read the current page (`confluence-read` with `page ID`, or `show ID` here). Change the text, keep what the user did not ask to change, then send the full new text.
3. Never delete content the user did not ask to remove. Tell the user what you changed.
4. After a write, give the user the `url` from the result.
5. A 401 or 403 error means the token is wrong or the person may not edit there. Say so. Do not try other credentials. A 409 on update means someone else changed the page. Read it again and retry once.
6. The script cannot delete pages and does not upload attachments.
