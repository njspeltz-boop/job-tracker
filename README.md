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

Open `config.json` and change the placeholder values, for example:

```json
{
  "job_titles": ["Data Analyst", "Junior Data Scientist"],
  "locations": ["Remote", "Austin, TX"],
  "remote_only": false,
  "exclude_keywords": ["Senior", "Staff", "Principal"],
  "max_results": 20
}
```

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
