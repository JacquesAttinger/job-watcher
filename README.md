<!-- Last edited: 2026-09-24 17:39 CDT -->

# job-watcher

Once an hour, a Claude cloud routine checks six internship lists and pushes a notification to your phone for every new posting that fits.
It runs in Anthropic's cloud on a Claude subscription, so no computer has to stay on, and it never bills per token.

## Why this exists

Early applicants get seen first.
Most internship postings get hundreds of applications within days, so the first 24–48 hours matter a lot.
Checking six different lists by hand, all day, is tedious and easy to forget.
This watches them for you and only interrupts you when a real match shows up.

## Subscribe to alerts (30 seconds)

1. Install the [ntfy app](https://ntfy.sh) (search "ntfy" on the App Store or Google Play, or use the web app at [ntfy.sh/app](https://ntfy.sh)).
2. Add a new subscription for the topic `jacques-jobs-3694`.
3. That's it.
   New postings show up as push notifications, roughly every hour, 7am–1am Central.

Each alert is one posting: `Company — Role`, with the term, location, and source underneath, and a tap opens the application page.

## Have a source to add?

If you know another internship list this should watch, open a [GitHub issue](../../issues/new) with a link to it.
If you can code, add a fetcher in `watcher/sources.py` and open a pull request instead — see `docs/job_watcher_plan.md` for how the existing sources are wired up.

## What it watches

| Source | Feed |
|---|---|
| [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) | `.github/scripts/listings.json` |
| [zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships](https://github.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships) | `docs/api/jobs.json` |
| [jobright-ai/2026-Software-Engineer-Internship](https://github.com/jobright-ai/2026-Software-Engineer-Internship) | `README.md` table |
| [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) | `README.md` table |
| [Chieler/Summer-2027-SWE-Internships](https://github.com/Chieler/Summer-2027-SWE-Internships) | `README.md` table (aggregates several boards; cross-source dedupe handles the overlap) |
| [ApplyGuy/2027-Internships](https://github.com/ApplyGuy/2027-Internships) | `data/internships.json` |

## Tech stack

- **Python 3.11**, standard library only — no runtime dependencies to install or trust.
- **pytest** and **ruff** for tests, linting, and formatting, enforced by a pre-commit hook.
- A **Claude cloud routine** (Anthropic) makes the per-posting judgment call and writes the alert text.
- **[ntfy.sh](https://ntfy.sh)** delivers the push notifications.
- **[healthchecks.io](https://healthchecks.io)** is a dead-man's-switch: it alerts if an hourly run ever goes silent.
- State lives in this repo as plain files (`state/seen.json`, `alerts.csv`, `runs/`), committed by each run — no database.

## How a run works

1. `python -m watcher.cli scan` downloads the feeds, drops everything already in `state/seen.json`, applies the hard exclusions in `watcher/filters.py`, and writes the survivors to `state/pending.json`.
2. Claude reads `pending.json`, decides per candidate, and writes `state/decisions.json`.
3. `python -m watcher.cli send` pushes one ntfy message per kept posting (max 8, then one "and N more"), appends `alerts.csv`, writes `runs/<stamp>.md`, marks every new key seen, commits to `main`, and pings healthchecks.io.

If step 2 never happens, step 3 refuses to run, so nothing is marked seen without a verdict.

## Run your own copy

The alerts above come from one shared instance watching for one set of filters.
To run it for yourself instead — your own topic, your own filters, your own schedule — fork the repo and follow `docs/job_watcher_plan.md`, which has the full setup (cloud routine, environment variables, healthchecks check).

For local development on this repo:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install
cp .env.example .env   # fill in NTFY_TOPIC and HC_PING_URL
.venv/bin/python -m watcher.cli test                 # one push to your phone
.venv/bin/python -m watcher.cli scan                 # see what is new
.venv/bin/python -m watcher.cli send --dry-run       # print what would be sent
.venv/bin/python -m pytest -q
```

### First run (bootstrap)

With no `state/seen.json`, `scan` marks everything as seen and `send` pushes a single "job-watcher armed" message.
Real alerts start on the next run.
`python -m watcher.cli seed` does both steps.

### Re-arming after a change

Edit `watcher/filters.py` or `routine/PROMPT.md`, open a PR, merge to `main`.
The next scheduled run clones `main` fresh, so it picks up the change on its own.
If the routine prompt changed, also paste the new `routine/PROMPT.md` into the routine at claude.ai/code/routines.

## Alerts

- Every posting alert: title `Company — Role`, body `term · location · source`, tap opens the application page.
- `job-watcher: <source> failed` at most once per source per day.
- `job-watcher is silent` comes from healthchecks.io when no run has pinged on schedule.

## Design

See `docs/job_watcher_plan.md`.
