# scripts/sports/f1.py
import requests
from datetime import datetime, timezone


def get_events(calendar_url: str) -> list[dict]:
    """
    Fetch F1 calendar and return a list of race events.
    Each event: {"name": str, "start_time": datetime (UTC-aware)}
    """
    response = requests.get(calendar_url, timeout=10)
    response.raise_for_status()
    data = response.json()

    events = []
    for race in data.get("races", []):
        gp_time_str = race["sessions"].get("gp")
        if not gp_time_str:
            continue
        start_time = datetime.fromisoformat(gp_time_str.replace("Z", "+00:00"))
        events.append({
            "name": f"{race['name']} Grand Prix",
            "start_time": start_time,
        })

    return events
