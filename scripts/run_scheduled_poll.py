"""Run the scheduled Gmail polling cycle for the lean pilot runtime."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.shared.config import get_settings
from src.shared.database import SessionLocal
from src.workflow.polling import run_scheduled_poll_cycle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the scheduled Gmail polling cycle.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Poll all active mailboxes immediately and ignore the due-window check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = get_settings()
    session = SessionLocal()
    try:
        result = run_scheduled_poll_cycle(session, settings, force=args.force)
    except Exception:
        logging.getLogger(__name__).exception("Scheduled poll runner crashed before completing the cycle.")
        return 1
    finally:
        session.close()

    logging.getLogger(__name__).info(
        "Scheduled poll cycle complete: total=%s due=%s polled=%s failed=%s skipped=%s",
        result.total_mailboxes,
        result.due_mailboxes,
        result.polled_mailboxes,
        result.failed_mailboxes,
        result.skipped_mailboxes,
    )
    return 0 if result.failed_mailboxes == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
