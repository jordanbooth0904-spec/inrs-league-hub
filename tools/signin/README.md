# Discord sign-in setup

Sign-in is optional. People who don't sign in can still use the whole site, including the Sportsbook, which
saves their bets in their browser like it always has. Signing in adds the Sportsbook leaderboard, keeps
your bets on every device, and makes Driver of the Race votes one per Discord account.

Sign-in stays hidden until `AUTH_URL` and `FB_KEY` are filled in near the top of the sign-in section of
`index.html`. Both are public values, not secrets.

## 1. Firebase (about 3 minutes)

1. Firebase console > Build > Authentication > Get started. You don't need to switch on any providers.
2. Project settings (gear icon) > General: copy the **Web API key**. This is `FB_KEY`.
3. Project settings > Service accounts > Generate new private key. This downloads a JSON file. Keep it
   private, and never put it on GitHub or in Discord.

## 2. Cloudflare Worker (about 5 minutes, free plan is fine)

1. dash.cloudflare.com > Workers & Pages > Create > Create Worker. Name it `inrs-signin` and click Deploy.
2. Click Edit code, replace everything with the contents of `worker.js`, then click Deploy.
3. Copy the Worker's address, for example `https://inrs-signin.yourname.workers.dev`. This is `AUTH_URL`.

## 3. Discord app (about 3 minutes)

1. discord.com/developers/applications > New Application, named `INRS League Hub`.
2. OAuth2: copy the **Client ID**. Click Reset Secret and copy the **Client Secret**.
3. OAuth2 > Redirects > Add: `AUTH_URL` + `/callback`, for example
   `https://inrs-signin.yourname.workers.dev/callback`. Save.

## 4. Worker settings

Worker > Settings > Variables and Secrets. Add these five. Use the Secret type for the two marked secret.

| Name | Value |
|---|---|
| `DISCORD_CLIENT_ID` | Client ID from step 3 |
| `DISCORD_CLIENT_SECRET` (secret) | Client Secret from step 3 |
| `FIREBASE_CLIENT_EMAIL` | `client_email` from the JSON file |
| `FIREBASE_PRIVATE_KEY` (secret) | `private_key` from the JSON file, including the BEGIN and END lines |
| `SITE_URL` | `https://inrs.page/` |

## 5. Database rules

Realtime Database > Rules: replace the rules with `database.rules.json` and click Publish. Every rule you
have today is kept the same. The new ones add:

- public read on `lapsIndex` and `laps` (lap times and track records from the live helper)
- `sb`: each signed-in player can only write their own Sportsbook bets. Each bet gets a server timestamp and
  can't be edited or deleted after it's placed. Names must match the Discord account.
- `dotr`: a vote under a Discord account can only be cast by that account. Anonymous votes work like before.

## 6. Switch it on

Put `AUTH_URL` and `FB_KEY` into `index.html`, or send them to whoever maintains the site, and push.

## How the leaderboard stays fair

Every visitor's browser replays each player's bets the same way: start at 1,000, a bet only counts if it was
placed (by server time) before betting closed and the player had the balance for it, and a reload only counts
if the balance was under 10 at the time. Live bets count up to the moment the live helper saw 10 laps to go.
The score is the balance minus 1,000 for each reload.

## Applications to Discord (optional)

Each league application gets its own post (thread) in a Discord **forum** channel. Edited answers and every
admin review (status, message to the applicant, admin note) are added to that thread.

1. In Discord, create a forum channel (e.g. `#applications`) that only staff can see, because admin notes are
   posted there. In the forum's settings, leave "Require tags" off.
2. Forum channel > Edit Channel > Integrations > Webhooks > New Webhook. Name it `INRS Applications` and
   click Copy Webhook URL. Treat this link like a password.
3. Cloudflare > Workers & Pages > `inrs-signin` > Edit code: replace everything with `worker.js`, then Deploy.
4. Settings > Variables and Secrets > Add: name `APPS_WEBHOOK`, type **Secret**, value = the webhook URL. Deploy.

The site calls `/app-notify` after someone applies and after an admin saves a review. The worker reads the
application from the database with the service account (so callers can't post made-up content), and records
the thread in `/appDiscord/<form>/<uid>` (not readable by anyone through the site). It only posts when
something changed. In Admin > Applications, "Post all to Discord" posts applications sent before this was set up.
