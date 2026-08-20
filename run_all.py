import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def start_process(name: str, command: list[str], cwd: Path):
    print(f"Starting {name} in {cwd}")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=os.environ.copy(),
    )


def main():
    backend_proc = start_process(
        "backend",
        [sys.executable, "app/main.py"],
        BACKEND_DIR,
    )
    frontend_proc = start_process(
        "frontend",
        ["npm", "run", "dev"],
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
