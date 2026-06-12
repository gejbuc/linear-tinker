#!/usr/bin/env python3
"""
Schedule one-shot cron-job.org jobs that mirror production triggers but fire soon.

Use this to end-to-end test the morning and prestart GitHub workflows without
waiting for 12:00 EAT or a real event start time.

Usage:
  $env:CRONJOB_TOKEN = "..."   # or CRON_TOKEN
  $env:GITHUB_PAT    = "..."   # or GITHUB_TOKEN — fine-grained PAT with actions:write
  python scripts/schedule_test_cronjobs.py              # morning @ +3 min, prestart @ +8 min
  python scripts/schedule_test_cronjobs.py --morning    # morning only
  python scripts/schedule_test_cronjobs.py --prestart   # prestart only
  python scripts/schedule_test_cronjobs.py --list
  python scripts/schedule_test_cronjobs.py --cleanup
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

CRONJOB_API = "https://api.cron-job.org"
GITHUB_REPO = "gejbuc/linear-tinker"
MORNING_WORKFLOW_ID = "291200018"
PRESTART_WORKFLOW_ID = "291200019"
TEST_JOB_TITLE_PREFIX = "linear-tinker-test"


def _token(name: str, *aliases: str) -> str | None:
    for key in (name, *aliases):
        value = os.getenv(key)
        if value:
            return value
    return None


def _headers(cronjob_token: str) -> dict:
    return {"Authorization": f"Bearer {cronjob_token}"}


def _create_dispatch_job(
    *,
    title: str,
    workflow_id: str,
    fire_time: datetime,
    cronjob_token: str,
    github_token: str,
) -> int | None:
    """Create a one-shot cron-job.org job that POSTs workflow_dispatch at fire_time (UTC)."""
    body = {
        "job": {
            "title": title,
            "url": f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_id}/dispatches",
            "enabled": True,
            "saveResponses": True,
            "requestMethod": 1,
            "requestTimeout": 30,
            # cron-job.org requires wildcard mdays/months and expiresAt=0 or nextExecution stays null.
            # Stale test jobs are removed via --cleanup; production prestarts are cleaned each morning.
            "schedule": {
                "timezone": "UTC",
                "hours": [fire_time.hour],
                "minutes": [fire_time.minute],
                "mdays": [-1],
                "months": [-1],
                "wdays": [-1],
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
    if resp.status_code != 200:
        print(f"  [FAIL] Failed to create '{title}': HTTP {resp.status_code} {resp.text}")
        return None

    job_id = resp.json().get("jobId")
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
            },
        }
    }
    patch_resp = requests.patch(
        f"{CRONJOB_API}/jobs/{job_id}",
        json=patch,
        headers=_headers(cronjob_token),
        timeout=10,
    )
    if patch_resp.status_code != 200:
        print(f"  [FAIL] Header patch failed for job {job_id}: HTTP {patch_resp.status_code}")
        return None

    details = requests.get(
        f"{CRONJOB_API}/jobs/{job_id}",
        headers=_headers(cronjob_token),
        timeout=10,
    ).json().get("jobDetails", {})
    next_exec = details.get("nextExecution")
    if not next_exec:
        print(
            f"  [WARN] Job {job_id} created but nextExecution is null — "
            f"cron-job.org may not run it. Check schedule via --list."
        )
    else:
        next_dt = datetime.fromtimestamp(next_exec, tz=timezone.utc)
        print(
            f"  [OK] Job {job_id} '{title}' next run {next_dt:%Y-%m-%d %H:%M:%S} UTC "
            f"(target {fire_time:%H:%M} UTC)"
        )
    return job_id


def list_test_jobs(cronjob_token: str) -> list[dict]:
    resp = requests.get(f"{CRONJOB_API}/jobs", headers=_headers(cronjob_token), timeout=10)
    resp.raise_for_status()
    return [j for j in resp.json().get("jobs", []) if j.get("title", "").startswith(TEST_JOB_TITLE_PREFIX)]


def cleanup_test_jobs(cronjob_token: str) -> int:
    deleted = 0
    for job in list_test_jobs(cronjob_token):
        job_id = job["jobId"]
        requests.delete(f"{CRONJOB_API}/jobs/{job_id}", headers=_headers(cronjob_token), timeout=10)
        print(f"  [DEL] Deleted test job {job_id}: {job['title']}")
        deleted += 1
    if deleted == 0:
        print("  No test jobs to delete.")
    return deleted


def schedule_test_jobs(
    *,
    cronjob_token: str,
    github_token: str,
    morning: bool,
    prestart: bool,
    morning_delay_minutes: int,
    prestart_delay_minutes: int,
) -> None:
    now = datetime.now(timezone.utc)

    if morning:
        fire = now + timedelta(minutes=morning_delay_minutes)
        _create_dispatch_job(
            title=f"{TEST_JOB_TITLE_PREFIX}:morning",
            workflow_id=MORNING_WORKFLOW_ID,
            fire_time=fire,
            cronjob_token=cronjob_token,
            github_token=github_token,
        )

    if prestart:
        fire = now + timedelta(minutes=prestart_delay_minutes)
        _create_dispatch_job(
            title=f"{TEST_JOB_TITLE_PREFIX}:prestart",
            workflow_id=PRESTART_WORKFLOW_ID,
            fire_time=fire,
            cronjob_token=cronjob_token,
            github_token=github_token,
        )


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Schedule near-term cron-job.org test triggers")
    parser.add_argument("--morning", action="store_true", help="Schedule only the morning workflow test")
    parser.add_argument("--prestart", action="store_true", help="Schedule only the prestart workflow test")
    parser.add_argument(
        "--delay-minutes",
        type=int,
        default=3,
        help="Minutes until the morning job fires (default: 3)",
    )
    parser.add_argument(
        "--prestart-delay-minutes",
        type=int,
        default=None,
        help="Minutes until the prestart job fires (default: morning delay + 5)",
    )
    parser.add_argument("--list", action="store_true", help="List existing test jobs")
    parser.add_argument("--cleanup", action="store_true", help="Delete all test jobs")
    args = parser.parse_args()

    cronjob_token = _token("CRONJOB_TOKEN", "CRON_TOKEN")
    if not cronjob_token:
        print("Set CRONJOB_TOKEN (or CRON_TOKEN) first.", file=sys.stderr)
        return 1

    if args.list:
        jobs = list_test_jobs(cronjob_token)
        if not jobs:
            print("No test jobs found.")
        for job in jobs:
            jid = job["jobId"]
            details = requests.get(
                f"{CRONJOB_API}/jobs/{jid}",
                headers=_headers(cronjob_token),
                timeout=10,
            ).json().get("jobDetails", {})
            history = requests.get(
                f"{CRONJOB_API}/jobs/{jid}/history",
                headers=_headers(cronjob_token),
                timeout=10,
            ).json()
            next_exec = details.get("nextExecution")
            next_str = (
                datetime.fromtimestamp(next_exec, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                if next_exec
                else "null (will NOT run)"
            )
            print(
                f"  {jid}: {job['title']} | next={next_str} | "
                f"lastExec={details.get('lastExecution', 0)} | "
                f"history={len(history.get('history', []))} runs"
            )
        return 0

    if args.cleanup:
        cleanup_test_jobs(cronjob_token)
        return 0

    if args.morning or args.prestart:
        schedule_morning = args.morning
        schedule_prestart = args.prestart
    else:
        schedule_morning = True
        schedule_prestart = True

    github_token = _token("GITHUB_PAT", "GITHUB_TOKEN", "MORNING_GH_PAT")
    if not github_token:
        print("Set GITHUB_PAT (or GITHUB_TOKEN) first.", file=sys.stderr)
        return 1

    prestart_delay = args.prestart_delay_minutes
    if prestart_delay is None:
        prestart_delay = args.delay_minutes + 5

    print("Scheduling test cron-job.org jobs (same payloads as production):")
    schedule_test_jobs(
        cronjob_token=cronjob_token,
        github_token=github_token,
        morning=schedule_morning,
        prestart=schedule_prestart,
        morning_delay_minutes=args.delay_minutes,
        prestart_delay_minutes=prestart_delay,
    )
    print("\nWatch GitHub Actions and your ntfy topic. List jobs: python scripts/schedule_test_cronjobs.py --list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
