import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# Strings that appear when nothing is listening where we tried to connect.
_UNREACHABLE_MARKERS = (
    "connection refused",
    "could not connect to server",
    "connection timed out",
    "name or service not known",
    "getaddrinfo failed",
)


def _describe_db_url(db_url: str) -> str:
    """Human-readable, secret-free summary of a database URL."""
    if db_url.startswith("sqlite"):
        path = db_url.split(":///", 1)[-1] if ":///" in db_url else "(in-memory)"
        return f"SQLite ({path})"
    try:
        parts = urlsplit(db_url)
        host = parts.hostname or "?"
        if parts.port:
            host += f":{parts.port}"
        return f"PostgreSQL @ {host}{parts.path or ''}"
    except ValueError:
        return "PostgreSQL"


def _is_driver_missing(exc: Exception) -> bool:
    """
    True only when the Postgres driver package itself can't be imported.

    Every ordinary psycopg2 failure string starts with "(psycopg2.<Exc>)",
    so matching that substring alone would misfire on any connection error.
    """
    from sqlalchemy.exc import NoSuchModuleError

    # \b so a typo'd dialect like postgresql.psycopg2bogus doesn't match.
    plugin_not_loaded = isinstance(exc, NoSuchModuleError) and re.search(
        r"sqlalchemy\.dialects:postgresql\.psycopg2\b", str(exc)
    )
    module_not_found = isinstance(exc, ModuleNotFoundError) and "psycopg2" in str(exc)
    return bool(plugin_not_loaded or module_not_found)


def _is_unreachable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _UNREACHABLE_MARKERS)


def check_database(env: dict) -> None:
    """
    Fail fast with an actionable message instead of letting the backend
    process start, fail to connect, and leave collaborators staring at a
    port that never comes up with no clue why.

    app.config resolves backend/.env by file location (not CWD), so this
    works no matter which directory run_all.py is launched from.
    """
    sys.path.insert(0, str(BACKEND_DIR))
    os.environ.update(env)
    db_url = ""
    try:
        from app.config import get_settings  # noqa: E402
        from sqlalchemy import create_engine, text  # noqa: E402

        get_settings.cache_clear()
        db_url = get_settings().database_url

        # Real environment variables outrank .env in pydantic-settings; if
        # someone has a stray global DATABASE_URL set, say so explicitly -
        # it's invisible otherwise and overrides whatever .env promises.
        try:
            from dotenv import dotenv_values  # noqa: E402

            dotenv_url = dotenv_values(BACKEND_DIR / ".env").get("DATABASE_URL")
        except Exception:  # noqa: BLE001 - diagnostic nicety only
            dotenv_url = None
        env_override = env.get("DATABASE_URL")
        if env_override and dotenv_url and env_override != dotenv_url:
            print(f"Note: DATABASE_URL in your shell ({_describe_db_url(env_override)})")
            print(f"overrides backend/.env ({_describe_db_url(dotenv_url)}).")

        engine = create_engine(db_url, connect_args={"connect_timeout": 3} if "sqlite" not in db_url else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Database reachable: {_describe_db_url(db_url)}")
        return
    except Exception as exc:  # noqa: BLE001 - startup diagnostic, not app logic
        print("\nERROR: Could not reach the database configured in backend/.env")
        if db_url:
            print(f"  Configured: {_describe_db_url(db_url)}")
        print(f"  {exc}\n")
        print("Fix one of these:")
        print("  1. Start Postgres via Docker:   docker compose up -d db")
        print("  2. Or switch to SQLite for local dev - in backend/.env set:")
        print("       DATABASE_URL=sqlite:///./connx_dev.db")
        print("     (see backend/.env.example for the commented-out line)")

        if _is_driver_missing(exc):
            print("\n  Cause: the Postgres driver isn't installed.")
            print("  Fix:   pip install psycopg2-binary\n")
        elif _is_unreachable(exc):
            target = db_url.split("@", 1)[-1].split("/", 1)[0] if "@" in db_url else "that address"
            print(f"\n  Cause: nothing is listening at {target} - Postgres isn't running (option 1),")
            print("  or you meant to develop locally without it (use option 2's SQLite line).\n")
        else:
            print()
        sys.exit(1)


def start_process(name: str, command: list[str], cwd: Path):
    print(f"Starting {name} in {cwd}")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=os.environ.copy(),
    )


def _find_npm() -> str:
    """
    Absolute path to the npm launcher. On Windows npm is npm.cmd, which
    CreateProcess refuses to resolve from a bare "npm" - spawning it
    without the full path fails with WinError 2.
    """
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print("\nERROR: npm not found on PATH.")
        print("Install Node.js (https://nodejs.org) or start the frontend")
        print("separately:  cd frontend && npm run dev\n")
        sys.exit(1)
    return npm


def main():
    # Piped/redirected output on Windows defaults to cp1252, which can't
    # encode non-ASCII diagnostics; never let the helper crash on printing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:  # noqa: BLE001 - cosmetic safeguard only
                pass

    check_database(os.environ.copy())

    if not (FRONTEND_DIR / "node_modules").exists():
        print("Note: frontend/node_modules is missing - run 'npm install' in")
        print("frontend/ once, or Next.js will fail to start below.\n")

    # -m uvicorn (not app/main.py): running a script by path only puts
    # backend/app on sys.path, so `import app.config` inside it would fail.
    # With -m, the CWD (backend/) is what gets imported against.
    backend_proc = start_process(
        "backend",
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        BACKEND_DIR,
    )
    frontend_proc = start_process(
        "frontend",
        [_find_npm(), "run", "dev"],
        FRONTEND_DIR,
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        for proc in (backend_proc, frontend_proc):
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
        for proc in (backend_proc, frontend_proc):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    main()
