# linear-tinker

A lightweight sports notifier for F1 and World Cup 2026 that runs on GitHub Actions and pushes alerts to your phone via [ntfy.sh](https://ntfy.sh) — no sign-ups, no API keys.

## Overview

Two GitHub Actions workflows run automatically:

- **Morning check** (06:00 UTC daily) — fires a "Race Day" or "Match Day" alert for every event starting today
- **Pre-start check** (every 5 min, 04:00–23:00 UTC) — fires a "starting in ~N minutes" alert when an event is about to begin

Notification times are shown in your local timezone (configured in `config.yaml`). Alerts are delivered via ntfy.sh, which is free and requires no account.

## Project Structure

```
linear-tinker/
├── .github/
│   └── workflows/
│       ├── morning.yml       # Daily 06:00 UTC race/match day alert
│       └── prestart.yml      # Every 5 min pre-start T-minus alert
├── scripts/
│   ├── notifier.py           # Orchestrator — reads config, runs sport checks
│   └── sports/
│       ├── f1.py             # F1 calendar fetcher
│       └── world_cup.py      # World Cup schedule fetcher
├── tests/
├── config.yaml               # All user-editable settings
├── requirements.txt
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

Both workflows run automatically. You can also trigger either one manually from the **Actions** tab via **workflow_dispatch**.

## Configuration

Everything lives in `config.yaml` at the root — no code changes needed for common tweaks.

```yaml
notifications:
  ntfy_topic: "your-topic"       # overridden by NTFY_TOPIC GitHub secret
  pre_start_minutes: 10          # how early to send the T-minus alert
  timezone: "Africa/Nairobi"     # times in messages shown in this zone

sports:
  f1:
    enabled: true                # set false to silence F1 alerts
  world_cup:
    enabled: true                # set false to silence World Cup alerts
```

Any [tz database timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) works for the `timezone` field.

## Demo

To test the full notification path locally:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your ntfy topic (PowerShell)
$env:NTFY_TOPIC = "your_topic_here"

# 3. Morning mode — checks if today is a race/match day
python scripts/notifier.py --mode morning

# 4. Pre-start mode — checks if anything starts in the next 10 minutes
python scripts/notifier.py --mode prestart
```

To force a notification without waiting for a real event, temporarily set a known date in `run_morning()` inside `notifier.py`:

```python
today = date(2026, 6, 14)  # Barcelona GP
# or
today = date(2026, 6, 11)  # World Cup opener: Mexico vs South Africa
```

Run it, notification lands on your phone, then revert.

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP calls to fetch calendars and post notifications |
| `pytz` | Timezone conversion for local time display |
| `pyyaml` | Parses `config.yaml` |

## Upcoming Events

| Date | Event |
|---|---|
| Jun 11 | ⚽ World Cup opens — Mexico vs South Africa |
| Jun 14 | 🏎️ Barcelona-Catalunya Grand Prix |
| Jul 19 | ⚽ World Cup Final |
