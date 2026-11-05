Connect Finmatics with a user of its own in three steps.

1. In Finmatics, create a user for the agent, without a second factor, and give it a role that can upload and edit documents for the clients it should work with. Reading alone is not enough for `upload` and `update`.
2. Set the user name as `FINMATICS_USER` and the password as `FINMATICS_PASSWORD`.
3. Check the connection: `python scripts/finmatics.py clients`.

The skill talks to `https://api.finmatics.com` and sends the user and password as HTTP Basic on every request, which Finmatics supports. The Finmatics documentation describes a login that returns a token. That login takes the password in the request body, which a credential vault with a proxy cannot fill in, so the skill does not use it.

In a GEKI bot, `FINMATICS_PASSWORD` is a shared credential of the company (an environment variable secret in a vault), and `FINMATICS_USER` is a plain setting. The password must be 8 or more printable ASCII characters without spaces.
