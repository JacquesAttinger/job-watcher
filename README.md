<!-- Last edited: 2026-09-18 21:10 CDT -->

# job-watcher

Once an hour, a Claude cloud routine checks six internship lists and pushes a notification to Jacques's phone for every new posting that fits.
It runs in Anthropic's cloud on the Max subscription, so the Mac can be off, and it never bills per token.

## What it watches

| Source | Feed |
|---|---|
| SimplifyJobs/Summer2027-Internships | `.github/scripts/listings.json` |
| zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships | `docs/api/jobs.json` |
| jobright-ai/2026-Software-Engineer-Internship | `README.md` table |
| speedyapply/2027-SWE-College-Jobs | `README.md` table |
| Chieler/Summer-2027-SWE-Internships | `README.md` table (aggregates several boards; cross-source dedupe handles the overlap) |
| ApplyGuy/2027-Internships | `data/internships.json` |

## How a run works

1. `python -m watcher.cli scan` downloads the feeds, drops everything already in `state/seen.json`, applies the hard exclusions in `watcher/filters.py`, and writes the survivors to `state/pending.json`.
2. Claude reads `pending.json`, decides per candidate, and writes `state/decisions.json`.
3. `python -m watcher.cli send` pushes one ntfy message per kept posting (max 8, then one "and N more"), appends `alerts.csv`, writes `runs/<stamp>.md`, marks every new key seen, commits to `main`, and pings healthchecks.io.

If step 2 never happens, step 3 refuses to run, so nothing is marked seen without a verdict.

## Local use

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install
cp .env.example .env   # fill in NTFY_TOPIC and HC_PING_URL
.venv/bin/python -m watcher.cli test                 # one push to your phone
.venv/bin/python -m watcher.cli scan                 # see what is new
.venv/bin/python -m watcher.cli send --dry-run       # print what would be sent
.venv/bin/python -m pytest -q
```

## First run (bootstrap)

With no `state/seen.json`, `scan` marks everything as seen and `send` pushes a single "job-watcher armed" message.
Real alerts start on the next run.
`python -m watcher.cli seed` does both steps.

## Re-arming after a change

Edit `watcher/filters.py` or `routine/PROMPT.md`, open a PR, merge to `main`.
The next scheduled run clones `main` fresh, so it picks up the change on its own.
If the routine prompt changed, also paste the new `routine/PROMPT.md` into the routine at claude.ai/code/routines.

## Alerts

- Every posting alert: title `Company — Role`, body `term · location · source`, tap opens the application page.
- `job-watcher: <source> failed` at most once per source per day.
- `job-watcher is silent` comes from healthchecks.io when no run has pinged on schedule.

## Design

See `docs/job_watcher_plan.md`.
