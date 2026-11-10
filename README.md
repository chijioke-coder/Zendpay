# Zendpay (simulation)

A real-world banking app made for all

## Deploy: Supabase + GitHub + Vercel

### 1. Supabase (database)
1. Create a project at supabase.com.
2. **SQL Editor > New query**, paste `supabase/migrations/20261110000000_zendpay_init.sql`, **Run**.
   It is safe to re-run. It also locks the tables away from Supabase's public API (RLS on, no policies).
3. **Project Settings > Database > Connection string > Transaction pooler** (port 6543). Copy the URI and
   put your database password in place of `[YOUR-PASSWORD]`. This is your `DATABASE_URL`.

### 2. GitHub
Push this folder. `.gitignore` already excludes `.env`, `*.db`, `.secret_key` and `owner_credentials.txt`.
**Never commit real secrets.** Only `.env.example` (placeholders) belongs in the repo.

### 3. Vercel
Import the GitHub repo (Vercel detects Flask from `app.py` + `requirements.txt`; no `vercel.json` needed).
Add these Environment Variables (see `.env.example`), then deploy:

| Name | Value |
|---|---|
| `DATABASE_URL` | Supabase transaction-pooler URI |
| `SECRET_KEY` | long random string: `python3 -c "import secrets;print(secrets.token_hex(32))"` |
| `OWNER_EMAIL` | your owner login email |
| `OWNER_PASSWORD` | your owner password (only used to create the owner the first time) |
| `ZENDPAY_TZ_OFFSET` | `1` (hours from UTC for displayed times) |

The first request creates the single owner account. Sign in at `/login` with `OWNER_EMAIL` / `OWNER_PASSWORD`
and you land on the owner dashboard. Change the password later under Owner > Settings.
Tip: set the Vercel function region (Settings > Functions) close to your Supabase region for speed.

## Run locally (no Supabase needed)
    pip install -r requirements.txt
    ./run.sh            # http://localhost:5000, SQLite file; owner login written to owner_credentials.txt
To test against Postgres locally, export `DATABASE_URL` and `SECRET_KEY` first.

## Flow
1. User signs up (3 steps) -> status **Account under verification**.
2. Owner approves/declines. Declined: "Sorry, you currently cannot have an account with us. Thanks for trying Zendpay."
3. User requests a deposit (or contacts the owner outside the app); owner approves -> both ledgers updated.
4. Users transfer to other Zendpay accounts, or to owner-created bank accounts. Anything else:
   "Service unavailable for this financial institution".

## Fees (virtual)
Zendpay-to-Zendpay 0.5% (min $0.10, max $5 equivalent); To Bank 1% (min $0.25, max $10). Edit `FEES` in `data.py`.
Cross-currency transfers convert at fixed simulation rates (`CURRENCIES` in `data.py`).

## Account states
active, restricted (view + receive only), suspended (cannot sign in), rejected, deleted (soft delete, history kept).
