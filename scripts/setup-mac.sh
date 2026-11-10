#!/usr/bin/env bash
# ConnX one-shot setup for macOS (also works on Linux).
#
# Usage (from anywhere):
#   bash scripts/setup-mac.sh [options]
#
# Options:
#   --email you@example.com   Real contact email for NOMINATIM_USER_AGENT
#   --fresh                   Delete and rebuild .venv and frontend/node_modules
#   --skip-pull               Do not run git pull
#   --skip-tests              Do not run pytest / vitest at the end
#   --run                     Start the app (python run_all.py) when done
#
# Safe to re-run. It never overwrites an existing backend/.env or
# frontend/.env.local; it only appends settings that are missing. It refuses to
# pull if you have uncommitted changes to tracked files.

set -euo pipefail

EMAIL=""
FRESH=0
SKIP_PULL=0
SKIP_TESTS=0
RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --email) EMAIL="${2:-}"; shift 2 ;;
    --fresh) FRESH=1; shift ;;
    --skip-pull) SKIP_PULL=1; shift ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --run) RUN=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
warn() { printf 'WARNING: %s\n' "$1"; }
die()  { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
[ -d .git ] || die "$REPO_ROOT is not a git checkout."

# ---------------------------------------------------------------- 1. git pull
step "Updating the repo"
if [ "$SKIP_PULL" -eq 1 ]; then
  echo "Skipped (--skip-pull)."
else
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    git status --short --untracked-files=no
    die "You have uncommitted changes. Commit or 'git stash' them, then re-run."
  fi
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$BRANCH" != "main" ]; then
    warn "On branch '$BRANCH', not 'main'. Pulling that branch's upstream."
  fi
  git pull --ff-only || die "git pull --ff-only failed (local commits diverge from remote?). Resolve manually."
fi
echo "At commit: $(git log -1 --format='%h %s')"

# ------------------------------------------------------------ 2. tool checks
step "Checking Python"
PY=""
for cand in python3.12 python3.13 python3.14 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if (3,12) <= sys.version_info[:2] <= (3,14) else 1)'; then
      PY="$cand"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "Need Python 3.12, 3.13 or 3.14 (3.12 is the reference)."
  echo "Install with:  brew install python@3.12"
  die "No suitable Python found."
fi
echo "Using $PY ($("$PY" --version))"

step "Checking Node"
command -v node >/dev/null 2>&1 || {
  echo "Install with:  brew install node@20   (or use nvm: cd frontend && nvm install)"
  die "node not found."
}
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
NPM_MAJOR="$(npm -v | cut -d. -f1)"
[ "$NODE_MAJOR" -ge 20 ] || die "Node $NODE_MAJOR found; need 20 or newer (frontend/.nvmrc says 20)."
[ "$NPM_MAJOR" -ge 10 ] || die "npm $NPM_MAJOR found; need 10 or newer."
echo "node $(node -v), npm $(npm -v)"

# ------------------------------------------------------------- 3. backend
step "Backend virtualenv and pinned packages"
if [ "$FRESH" -eq 1 ] && [ -d .venv ]; then
  echo "Removing .venv (--fresh)"
  rm -rf .venv
fi
if [ -d .venv ] && ! .venv/bin/python -c 'import sys; sys.exit(0 if (3,12) <= sys.version_info[:2] <= (3,14) else 1)' 2>/dev/null; then
  echo "Existing .venv is broken or on an unsupported Python; rebuilding."
  rm -rf .venv
fi
[ -d .venv ] || "$PY" -m venv .venv
VENV_PY="$REPO_ROOT/.venv/bin/python"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install -r backend/requirements.txt

# ------------------------------------------------------------- 4. frontend
step "Frontend packages (npm ci)"
if [ "$FRESH" -eq 1 ]; then
  rm -rf frontend/node_modules
fi
rm -rf frontend/.next
( cd frontend && npm ci )

# ------------------------------------------------------------- 5. env files
step "Environment files"
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from backend/.env.example"
else
  # Append any KEY=value from the example that the existing file lacks.
  # Existing values are never touched.
  [ -z "$(tail -c1 backend/.env)" ] || echo >> backend/.env
  ADDED=0
  while IFS= read -r line; do
    case "$line" in
      [A-Z]*=*)
        key="${line%%=*}"
        if ! grep -q "^${key}=" backend/.env; then
          echo "$line" >> backend/.env
          echo "  added missing setting: $key"
          ADDED=$((ADDED + 1))
        fi
        ;;
    esac
  done < backend/.env.example
  echo "backend/.env kept ($ADDED setting(s) added)."
fi

if [ -n "$EMAIL" ]; then
  tmp="$(mktemp)"
  sed "s|^NOMINATIM_USER_AGENT=.*|NOMINATIM_USER_AGENT=ConnX/0.1 (contact: ${EMAIL})|" backend/.env > "$tmp"
  mv "$tmp" backend/.env
  echo "Set NOMINATIM_USER_AGENT contact to $EMAIL"
fi
if grep -q "^NOMINATIM_USER_AGENT=.*\(your-real-email\|example\.com\)" backend/.env; then
  warn "NOMINATIM_USER_AGENT still has a placeholder contact. OSM may block it with HTTP 403."
  warn "Re-run with:  bash scripts/setup-mac.sh --skip-pull --email you@yourdomain.com"
fi
if ! grep -q "^DATABASE_URL=sqlite" backend/.env; then
  warn "backend/.env DATABASE_URL is not SQLite. For zero-setup local dev use: DATABASE_URL=sqlite:///./connx_dev.db"
fi

if [ ! -f frontend/.env.local ]; then
  cp frontend/.env.local.example frontend/.env.local
  echo "Created frontend/.env.local"
else
  echo "frontend/.env.local kept."
fi

# ------------------------------------------------------------- 6. ports
step "Port check"
for port in 8000 3000; do
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "Port $port is already in use. Stop that process ('lsof -i :$port') before starting ConnX."
  else
    echo "Port $port is free."
  fi
done

# ------------------------------------------------------------- 7. tests
if [ "$SKIP_TESTS" -eq 1 ]; then
  step "Tests skipped (--skip-tests)"
else
  step "Backend tests"
  ( cd backend && "$VENV_PY" -m pytest -q )
  step "Frontend tests"
  ( cd frontend && npm test )
fi

# ------------------------------------------------------------- 8. done
step "Setup complete"
echo "Start the app with:"
echo "    source .venv/bin/activate && python run_all.py"
echo "Then open http://localhost:3000"
echo "(Routing and search use public servers; if they are slow, retry. For offline use set"
echo " ROUTING_PROVIDER=mock and GEOCODING_PROVIDER=mock in backend/.env.)"

if [ "$RUN" -eq 1 ]; then
  step "Starting ConnX"
  exec "$VENV_PY" run_all.py
fi
