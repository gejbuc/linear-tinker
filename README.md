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

## Demo

To test the full notification path locally without waiting for a race day:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your ntfy topic (PowerShell)
$env:NTFY_TOPIC = "your_topic_here"

# 3. Run — reports no race if today isn't a GP day
python scripts/notifier.py
```

To force a notification, temporarily hardcode a known race date inside `check_f1_schedule()`:

```python
# swap the live date line for a fixed one
from datetime import date
today = date(2026, 6, 14)  # Barcelona GP
```

Run it, notification lands on your phone, then revert.

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP calls to fetch the calendar and post notifications |
| `pytz` | Timezone-aware date comparison |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `NTFY_TOPIC` | `my_testing_f1_topic_999` | The ntfy.sh topic to push alerts to. Set via GitHub secret. |
| `CALENDAR_URL` | sportstimes GitHub JSON | F1 race calendar source. |
