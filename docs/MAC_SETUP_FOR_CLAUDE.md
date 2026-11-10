# Mac setup, instructions for Claude Code

Goal: get this repo running locally on macOS at the latest `main`. Everything is
automated by `scripts/setup-mac.sh`. Follow these steps in order.

## Steps

1. `cd` into the connX repo root. If you have not yet pulled the script:
   `git pull --ff-only origin main` (if there are uncommitted changes to tracked
   files, ask the user whether to commit or stash them; never discard them).
2. Ask the user for a real contact email (OpenStreetMap blocks placeholder
   User-Agents with HTTP 403). Use it as `--email` below.
3. Run:
   ```bash
   bash scripts/setup-mac.sh --email <their-email>
   ```
   The script pulls, checks Python (3.12 to 3.14) and Node (20+, npm 10+),
   rebuilds `.venv` with the pinned `backend/requirements.txt`, runs `npm ci` in
   `frontend/`, creates or tops up `backend/.env` and `frontend/.env.local`
   without overwriting existing values, checks ports 3000/8000 and runs the
   backend and frontend tests.
4. If it stops with an error, read the message, fix the cause and re-run (the
   script is idempotent):
   - Python or Node missing or too old: install with Homebrew
     (`brew install python@3.12`, `brew install node@20`), then re-run.
     Ask before installing anything.
   - `psycopg2-binary` fails to build: `brew install postgresql`, re-run.
   - Dirty working tree: ask the user, then commit or stash.
   - Broken or odd dependencies: re-run with `--fresh`.
5. When it finishes, start the app: `source .venv/bin/activate && python run_all.py`
   (or run the script with `--run`). Keep it running and tell the user to open
   http://localhost:3000.

## Rules

- Do not edit source files, do not push, do not run `npm install` (use `npm ci`
  so `package-lock.json` is not rewritten).
- Do not overwrite or delete `backend/.env`, `frontend/.env.local` or
  `backend/connx_dev.db` without asking.
- Docker is not needed; the project runs on SQLite with no extra infrastructure.
- If routing or search errors appear at runtime, the public OSM servers are
  probably slow; retry, or set `ROUTING_PROVIDER=mock` and
  `GEOCODING_PROVIDER=mock` in `backend/.env` to work offline.

## Report back

Summarise: commit now checked out, Python and Node versions used, test results,
any warnings from the script (placeholder email, non-SQLite `DATABASE_URL`, busy
ports), and whether the app is running.
