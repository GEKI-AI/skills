---
name: confluence-read
description: Search and read Confluence Cloud. Find pages with CQL or plain text, read a page as Markdown, list spaces, the pages of a space and child pages. Use when the user asks what is written in Confluence, wants a wiki page summarised, or needs a document from the company wiki. Read only, it never changes anything.
license: Apache-2.0
compatibility: Python 3.11+, access to your Confluence Cloud site over HTTPS
metadata:
  version: "2"
  geki-tags: confluence, wiki, atlassian
  geki-category: knowledge
  geki-access: read
  geki-auth: company, person-token
  geki-credentials: CONFLUENCE_TOKEN
  geki-settings: CONFLUENCE_URL
  geki-hosts: $CONFLUENCE_URL
---

# Confluence, read

Read-only access to Confluence Cloud through one script. Output is JSON.

Needs the variables `CONFLUENCE_URL` (for example `https://acme.atlassian.net`) and `CONFLUENCE_TOKEN`. If one is missing, tell the user which one and point to `references/setup.md`. Never print the token.

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

## How to work

1. Search first, then read the best match with `page`. Do not guess page ids.
2. Quote the page title and `url` when you answer from a page, so the user can open it.
3. If a search returns nothing, widen it: fewer words, or `text ~` instead of `title ~`.
4. A 401 or 403 error means the token is wrong or the person has no access to that page. Say so. Do not retry with other credentials.
5. Page bodies can be long. Read only the parts you need. Summarise, do not paste the whole page.

To change pages, use the skill `confluence-write`.
