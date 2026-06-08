# scripts/sports/world_cup.py
import requests
import re
from datetime import datetime, timezone, timedelta


def _parse_utc_time(date_str: str, time_str: str) -> datetime:
    """
    Parse openfootball date + time strings into a UTC-aware datetime.
    e.g. "2026-06-11", "13:00 UTC-6"  ->  datetime(2026, 6, 11, 19, 0, tzinfo=UTC)
    """
    # Extract offset: "UTC-6" -> -6, "UTC+2" -> +2, "UTC" -> 0
    match = re.search(r"UTC([+-]\d+)?", time_str)
    offset_hours = int(match.group(1)) if match and match.group(1) else 0
    offset = timedelta(hours=offset_hours)

    # Local time string without the timezone part
    local_time_str = re.sub(r"\s*UTC[+-]?\d*", "", time_str).strip()
    local_dt = datetime.strptime(f"{date_str} {local_time_str}", "%Y-%m-%d %H:%M")

    # Convert local -> UTC
    utc_dt = local_dt.replace(tzinfo=timezone.utc) - offset
    return utc_dt


def get_events(calendar_url: str) -> list[dict]:
    """
    Fetch World Cup schedule and return a list of match events.
    Each event: {"name": str, "start_time": datetime (UTC-aware)}
    """
    response = requests.get(calendar_url, timeout=10)
    response.raise_for_status()
    data = response.json()

    events = []
    for match in data.get("matches", []):
        date_str = match.get("date")
        time_str = match.get("time", "")
        team1 = match.get("team1", "TBD")
        team2 = match.get("team2", "TBD")

        if not date_str or not time_str:
            continue

        try:
            start_time = _parse_utc_time(date_str, time_str)
        except (ValueError, AttributeError):
            continue

        events.append({
            "name": f"{team1} vs {team2}",
            "start_time": start_time,
        })

    return events
