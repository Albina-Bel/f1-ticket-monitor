# F1 Madrid 2026 — Entrada General Ticket Monitor

Watches the Fever page for F1 Spanish Grand Prix 2026 "Entrada General" tickets
and emails `a.t.bazhenova@gmail.com` as soon as either ticket becomes available
again.

Tracked tickets:

| ID | Ticket | Price |
| --- | --- | --- |
| `450963725` | Standing Area Second Release | €295 |
| `284360367` | Section 17 Pelouse Final Call | €397 |

## How it works

1. GitHub Actions runs `check.py` every 5 minutes (cron schedule).
2. The script downloads the public Fever page and parses the embedded
   `astro-tools-transfer-state` JSON blob to read live ticket availability —
   no headless browser, no API key.
3. It compares against `state.json` (committed back to the repo) to detect the
   sold-out → available transition.
4. On transition, it sends an email through Gmail SMTP.

## Setup (one-time)

### 1. Create a Gmail App Password

Regular Gmail passwords don't work for SMTP — you need an "App password".

1. Open https://myaccount.google.com/security
2. Make sure 2-Step Verification is enabled (required to create app passwords)
3. Go to https://myaccount.google.com/apppasswords
4. Create a new app password named something like "F1 ticket monitor"
5. Copy the 16-character password (no spaces)

### 2. Create the GitHub repo

```bash
cd /Users/Albina_Bazhenova/Projects/f1-ticket-monitor
git init -b main
git add .
git commit -m "initial commit"

# Create a PUBLIC repo (GitHub Actions is free unlimited on public repos)
gh repo create f1-ticket-monitor --public --source=. --push
```

> **Why public?** GitHub Actions on private repos has a 2000-minutes/month
> free quota. Running every 5 minutes uses ~4000 minutes/month and would
> stop mid-month. Public repos have unlimited free Actions minutes. There
> is no secret data in the code — credentials live in GitHub Secrets.

### 3. Configure GitHub Secrets

In your new repo, go to **Settings → Secrets and variables → Actions** and add:

| Secret name | Value |
| --- | --- |
| `SMTP_USER` | Your Gmail address (e.g. `a.t.bazhenova@gmail.com`) |
| `SMTP_PASS` | The 16-character app password from step 1 |
| `NOTIFY_EMAIL` | `a.t.bazhenova@gmail.com` |

Or via CLI:

```bash
gh secret set SMTP_USER     --body "a.t.bazhenova@gmail.com"
gh secret set SMTP_PASS     --body "xxxxxxxxxxxxxxxx"
gh secret set NOTIFY_EMAIL  --body "a.t.bazhenova@gmail.com"
```

### 4. Trigger a first run to verify

```bash
gh workflow run "Check F1 Madrid tickets"
gh run watch
```

You should see both tickets reported as `sold out` and no email sent. If you
want to test the email path end-to-end, temporarily change `state.json` to
mark both tickets as sold out (it already does that), then edit `check.py` to
force `has_available_tickets = True` for one ticket — push, watch the run,
restore the change.

## Caveats

- **GitHub cron is not exact.** The 5-min interval can be delayed by 5-15
  minutes during high load on GitHub. Real-world frequency is usually
  every 7-15 minutes.
- **Schedules pause after 60 days of repo inactivity.** Don't worry — the
  state.json commit on every check counts as activity, so this won't trigger.
- **If the email arrives, act fast.** The bot detects availability but
  someone else might still buy them seconds later.
- **Fever could change the page layout.** If it does, the script exits with
  code 2 ("tracked tickets not found") and you'll see a failed GitHub Actions
  run. Re-inspect the page and update the script.

## Running locally

```bash
python3 check.py
```

Without SMTP env vars set, email sending will be skipped (you'll just see
the printed status). With them set, you'll get a real email if the script
detects a sold-out → available transition vs the local `state.json`.
