"""Watchdog wrapper for AetherLab GUI with auto-restart.

Starts `python -m aetherlab` as a subprocess and auto-restarts on crash.
Backoff: 3s -> 6s -> 12s -> 24s -> 48s -> 60s (cap).
Resets to 3s after a healthy run (>120s uptime).
Logs to logs/watchdog.log.
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

# Resolve paths relative to this script's directory
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
LOG_FILE = LOG_DIR / "aetherlab_watchdog.log"

RESTART_DELAY_BASE = 3
RESTART_DELAY_CAP = 60
HEALTHY_UPTIME = 120  # seconds — reset backoff if alive this long

logger = logging.getLogger("aetherlab_watchdog")


def _setup_logging() -> None:
    """A read-only log location must not prevent launch or crash recovery."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(LOG_FILE), encoding="utf-8"))
    except OSError:
        # Console logging remains available when installation storage is read-only.
        pass
    if logging.getLogger().handlers:
        # basicConfig would ignore these handlers; do not leak an unused file.
        for handler in handlers:
            handler.close()
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
        handlers=handlers,
    )


def main() -> None:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    _setup_logging()
    delay = RESTART_DELAY_BASE
    restart_count = 0

    while True:
        logger.info("Starting AetherLab GUI: python -m aetherlab")
        started = time.monotonic()

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "aetherlab"],
                cwd=str(SCRIPT_DIR),
            )
            exit_code = proc.returncode
        except KeyboardInterrupt:
            logger.info("Watchdog interrupted — exiting")
            break
        except Exception as e:
            logger.error(f"Failed to start AetherLab: {e}")
            exit_code = -1

        uptime = time.monotonic() - started
        restart_count += 1
        logger.info(
            f"AetherLab exited with code {exit_code} "
            f"(uptime {uptime:.0f}s, restart #{restart_count})"
        )

        # Clean exit (user closed the window) — do NOT relaunch, otherwise the
        # user can never quit the app. Only auto-restart on a crash.
        if exit_code == 0:
            logger.info("Clean exit detected — watchdog stopping (user quit).")
            break

        # Healthy run — reset backoff
        if uptime >= HEALTHY_UPTIME:
            delay = RESTART_DELAY_BASE
            restart_count = 0
            logger.info("Healthy run detected — backoff reset")

        logger.info(f"Restarting in {delay}s (exit code {exit_code})...")
        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            logger.info("Watchdog interrupted — exiting")
            break
        delay = min(delay * 2, RESTART_DELAY_CAP)


if __name__ == "__main__":
    main()
