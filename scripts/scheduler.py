# scripts/scheduler.py
"""
Manages one-time cron-job.org jobs for pre-start alerts.

Called by the morning run after it finds today's events.
For each event it:
  1. Creates a cron-job.org job that fires at (start_time - pre_start_minutes)
  2. That job triggers the prestart workflow via GitHub workflow_dispatch
  3. The job is set to run once (single day/month/hour match) and expire immediately after

Requires env vars:
  CRONJOB_TOKEN  — cron-job.org API bearer token
  GITHUB_TOKEN   — fine-grained PAT with actions:write on this repo
"""
import os
import requests
from datetime import datetime, timezone, timedelta

CRONJOB_API = "https://api.cron-job.org"
GITHUB_REPO = "gejbuc/linear-tinker"
# Workflow ID for prestart.yml
PRESTART_WORKFLOW_ID = "291200019"

# Tag prefix so we can find and clean up our jobs
JOB_TITLE_PREFIX = "linear-tinker-prestart"


def _headers(cronjob_token: str) -> dict:
    return {"Authorization": f"Bearer {cronjob_token}"}


def _github_headers(github_token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "User-Agent": "linear-tinker",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def cleanup_stale_jobs(cronjob_token: str):
    """Delete any leftover prestart jobs from previous days."""
    resp = requests.get(f"{CRONJOB_API}/jobs", headers=_headers(cronjob_token), timeout=10)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    for job in jobs:
        if job.get("title", "").startswith(JOB_TITLE_PREFIX):
            job_id = job["jobId"]
            requests.delete(f"{CRONJOB_API}/jobs/{job_id}", headers=_headers(cronjob_token), timeout=10)
            print(f"  🗑 Deleted stale prestart job {job_id}: {job['title']}")


def schedule_prestart(
    event_name: str,
    start_time: datetime,
    pre_start_minutes: int,
    cronjob_token: str,
    github_token: str,
):
    """
    Create a one-time cron-job.org job that fires `pre_start_minutes` before start_time.
    The job triggers the GitHub prestart workflow via workflow_dispatch.
    """
    fire_time = start_time - timedelta(minutes=pre_start_minutes)

    # If fire time is already in the past, skip
    if fire_time <= datetime.now(timezone.utc):
        print(f"  ⚠ Skipping prestart for '{event_name}' — fire time {fire_time:%H:%M UTC} already passed")
        return

    # cron-job.org requires wildcard mdays/months and expiresAt=0 or nextExecution stays null.
    # Jobs are deleted by cleanup_stale_jobs() on the next morning run before they can repeat.
    # Headers/body are patched in a second request — API rejects them in the initial PUT
    body = {
        "job": {
            "title": f"{JOB_TITLE_PREFIX}:{event_name[:40]}",
            "url": f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{PRESTART_WORKFLOW_ID}/dispatches",
            "enabled": True,
            "saveResponses": True,
            "requestMethod": 1,  # POST
            "requestTimeout": 30,  # match the working morning trigger job
            "schedule": {
                "timezone": "UTC",
                "hours":   [fire_time.hour],
                "minutes": [fire_time.minute],
                "mdays":   [-1],
                "months":  [-1],
                "wdays":   [-1],
                "expiresAt": 0,
            },
        }
    }

    resp = requests.put(
        f"{CRONJOB_API}/jobs",
        json=body,
        headers=_headers(cronjob_token),
        timeout=10,
    )

    if resp.status_code == 200:
        job_id = resp.json().get("jobId")
        print(f"  ⏰ Scheduled prestart job {job_id} for '{event_name}' at {fire_time:%H:%M UTC}")

        # Patch headers and body separately — cron-job.org API requires this two-step approach
        patch = {
            "job": {
                "notification": {
                    "onFailure": True,
                    "onFailureCount": 1,
                    "onSuccess": False,
                    "onDisable": False,
                },
                "extendedData": {
                    "headers": {
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {github_token}",
                        "User-Agent": "cron-job-org-trigger",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    "body": '{"ref":"master"}',
                }
            }
        }
        patch_resp = requests.patch(
            f"{CRONJOB_API}/jobs/{job_id}",
            json=patch,
            headers=_headers(cronjob_token),
            timeout=10,
        )
        if patch_resp.status_code == 200:
            print(f"  ✓ Headers patched onto job {job_id}")
        else:
            print(f"  ✗ Header patch failed for job {job_id}: HTTP {patch_resp.status_code}")
    else:
        print(f"  ✗ Failed to schedule prestart for '{event_name}': HTTP {resp.status_code} {resp.text}")
