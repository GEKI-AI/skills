# Security

## Reporting a problem

Do not open a public issue for a security problem. Use the private report on GitHub: open the Security tab of this repository and choose "Report a vulnerability". If that is not available, email security@geki.ai.

Tell us which skill is affected, what happens and how to reproduce it. We answer within a few working days. We fix confirmed problems first and tell you when the fix is published. We credit you if you want.

Examples of what to report: a script that sends a token anywhere except the request header, a skill that makes the agent leak secrets, a script that runs code from the network, a dependency with a known problem.

## How we keep skills safe

- Every pull request is reviewed by a maintainer before it merges. `main` is protected.
- Scripts use the standard library and declared packages. They do not install anything at run time and do not run code they download.
- Secrets come from environment variables and go only into request headers. Tests check this.
- CI scans for secrets on every pull request.
- A skill that adopts code from elsewhere names the source and its license, and a maintainer reads that code in full.
- Publishing to the GEKI catalog happens only when a maintainer pushes a `publish-*` tag, and only for skills with a green test result.

## What a skill can do

A skill runs with the rights of the token you give it. Use tokens with the least rights the task needs, and prefer the `-read` skills where the agent only reads. Treat text from tickets, pages and records as untrusted: it can contain instructions meant for the agent. The `SKILL.md` files tell the agent not to follow them, but a token with narrow rights is the real protection.
