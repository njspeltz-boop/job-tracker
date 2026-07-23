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
from email.mime.text import MIMEText
from pathlib import Path

import requests

CONFIG_PATH = Path(__file__).parent / "config.json"
SEEN_JOBS_PATH = Path(__file__).parent / "seen_jobs.json"

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
    """Query the JSearch API once per job title in config.json and
    combine the results into a single list."""
    api_key = os.environ["RAPIDAPI_KEY"]
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": JSEARCH_HOST,
    }

    locations = ", ".join(config["locations"])
    all_jobs = []

    for title in config["job_titles"]:
        query = f"{title} in {locations}" if locations else title
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


def filter_new_jobs(jobs, seen_ids, config):
    """Drop jobs we've already emailed and anything matching an
    exclude keyword in the title."""
    exclude_keywords = [kw.lower() for kw in config.get("exclude_keywords", [])]
    max_results = config.get("max_results", 20)

    new_jobs = []
    for job in jobs:
        job_id = job.get("job_id")
        title = (job.get("job_title") or "").lower()

        if not job_id or job_id in seen_ids:
            continue
        if any(kw in title for kw in exclude_keywords):
            continue

        new_jobs.append(job)

    return new_jobs[:max_results]


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
    new_jobs = filter_new_jobs(jobs, seen_ids, config)

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
