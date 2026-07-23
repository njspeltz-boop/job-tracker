"""
Job Posting Finder
-------------------
Looks up job postings that match config.json, skips anything already sent
before, and emails the new matches. Meant to be run on a schedule (see
.github/workflows/job_search.yml) but works fine run by hand too:

    python job_search.py

Needs these environment variables to be set:
    RAPIDAPI_KEY        - API key for the JSearch API on RapidAPI
    GMAIL_ADDRESS        - the Gmail address to send from (and to)
    GMAIL_APP_PASSWORD   - a Gmail "App Password" for that address
"""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import requests

CONFIG_PATH = Path(__file__).parent / "config.json"
SEEN_JOBS_PATH = Path(__file__).parent / "seen_jobs.json"
SEARCH_LOG_PATH = Path(__file__).parent / "search_log.jsonl"

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search-v2"
JSEARCH_HOST = "jsearch.p.rapidapi.com"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_seen_ids():
    if not SEEN_JOBS_PATH.exists():
        return set()
    with open(SEEN_JOBS_PATH) as f:
        return set(json.load(f))


def save_seen_ids(seen_ids):
    with open(SEEN_JOBS_PATH, "w") as f:
        json.dump(sorted(seen_ids), f, indent=2)


def search_jobs(config):
    """Query the JSearch API once per broad search term in config.json
    (rather than exact job titles, so differently-worded postings still
    turn up) and combine the results into a single list."""
    api_key = os.environ["RAPIDAPI_KEY"]
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }

    locations = ", ".join(config["locations"])
    all_jobs = []

    for term in config["search_terms"]:
        query = f"{term} in {locations}" if locations else term
        params = {
            "query": query,
            "page": "1",
            "num_pages": "1",
            "date_posted": "week",
            "remote_jobs_only": "true" if config.get("remote_only") else "false",
        }
        response = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        all_jobs.extend(response.json().get("data", {}).get("jobs", []))

    return all_jobs


def evaluate_jobs(jobs, seen_ids, config):
    """Decide which jobs to send, and record a reason for every job -
    kept or dropped - so a posting that never arrived by email can be
    traced back to the exact filter that caught it (or confirmed as
    never returned by JSearch at all)."""
    require_keywords = [kw.lower() for kw in config.get("require_keywords", [])]
    exclude_keywords = [kw.lower() for kw in config.get("exclude_keywords", [])]
    exclude_remote = config.get("exclude_remote_results", False)
    max_results = config.get("max_results", 20)

    new_jobs = []
    log_entries = []
    included_ids = set()

    for job in jobs:
        job_id = job.get("job_id")
        title = job.get("job_title") or ""
        title_lower = title.lower()
        description = (job.get("job_description") or "").lower()
        entry = {
            "job_id": job_id,
            "job_title": title,
            "employer_name": job.get("employer_name"),
            "job_apply_link": job.get("job_apply_link"),
        }

        if not job_id:
            entry["decision"], entry["reason"] = "dropped", "missing job_id"
        elif job_id in seen_ids:
            entry["decision"], entry["reason"] = "dropped", "already sent in a previous run"
        elif job_id in included_ids:
            entry["decision"], entry["reason"] = "dropped", "duplicate within this run (matched multiple search terms)"
        elif exclude_remote and job.get("job_is_remote"):
            entry["decision"], entry["reason"] = "dropped", "tagged remote, exclude_remote_results is on"
        elif any(kw in title_lower for kw in exclude_keywords):
            matched = next(kw for kw in exclude_keywords if kw in title_lower)
            entry["decision"], entry["reason"] = "dropped", f"title matched exclude keyword '{matched}'"
        elif require_keywords and not any(kw in title_lower or kw in description for kw in require_keywords):
            entry["decision"], entry["reason"] = "dropped", "no require_keywords found in title or description"
        else:
            new_jobs.append(job)
            included_ids.add(job_id)
            entry["decision"], entry["reason"] = "kept", "passed all filters"

        log_entries.append(entry)

    kept = new_jobs[:max_results]
    cut_ids = {j["job_id"] for j in new_jobs[max_results:]}
    for entry in log_entries:
        if entry["job_id"] in cut_ids:
            entry["decision"], entry["reason"] = "dropped", f"exceeded max_results ({max_results})"

    return kept, log_entries


def append_search_log(log_entries):
    run_record = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": log_entries,
    }
    with open(SEARCH_LOG_PATH, "a") as f:
        f.write(json.dumps(run_record) + "\n")


def build_email(jobs):
    subject = f"{len(jobs)} new job posting{'s' if len(jobs) != 1 else ''} for you"

    rows = []
    for job in jobs:
        title = job.get("job_title", "Unknown title")
        company = job.get("employer_name", "Unknown company")
        location = job.get("job_city") or job.get("job_country") or "Remote"
        link = job.get("job_apply_link", "#")
        rows.append(
            f'<li><a href="{link}">{title}</a> — {company} ({location})</li>'
        )

    body = f"<p>Found {len(jobs)} new posting(s):</p><ul>{''.join(rows)}</ul>"
    return subject, body


def send_email(subject, html_body):
    address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    message = MIMEText(html_body, "html")
    message["Subject"] = subject
    message["From"] = address
    message["To"] = address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(address, app_password)
        server.send_message(message)


def main():
    config = load_config()
    seen_ids = load_seen_ids()

    jobs = search_jobs(config)
    new_jobs, log_entries = evaluate_jobs(jobs, seen_ids, config)
    append_search_log(log_entries)

    if not new_jobs:
        print("No new jobs found.")
        return

    subject, body = build_email(new_jobs)
    send_email(subject, body)
    print(f"Sent email with {len(new_jobs)} new job(s).")

    seen_ids.update(job["job_id"] for job in new_jobs)
    save_seen_ids(seen_ids)


if __name__ == "__main__":
    main()
