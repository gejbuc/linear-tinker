# scripts/notifier.py
"""
Orchestrator for sports notifications.

Modes (set via MODE environment variable):
  morning   — fires a "match/race day" alert for every event starting today (default)
  prestart  — fires a "starting soon" alert for events within pre_start_minutes
  afternoon — re-sends the morning race day alerts without scanning or scheduling
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
    """Send a heads-up for every event in the next 24 hours, then schedule prestart jobs."""
    tz_name = cfg["notifications"].get("timezone", "UTC")
    tz = pytz.timezone(tz_name)
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=24)
    pre_start_minutes = cfg["notifications"]["pre_start_minutes"]
    print(f"[morning] Scanning events from now until {window_end.astimezone(tz).strftime('%H:%M EAT, %b %d')} ({tz_name})")

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
            start = event["start_time"]
            # Include any event starting in the next 24 hours
            # This catches early-morning EAT kickoffs (e.g. 03:00 EAT = 00:00 UTC)
            # that would be missed by a simple "today" date comparison
            if now < start <= window_end:
                found_any = True
                time_str = local_time_str(start, tz_name)
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
                        start_time=start,
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
        # Find the next upcoming event across all sports and notify
        now = datetime.now(timezone.utc)
        next_event = None
        next_sport_cfg = None
        for sport_key, sport_cfg in cfg["sports"].items():
            if not sport_cfg.get("enabled", False):
                continue
            module = __import__(SPORT_MODULES[sport_key], fromlist=["get_events"])
            events = module.get_events(sport_cfg["calendar_url"])
            for event in events:
                if event["start_time"] > now:
                    if next_event is None or event["start_time"] < next_event["start_time"]:
                        next_event = event
                        next_sport_cfg = sport_cfg

        if next_event:
            tz = pytz.timezone(tz_name)
            delta = next_event["start_time"] - now
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes = remainder // 60
            local_dt = next_event["start_time"].astimezone(tz)
            time_str = local_dt.strftime("%H:%M EAT, %b %d")
            if days > 0:
                countdown = f"{days}d {hours}h"
            elif hours > 0:
                countdown = f"{hours}h {minutes}m"
            else:
                countdown = f"{minutes}m"
            send_notification(
                topic=topic,
                title="Nothing Yet",
                message=f"⏳ No event starting soon. Next up: {next_event['name']} in {countdown} ({time_str}).",
                tags="hourglass_flowing_sand",
            )
        else:
            send_notification(
                topic=topic,
                title="Nothing Yet",
                message="⏳ No upcoming events found in the calendar.",
                tags="hourglass_flowing_sand",
            )


def run_afternoon(cfg: dict, topic: str):
    """Re-send today's race day alerts without scanning or scheduling prestart jobs."""
    tz_name = cfg["notifications"].get("timezone", "UTC")
    now = datetime.now(timezone.utc)
    # Only resend events that fall on today's UTC date (not tomorrow)
    today = now.date()
    print(f"[afternoon] Re-sending alerts for {today} (no scheduling)")

    found_any = False
    for sport_key, sport_cfg in cfg["sports"].items():
        if not sport_cfg.get("enabled", False):
            continue

        module = __import__(SPORT_MODULES[sport_key], fromlist=["get_events"])
        events = module.get_events(sport_cfg["calendar_url"])

        for event in events:
            start = event["start_time"]
            if start.date() == today:
                found_any = True
                time_str = local_time_str(start, tz_name)
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

    if not found_any:
        print("  No events remaining today.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["morning", "prestart", "afternoon"],
        default=os.getenv("MODE", "morning"),
        help="morning = race day alert, prestart = T-minus alert, afternoon = reminder resend",
    )
    args = parser.parse_args()

    cfg = load_config()
    topic = get_ntfy_topic(cfg)

    print(f"Mode: {args.mode} | Topic: {topic}")

    if args.mode == "morning":
        run_morning(cfg, topic)
    elif args.mode == "prestart":
        run_prestart(cfg, topic)
    elif args.mode == "afternoon":
        run_afternoon(cfg, topic)
