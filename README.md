# linear-tinker

A lightweight F1 race day notifier that runs on GitHub Actions and pushes alerts to your phone via [ntfy.sh](https://ntfy.sh) — no sign-ups, no API keys.

## Overview

Every morning at 06:00 UTC, GitHub Actions runs a small Python script that fetches the F1 race calendar, checks if today is a Grand Prix day, and fires a push notification if it is. Notifications are delivered through ntfy.sh, which is free and requires no account.

## Project Structure

```
linear-tinker/
├── .github/
│   └── workflows/
│       └── cron.yml        # GitHub Actions workflow (daily cron + manual trigger)
├── scripts/
│   └── notifier.py         # F1 calendar checker and notification sender
├── tests/                  # Verification (behavioral guarantees)
├── requirements.txt        # Python dependencies
├── README.md
└── .gitignore
```

## Setup

### 1. Subscribe to notifications

1. Install the **ntfy** app ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)) or open [ntfy.sh](https://ntfy.sh) in a browser.
2. Subscribe to a unique topic name of your choosing (e.g. `f1_stealth_alerts_8675309`).

### 2. Add the GitHub secret

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
   - **Name**: `NTFY_TOPIC`
   - **Secret**: your chosen topic name from step 1
3. Click **Add secret**.

### 3. That's it

The workflow runs automatically every day at 06:00 UTC. You can also trigger it manually from the **Actions** tab via **workflow_dispatch**.

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP calls to fetch the calendar and post notifications |
| `icalendar` | Parses the `.ics` calendar feed |
| `pytz` | Timezone-aware date comparison |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `NTFY_TOPIC` | `my_testing_f1_topic_999` | The ntfy.sh topic to push alerts to. Set via GitHub secret. |
| `ICS_URL` | f1calendar.com feed | F1 race-only ICS calendar URL. |
