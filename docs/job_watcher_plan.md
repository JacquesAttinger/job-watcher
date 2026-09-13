<!-- Last edited: 2026-09-13 13:28 CDT -->

# job-watcher — internship posting alerts on your phone

## TLDR

Build a small robot that looks at three internship lists once an hour and sends a push notification to your phone when a new SWE or AI/ML internship appears.
The robot runs in Anthropic's cloud as a Claude routine, so your Mac can be off.
It uses only your Max subscription; when the subscription window is empty, it pauses and never bills by the token.
A Python script does the heavy lifting (download, compare, filter); Claude only makes the final "is this really a software internship?" call and writes the alert text.
For zero2sudo's stories you do not need a robot: Instagram's own "story notifications" bell already pushes to your phone the moment he posts.

## Context

Jacques is in an SWE internship search for Summer 2027 (B.S. Math + CS, UChicago, expected Jun 2028).
Idea #6 in `SWE_Networking/outreach_automation_ideas.md` names this exact project: a job-posting watcher with same-day alerting, because applying in the first 24–48 hours matters.
The original ask was "a Claude session always open, checking every 10 minutes."
The interview replaced that with a cloud routine because Mac-off operation mattered more than the 10-minute cadence, and because a Claude session per poll would burn the Max window.

### Hard constraint

No API usage-based billing, ever.
Only the Max subscription.
When the window is used up, the watcher must stop, not fall back to metered billing.
Verified against the routines docs: "Routines draw down subscription usage the same way interactive sessions do" and "Without usage credits, additional runs are rejected until the window resets."
Jacques must leave **usage credits OFF** at claude.ai/settings/usage.

## Decisions (from the grilling session, 2026-09-13)

| # | Decision | Choice |
|---|---|---|
| 1 | Runtime | Cloud routine, hourly (cloud minimum is 1 hour) |
| 2 | Instagram | No automation. Turn on the story-notifications bell on zero2sudo's profile |
| 3 | Alert channel | ntfy.sh push, long random topic name |
| 4 | Filter | Summer 2027, Fall 2026, Winter 2027 (co-ops included), or term unstated. Software / AI-ML / security-adjacent. Bachelor's-eligible. US or remote. Drop quant, hardware, product, analyst |
| 5 | Alert shape | One push per posting, cap 8 per run, then one "and N more" push |
| 6 | State repo | New private repo `JacquesAttinger/job-watcher`; state commits to `main` |
| 7 | Schedule | Hourly, 7am–1am America/Chicago (19 runs/day) |
| 8 | Failure handling | Per-source error push (max once/day/source) + healthchecks.io dead-man switch → ntfy |
| 9 | Model | Sonnet 5 |
| 10 | Bootstrap | First run seeds `seen.json` silently and sends one "armed" push |
| 11 | Scope | Alerts + cumulative `alerts.csv`. No resume tailoring (follow-up) |
| — | Connectors | None attached to the routine (least privilege) |

## Facts that shape the design (checked 2026-09-13)

### Sources

| Source | Feed (all via `raw.githubusercontent.com`, on the default allowlist) | Key | Useful fields | Cadence |
|---|---|---|---|---|
| `SimplifyJobs/Summer2027-Internships` (branch `dev`) | `.github/scripts/listings.json`, 12.5 MB, 16,588 entries, 3,736 active+visible | `id` | `title`, `company_name`, `url`, `terms[]`, `category`, `degrees[]`, `locations[]`, `sponsorship`, `active`, `is_visible`, `date_posted` | 30 min |
| `zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships` | `docs/api/jobs.json`, `jobs[]` (749) | `id` | `title`, `company`, `url`, `season`, `category`, `location`, `sponsorship`, `program`, `first_seen_at` | 30 min |
| `jobright-ai/2026-Software-Engineer-Internship` (branch `master`) | `README.md` markdown table (~58 rows; old rows roll off) | jobright job id in the URL | Company, Job Title, Location, Work Model, Date Posted | hourly |

