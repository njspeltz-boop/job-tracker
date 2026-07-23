# Job Posting Finder

Finds job postings that match your criteria (pulled from LinkedIn, Indeed,
Glassdoor, ZipRecruiter, etc. via the JSearch API) and emails you the new
ones. Runs automatically every Monday and Thursday via GitHub Actions.

## How it works

1. `config.json` holds your search criteria — job titles, locations,
   whether you want remote-only, and words that should exclude a posting.
2. `job_search.py` reads that config, asks the [JSearch API](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
   for matching postings, drops anything it already sent you before (using
   `seen_jobs.json` as memory), and emails whatever's left.
3. `.github/workflows/job_search.yml` runs `job_search.py` automatically
   twice a week, using secrets you'll set up below, and saves the updated
   `seen_jobs.json` back to the repo so the "already sent" memory persists.
4. Every run also appends to `search_log.jsonl` — one line per run, listing
   *every* posting JSearch returned and whether it was emailed or dropped
   (and why). See "Diagnosing missed or unwanted postings" below.

## Diagnosing missed or unwanted postings

If you spot a role elsewhere that never showed up in an email, or the
opposite — you got something irrelevant — `search_log.jsonl` has the answer.
Each line is one run's full results, e.g.:

```json
{"run_at": "2026-07-23T23:34:02+00:00", "results": [
  {"job_id": "...", "job_title": "Private Equity Associate", "employer_name": "Acme Capital", "decision": "kept", "reason": "passed all filters"},
  {"job_id": "...", "job_title": "PE Analyst Intern", "employer_name": "Beta Partners", "decision": "dropped", "reason": "title matched exclude keyword 'intern'"}
]}
```

Two cases:
- **The role appears in the log as "dropped"** — the `reason` tells you which
  filter caught it (wrong keyword, tagged remote, etc.), so you know exactly
  what to adjust in `config.json`.
- **The role never appears in the log at all** — JSearch never returned it
  for your `search_terms`/`locations`, meaning it's a coverage gap (the
  source it was posted on isn't indexed by JSearch, or the search terms need
  broadening), not a filtering problem.

Paste the posting's title/company (or the relevant log line) back to me and
I can help figure out which case it is and adjust the config.

## One-time setup

### 1. Get a JSearch API key (free)

1. Create a free account at [rapidapi.com](https://rapidapi.com/).
2. Go to the [JSearch API page](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
   and subscribe to the **free** "Basic" plan (no credit card needed).
3. On that page, find your API key (it's under "X-RapidAPI-Key" in the
   code snippets). Copy it — you'll add it as a GitHub secret in step 3.

### 2. Set up a Gmail App Password

Since Gmail needs stronger-than-a-password proof for scripts, you'll create
a dedicated "App Password":

1. On the Google account that will send the emails (njspeltz@gmail.com),
   turn on **2-Step Verification** if it isn't already on:
   https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords and create a new app
   password (name it something like "job-tracker").
3. Google shows you a 16-character password — copy it. You'll add it as a
   GitHub secret next.

### 3. Add secrets to the GitHub repo

In this repo on GitHub: **Settings → Secrets and variables → Actions → New
repository secret**. Add these three:

| Secret name           | Value                                  |
|------------------------|-----------------------------------------|
| `RAPIDAPI_KEY`         | the JSearch API key from step 1        |
| `GMAIL_ADDRESS`        | `njspeltz@gmail.com`                   |
| `GMAIL_APP_PASSWORD`   | the 16-character app password from step 2 |

### 4. Edit `config.json` with your real preferences

Open `config.json` and change the values, for example:

```json
{
  "search_terms": ["Private Equity", "Venture Capital"],
  "locations": ["Minnesota"],
  "remote_only": false,
  "exclude_remote_results": true,
  "require_keywords": ["private equity", "venture capital", "portfolio", "diligence", "fund"],
  "exclude_keywords": ["Director", "Staff", "Intern"],
  "max_results": 20
}
```

What each field does:
- `search_terms` — broad topics used to build the search query (e.g. "Private Equity in Minnesota"). Kept broad on purpose: JSearch's underlying search matches on meaning, not just exact text, so a broad term surfaces postings whose title is worded differently than you'd expect.
- `locations` — where to search.
- `remote_only` — if `true`, only fully-remote postings match, regardless of `locations`.
- `exclude_remote_results` — if `true`, drops any posting JSearch tags as remote, even if it turned up while searching your `locations` (useful when you want in-person/local roles specifically).
- `require_keywords` — a posting must mention at least one of these words *somewhere in its title or full description* to be included. This is what gives the matching "nuance" — a posting titled something unexpected (e.g. "Investment Team Associate") still gets caught if the description mentions "private equity" or "diligence".
- `exclude_keywords` — checked against the title only; any match drops the posting (e.g. filtering out "Director" or "Intern" level roles).
- `max_results` — cap on how many new postings get emailed in one run.

Commit and push that change whenever you want to adjust what it searches for.

## Testing it yourself before trusting the schedule

You can run the script on your own computer to check everything works,
before waiting for Monday/Thursday:

```bash
pip install -r requirements.txt

export RAPIDAPI_KEY="your-jsearch-key"
export GMAIL_ADDRESS="njspeltz@gmail.com"
export GMAIL_APP_PASSWORD="your-16-char-app-password"

python job_search.py
```

The first run will likely find and email several jobs (since `seen_jobs.json`
starts empty). Run it a second time right after — you should get "No new
jobs found." printed instead, since everything from the first run is now in
`seen_jobs.json`.

Once the three secrets are added on GitHub, you can also trigger a real run
from the **Actions** tab → "Find job postings" workflow → **Run workflow**,
without waiting for the schedule.

## Adjusting the schedule

The schedule lives in `.github/workflows/job_search.yml` as a cron
expression (`0 13 * * 1,4`), which GitHub always interprets in UTC. Edit the
hour if 9am US Eastern isn't the time you want.
