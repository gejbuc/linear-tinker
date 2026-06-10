# linear-tinker

A lightweight sports notifier for F1 and World Cup 2026 that pushes alerts to your phone via [ntfy.sh](https://ntfy.sh) — no sign-ups, no API keys for the core functionality.

## How it works

Timing is handled entirely by [cron-job.org](https://cron-job.org) rather than GitHub's notoriously delayed scheduler.

```
12:00 EAT daily
  └─ cron-job.org triggers morning workflow
       ├─ sends "Race Day / Match Day" alert for each event today
       ├─ sends "No events today" if nothing scheduled
       └─ creates a one-time cron-job.org job at (start - 10 min) for each event

At each pre-start time (exact, no polling)
  └─ cron-job.org triggers prestart workflow
       └─ sends "Starting in ~10 minutes" alert
```

No idle polling. Prestart jobs are created fresh each morning and expire automatically after the event starts.

## Project Structure

```
linear-tinker/
├── .github/
│   └── workflows/
│       ├── morning.yml       # Triggered by cron-job.org at 12:00 EAT
│       ├── prestart.yml      # Triggered by cron-job.org at event start - 10 min
│       └── keepalive.yml     # Weekly Sunday run to keep workflows active
├── scripts/
│   ├── notifier.py           # Orchestrator — morning and prestart modes
│   ├── scheduler.py          # Creates/cleans up cron-job.org prestart jobs
│   ├── setup_cronjob.ps1     # One-time script to register the morning trigger
│   └── sports/
│       ├── f1.py             # F1 calendar fetcher
│       └── world_cup.py      # World Cup schedule fetcher
├── config.yaml               # All user-editable settings
├── requirements.txt
└── .gitignore
```

## Setup

### 1. Subscribe to notifications

1. Install the **ntfy** app ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)) or open [ntfy.sh](https://ntfy.sh) in a browser.
2. Subscribe to a unique topic name of your choosing.

### 2. Register the morning trigger on cron-job.org

Create a free account at [cron-job.org](https://cron-job.org), then run:

```powershell
$env:GITHUB_PAT    = "your_github_fine_grained_pat"
$env:CRONJOB_TOKEN = "your_cronjob_org_api_token"
.\scripts\setup_cronjob.ps1
```

This creates a cron-job.org job that hits GitHub's `workflow_dispatch` API at **12:00 EAT (09:00 UTC)** daily.

### 3. Add GitHub secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|---|---|
| `NTFY_TOPIC` | Your ntfy.sh topic name |
| `CRONJOB_TOKEN` | cron-job.org API bearer token |
| `MORNING_GH_PAT` | GitHub fine-grained PAT with `actions: write` on this repo |

### 4. That's it

The morning workflow fires at 12:00 EAT, sends today's alerts, and auto-schedules prestart jobs for each event. No further configuration needed.

## Configuration

Edit `config.yaml` to customise behaviour — no code changes needed.

```yaml
notifications:
  ntfy_topic: "your-topic"       # overridden by NTFY_TOPIC secret
  pre_start_minutes: 10          # how early to send the T-minus alert
  timezone: "Africa/Nairobi"     # all times shown in this zone

sports:
  f1:
    enabled: true                # set false to silence F1 alerts
  world_cup:
    enabled: true                # set false to silence World Cup alerts
```

Any [tz database timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) works.

## What you receive

| When | Notification |
|---|---|
| 12:00 EAT every day | 🏎️ / ⚽ Match/Race day alert with local kick-off time — or a quiet day nudge |
| `start_time - 10 min` | 🏁 / ⚽ "Starting in ~10 minutes" alert, fired at exact time |

On days with multiple events you get one morning alert and one prestart buzz per event.

## Demo

Test locally without waiting for an event:

```powershell
pip install -r requirements.txt
$env:NTFY_TOPIC = "your_topic"

# Morning mode
python scripts/notifier.py --mode morning

# Prestart mode
python scripts/notifier.py --mode prestart
```

To force a notification, temporarily hardcode a known race date in `run_morning()`:

```python
today = date(2026, 6, 14)  # Barcelona GP
# or
today = date(2026, 6, 11)  # World Cup opener
```

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP — calendar fetches, ntfy posts, cron-job.org API |
| `pytz` | Timezone conversion for local time display |
| `pyyaml` | Parses `config.yaml` |

## Upcoming Events

| Date | Event |
|---|---|
| Jun 11 | ⚽ World Cup opens — Mexico vs South Africa (23:00 EAT) |
| Jun 14 | 🏎️ Barcelona-Catalunya Grand Prix (16:00 EAT) |
| Jul 19 | ⚽ World Cup Final |