Observed field values:

- Simplify `category`: `Software`, `AI/ML/Data`, `Hardware`, `Quant`, `Product`, plus legacy `Software Engineering`, `Data Science, AI & Machine Learning`.
- Simplify `terms`: `Summer 2027`, `Fall 2026`, `Winter 2027`, `N/A`, and others.
- Simplify `degrees`: multi-valued, e.g. `["Bachelor's","Master's"]`; PhD-only rows exist.
- Simplify `locations`: `Chicago, IL`, `NYC`, `SF`, `Remote in USA`, `Toronto, ON, Canada`, `London, UK`.
- zshah `season`: `Summer 2027`, `Not stated`, `Fall 2026`. `category`: `Software`, `Data & ML/AI`, `Security`, `Quant`, `Hardware`, `Other`.
- jobright has no term or category field; only the title and a day-precision date.

The three sources overlap heavily, so cross-source dedupe is required.

### Platform

- Cloud routine: fresh Ubuntu 24.04 VM per run, repo cloned from default branch, Python 3 + pip + uv preinstalled, `gh` and `git push` authenticated through the GitHub proxy.
- Push to `main` is allowed when the branch is unprotected and every commit is Jacques's (docs: routines § Repositories and branch permissions).
- Environment variables are readable by anyone who uses the environment; on a personal account that is only Jacques.
- Only `ntfy.sh` and `hc-ping.com` need adding to the environment's allowed domains.
- Account: `claude auth status` → personal org, `subscriptionType: max`. No routines exist yet.
- Daily routine run cap is shown at claude.ai/code/routines; it must be ≥ 19. Check before creating the schedule.
- Mac timezone is CDT, so "local" in the CLI already means Central.

## Architecture

### Repo layout — `JacquesAttinger/job-watcher` (private)

```
README.md                  what it is, how to test, how to re-arm
CLAUDE.md                  repo context for the cloud session (short)
routine/PROMPT.md          the routine prompt, versioned (the routine itself holds a copy)
watcher/
  __init__.py
  models.py                Posting dataclass + dedupe key
  sources.py               fetch + normalize, one function per source
  filters.py               deterministic rules (term, degree, location, category)
  state.py                 seen.json / errors.json / pending.json / decisions.json I/O
  notify.py                ntfy JSON publish, healthchecks ping
  report.py                alerts.csv append, runs/<stamp>.md summary
  cli.py                   subcommands: scan | send | seed | test
tests/
  fixtures/                trimmed JSON + README samples
  test_sources.py, test_filters.py, test_dedupe.py, test_cli.py
state/
  seen.json                {"keys": [...]}  all keys ever observed
  errors.json              {"simplify": "<iso of last error push>", ...}
  pending.json             written by scan, consumed by send (gitignored)
  decisions.json           written by Claude, consumed by send (gitignored)
alerts.csv                 date, source, company, title, term, location, sponsorship, url
runs/YYYY-MM-DD-HHMM.md    one summary per run
docs/job_watcher_plan.md   this plan
pyproject.toml             ruff config, pytest
.pre-commit-config.yaml    ruff + ruff-format (local commits only)
.env.example               NTFY_TOPIC=, HC_PING_URL=
```

Every file under 500 lines, every function under 75 lines, a "last edited" timestamp comment at the top of each source file.
Standard library only (`urllib`, `json`, `csv`, `re`) so the cloud run needs no `pip install`.

### Run flow (one routine run)

1. `python -m watcher.cli scan`
   - Fetch the three feeds. A source that fails is recorded and skipped; the others continue.
   - Normalize each row to `Posting(source, source_id, company, title, url, terms, category, degrees, locations, sponsorship)`.
   - Dedupe key: `normalize(company) + "|" + normalize(title)`, where normalize lowercases, strips punctuation, and collapses whitespace. Fallback to the URL when the company is empty.
   - `new = postings whose key is not in seen.json`.
   - Apply the deterministic **hard exclusions** (below) to `new`. Survivors become `candidates`.
   - Write `state/pending.json`: `{"new_keys": [...all new keys...], "candidates": [...], "source_errors": {...}}`.
   - Print a compact table of candidates for Claude.
