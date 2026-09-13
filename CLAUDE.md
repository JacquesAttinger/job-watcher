<!-- Last edited: 2026-09-13 12:48 CDT -->

# job-watcher

Hourly internship-posting watcher. A Claude cloud routine runs `routine/PROMPT.md` against this repo.
The plan with every design decision is `docs/job_watcher_plan.md`. Read it before changing behavior.

- `watcher/` is standard-library Python. No dependencies at runtime.
- `python -m watcher.cli scan|send|seed|test` is the whole interface. `--dry-run` prints instead of sending or writing.
- `state/seen.json`, `alerts.csv`, and `runs/` are written by the script and committed to `main` by each run. Do not hand-edit.
- Secrets (`NTFY_TOPIC`, `HC_PING_URL`) come from the environment or a local `.env`. Never commit them.
- Tests: `.venv/bin/python -m pytest -q`. Lint: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
- Keep every file under 500 lines and every function under 75 lines.
