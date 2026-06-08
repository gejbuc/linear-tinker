# scripts/notifier.py
import requests
from datetime import datetime
import pytz
import os
import sys

# 1. Configuration
# JSON calendar maintained by sportstimes — reliable and up to date
CALENDAR_URL = "https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2026.json"

# We will grab this from GitHub Secrets later so it stays private
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "my_testing_f1_topic_999")


def check_f1_schedule():
    print("Fetching F1 Calendar...")
    response = requests.get(CALENDAR_URL, timeout=10)

    if response.status_code != 200:
        print(f"Failed to fetch calendar: {response.status_code}")
        sys.exit(1)

    data = response.json()

    # Get current date in UTC
    today = datetime.now(pytz.utc).date()
    print(f"Checking for races on: {today}")

    for race in data.get("races", []):
        gp_time_str = race["sessions"].get("gp")
        if not gp_time_str:
            continue

        # Parse ISO timestamp and compare date
        gp_time = datetime.fromisoformat(gp_time_str.replace("Z", "+00:00"))

        if gp_time.date() == today:
            name = f"{race['name']} Grand Prix"
            print(f"RACE DAY! Found: {name}")
            send_notification(name, gp_time)
            return  # Exit after finding today's race

    print("No Grand Prix scheduled for today. Going back to sleep.")


def send_notification(race_name, start_time):
    # Format the time nicely (e.g., 14:00 UTC)
    time_str = start_time.strftime('%H:%M UTC')

    message = f"🏎️ It's Race Day! {race_name} starts today at {time_str}."

    # Send the push notification via NTFY
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode(encoding='utf-8'),
        headers={
            "Title": "F1 Alert",
            "Tags": "checkered_flag,race_car"  # Adds nice emojis to the notification
        }
    )
    print("Notification dispatched successfully!")


if __name__ == "__main__":
    check_f1_schedule()