2. **Claude review** (the only Claude judgment in the loop)
   - Read `pending.json`. For each candidate decide `alert: true|false` using the filter intent (software / AI-ML / security-adjacent internship or co-op, Bachelor's-eligible, US or remote).
   - Write `state/decisions.json`: `{"<key>": {"alert": true, "title": "Stripe — Software Engineer Intern", "body": "Summer 2027 · SF · Simplify"}}`.
   - Title ≤ 60 chars, body ≤ 100 chars, no markdown.
3. `python -m watcher.cli send`
   - Push one ntfy message per `alert: true`, in candidate order, up to 8. If more remain, push one "and N more — see runs/<stamp>.md" whose click URL is the summary file on github.com.
   - Append every alerted posting to `alerts.csv`.
   - Write `runs/<stamp>.md` (all candidates, decisions, source errors).
   - Push a per-source error alert if a source failed and `errors.json` shows no push for it in the last 24 h.
   - Add **all** `new_keys` (alerted or not) to `seen.json`, so nothing is re-judged next hour.
   - Ping `$HC_PING_URL` on success, `$HC_PING_URL/fail` on any exception.
   - `git add state alerts.csv runs && git commit -m "watch: <stamp>, <n> alerts" && git push origin main` (retry once).

If Claude fails between steps 1 and 3, `seen.json` is untouched, so the next run finds the same items again. Worst case is a duplicate alert, never a lost one.

### Hard exclusions (deterministic, in `filters.py`)

A posting is dropped before Claude sees it when any of these hold:

- Simplify: `active` is false or `is_visible` is false.
- Term is stated and none of it is in `{Summer 2027, Fall 2026, Winter 2027}`. Unstated (`N/A`, `Not stated`, empty, jobright) passes through.
- `degrees` is non-empty and contains neither `Bachelor's` nor `Associate's` (drops PhD-only and Master's-only).
- Category is stated and in `{Hardware, Hardware Engineering, Quant, Product, Product Management, Other}`. `Security` passes through for Claude to judge.
- Every location names a non-US country (suffix match on a small list: Canada, UK, India, Germany, France, Ireland, Singapore, Australia, Japan, China, Netherlands, Israel, Switzerland, Spain, Poland, Brazil, Mexico). Empty, ambiguous, `NYC`, `SF`, `Remote…`, and `..., XX` with a US state code pass through.
- Title matches an obvious non-software pattern: `\b(PhD|Ph\.D\.|MBA|analyst|sales|marketing|recruit|mechanical|electrical|civil)\b` (case-insensitive). Claude still sees anything not matched.

Sponsorship is never a filter; it is shown in the alert body.

### Alert format (ntfy JSON publish, avoids header-encoding issues)

```json
POST https://ntfy.sh
{"topic": "$NTFY_TOPIC", "title": "Stripe — Software Engineer Intern",
 "message": "Summer 2027 · San Francisco, CA · Simplify · sponsorship: Other",
 "click": "https://...", "tags": ["briefcase"], "priority": 3}
```

Special messages: `job-watcher armed, tracking N listings` (bootstrap), `job-watcher test OK` (test mode), `job-watcher: <source> failed: <reason>` (error, priority 4), `job-watcher is silent` (from healthchecks.io).

### Routine configuration

- Repo: `JacquesAttinger/job-watcher`, default branch `main`.
- Environment: new cloud environment `job-watcher`, network **Custom** with `ntfy.sh` and `hc-ping.com`, **Also include default list** checked. Environment variables `NTFY_TOPIC`, `HC_PING_URL`.
- Model: Sonnet 5. Connectors: none.
- Schedule: cron `23 0-6,12-23 * * *` **UTC** = 7:23am–1:23am Central during CDT (6:23am–12:23am during CST). Routine id `trig_01LMatVbuiXQhSxWRr54FC9w`, environment `env_01YGdptcimZebJ5wbBCqfEq6`.
- Prompt (`routine/PROMPT.md`, self-contained):
  1. If the `routine-fire-payload` block contains the word `test`, run `python -m watcher.cli test` and stop.
  2. Run `python -m watcher.cli scan`.
  3. Review `state/pending.json` and write `state/decisions.json` with the rules above.
  4. Run `python -m watcher.cli send`.
  5. Never edit `seen.json` by hand, never push to a branch other than `main`, never install packages.

### healthchecks.io

One check `job-watcher`, schedule type **cron** `23 0-6,12-23 * * *`, timezone **UTC**, grace 45 min.
It is the same UTC cron the routine uses, so DST can never desync the two.
Integration: ntfy → same topic.
The overnight gap is part of the cron schedule, so no false alarms overnight.
Ping URL: `https://hc-ping.com/072027a2-86b7-401c-9a61-7d3dff93f246`.

## Implementation steps

1. Create the private repo `job-watcher` (`gh repo create --private`) and clone it.
2. Copy this plan to `docs/job_watcher_plan.md` as the first commit.
3. Write `watcher/` modules and tests with trimmed fixtures from today's real feeds. Run `pytest` and `ruff`.
4. Add `pyproject.toml`, `.pre-commit-config.yaml` (ruff, ruff-format), `.gitignore` (`state/pending.json`, `state/decisions.json`, `.env`), `.env.example`, `README.md`, `CLAUDE.md`, `routine/PROMPT.md`.
5. Local dry run against live feeds: `python -m watcher.cli scan` then `send --dry-run` (prints instead of posting). Confirm candidate counts look sane.
6. Jacques does the manual setup (below). I wait for the topic and ping URL.
7. Local `python -m watcher.cli test` with the real `.env` → confirm the phone buzzes.
8. Create the cloud environment and the routine via `/schedule`, set the cron, set model Sonnet 5, remove all connectors.
9. Trigger **Run now** with text `test` → phone buzzes from the cloud, healthchecks receives a ping.
10. Trigger **Run now** with no text → bootstrap seeds `seen.json`, pushes "armed", commits to `main`.
11. Force a real alert: delete one recent software key from `seen.json`, commit, **Run now** → exactly one posting alert arrives with a working click URL.
12. Let the schedule run for a day. Check `runs/` and `alerts.csv`, adjust exclusions if noise appears.

## Manual setup for Jacques (5–10 minutes total)

- Instagram: zero2sudo profile → bell icon (or Following → Notifications) → Stories on. Make sure Instagram push is allowed on the phone.
- ntfy: install the ntfy app, subscribe to a topic like `jacques-jobs-<20 random chars>`. Send me the topic.
- healthchecks.io: free account, create the check as described, add the ntfy integration, send me the ping URL.
- claude.ai/settings/usage: confirm **usage credits are OFF**.
- claude.ai/code/routines: read the daily run cap and confirm it is ≥ 19.

## Verification

- Unit tests on fixtures: normalization of all three sources, dedupe across sources, each hard exclusion, bootstrap path, cap-8 logic.
- Local dry run against live feeds with `--dry-run`.
- Cloud `test` run: push arrives, healthchecks ping recorded.
- Cloud bootstrap run: `seen.json` committed to `main`, "armed" push arrives.
- Forced-alert run: one real alert, click opens the application page.
- Silence test: pause the routine for 2 h during the active window → healthchecks pushes "job-watcher is silent" to ntfy. Un-pause.
- After 24 h of scheduled runs: review `alerts.csv` for false positives and tune `filters.py`.

## Out of scope (follow-ups)

- Auto-tailored resume per posting (outreach idea #7).
- Any Instagram automation.
- 10-minute cadence (would need a Mac-on runner; revisit only if hourly proves too slow).
