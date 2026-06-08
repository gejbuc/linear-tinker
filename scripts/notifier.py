# scripts/notifier.py
import requests
from icalendar import Calendar
from datetime import datetime
import pytz
import os
import sys

# 1. Configuration
# Using a community F1 calendar that already filters for just the races
ICS_URL = "https://f1calendar.com/download/f1-calendar_r.ics"

# We will grab this from GitHub Secrets later so it stays private
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "my_testing_f1_topic_999")


def check_f1_schedule():
    print("Fetching F1 Calendar...")
    response = requests.get(ICS_URL)

    if response.status_code != 200:
        print(f"Failed to fetch calendar: {response.status_code}")
        sys.exit(1)

    # Parse the ICS file
    cal = Calendar.from_ical(response.text)

    # Get current date in UTC
    today = datetime.now(pytz.utc).date()
    print(f"Checking for races on: {today}")

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary'))

            # Double check it's the actual Grand Prix, not sprint or practice
            if "Grand Prix" in summary or "Race" in summary:
                start_time = component.get('dtstart').dt

                # Check if the race is happening TODAY
                if start_time.date() == today:
                    print(f"RACE DAY! Found: {summary}")
                    send_notification(summary, start_time)
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
