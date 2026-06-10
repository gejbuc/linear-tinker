# scripts/notifier.py
"""
Orchestrator for sports notifications.

Modes (set via MODE environment variable):
  morning   — fires a "match/race day" alert for every event starting today (default)
  prestart  — fires a "starting soon" alert for events within pre_start_minutes
"""
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml
import pytz

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

SPORT_MODULES = {
    "f1": "sports.f1",
    "world_cup": "sports.world_cup",
}


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_ntfy_topic(cfg: dict) -> str:
    # Env var (GitHub secret) takes priority over config file
    return os.getenv("NTFY_TOPIC", cfg["notifications"]["ntfy_topic"])


def get_cronjob_token() -> str | None:
    return os.getenv("CRONJOB_TOKEN")


def get_github_token() -> str | None:
    return os.getenv("GITHUB_TOKEN")


def local_time_str(dt: datetime, tz_name: str) -> str:
    """Convert a UTC-aware datetime to a formatted time string in the user's timezone."""
    tz = pytz.timezone(tz_name)
    return dt.astimezone(tz).strftime("%H:%M")


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def send_notification(topic: str, title: str, message: str, tags: str = "bell"):
    response = requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Tags": tags},
        timeout=10,
    )
    if response.status_code == 200:
        print(f"  ✓ Sent: {message}")
    else:
        print(f"  ✗ ntfy returned HTTP {response.status_code}")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_morning(cfg: dict, topic: str):
    """Send a heads-up for every event starting today, then schedule prestart jobs."""
    tz_name = cfg["notifications"].get("timezone", "UTC")
    tz = pytz.timezone(tz_name)
    today = datetime.now(tz).date()
    pre_start_minutes = cfg["notifications"]["pre_start_minutes"]
    print(f"[morning] Checking for events on {today} ({tz_name})")

    cronjob_token = get_cronjob_token()
    github_token = get_github_token()
    scheduling_enabled = bool(cronjob_token and github_token)

    # Import scheduler lazily so local runs without tokens still work
    if scheduling_enabled:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from scheduler import cleanup_stale_jobs, schedule_prestart
        cleanup_stale_jobs(cronjob_token)

    found_any = False
    for sport_key, sport_cfg in cfg["sports"].items():
        if not sport_cfg.get("enabled", False):
            continue

        module = __import__(SPORT_MODULES[sport_key], fromlist=["get_events"])
        events = module.get_events(sport_cfg["calendar_url"])

        for event in events:
            # Compare against today in the user's local timezone
            if event["start_time"].astimezone(tz).date() == today:
                found_any = True
                time_str = local_time_str(event["start_time"], tz_name)
                message = sport_cfg["race_day_message"].format(
                    name=event["name"],
                    time=time_str,
                )
                send_notification(
                    topic=topic,
                    title=sport_cfg["label"],
                    message=message,
                    tags="calendar,bell",
                )

                # Schedule a precise prestart alert via cron-job.org
                if scheduling_enabled:
                    schedule_prestart(
                        event_name=event["name"],
                        start_time=event["start_time"],
                        pre_start_minutes=pre_start_minutes,
                        cronjob_token=cronjob_token,
                        github_token=github_token,
                    )

    if not found_any:
        print("  No events today. Going back to sleep.")
        send_notification(
            topic=topic,
            title="No Events Today",
            message="📅 No F1 or World Cup events today. Enjoy the quiet.",
            tags="zzz",
        )


def run_prestart(cfg: dict, topic: str):
    """Send a 'starting soon' alert for events within pre_start_minutes."""
    tz_name = cfg["notifications"].get("timezone", "UTC")
    now = datetime.now(timezone.utc)
    window = cfg["notifications"]["pre_start_minutes"]
    soon = now + timedelta(minutes=window)
    print(f"[prestart] Checking for events between {now:%H:%M} and {soon:%H:%M} UTC")

    found_any = False
    for sport_key, sport_cfg in cfg["sports"].items():
        if not sport_cfg.get("enabled", False):
            continue

        module = __import__(SPORT_MODULES[sport_key], fromlist=["get_events"])
        events = module.get_events(sport_cfg["calendar_url"])

        for event in events:
            start = event["start_time"]
            # Fire if event starts within the next `window` minutes
            if now <= start <= soon:
                found_any = True
                minutes_away = int((start - now).total_seconds() / 60)
                time_str = local_time_str(start, tz_name)
                message = sport_cfg["pre_start_message"].format(
                    name=event["name"],
                    time=time_str,
                    minutes=minutes_away,
                )
                send_notification(
                    topic=topic,
                    title=sport_cfg["label"],
                    message=message,
                    tags="stopwatch,bell",
                )

    if not found_any:
        print("  No events starting soon.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["morning", "prestart"],
        default=os.getenv("MODE", "morning"),
        help="morning = race day alert, prestart = T-minus alert",
    )
    args = parser.parse_args()

    cfg = load_config()
    topic = get_ntfy_topic(cfg)

    print(f"Mode: {args.mode} | Topic: {topic}")

    if args.mode == "morning":
        run_morning(cfg, topic)
    elif args.mode == "prestart":
        run_prestart(cfg, topic)
