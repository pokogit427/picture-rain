"""Run the retention cleanup as a repeatable, single-active worker."""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.retention import cleanup_expired_data

DEFAULT_INTERVAL_SECONDS = 300.0
CLEANUP_LOCK_ID = 24040604


def _try_acquire_lock(db: Session) -> bool:
    """Allow only one cleanup worker to scan and mutate the retention state."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return True
    return bool(
        db.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": CLEANUP_LOCK_ID},
        )
    )


def _release_lock(db: Session) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.rollback()
        db.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": CLEANUP_LOCK_ID},
        )


def run_once(
    now: datetime | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    cleanup_fn: Callable[..., dict[str, int]] = cleanup_expired_data,
) -> dict[str, int | str]:
    """Run one guarded cleanup pass and return a log-safe summary."""
    with session_factory() as db:
        if not _try_acquire_lock(db):
            return {"status": "skipped", "reason": "already_running"}
        try:
            return {"status": "completed", **cleanup_fn(db, now)}
        finally:
            _release_lock(db)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Picture Rain retention cleanup worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one pass and exit successfully",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.getenv("CLEANUP_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))),
        help="delay between passes when running continuously",
    )
    args = parser.parse_args()
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be greater than zero")
    return args


def main() -> None:
    args = _parse_args()
    init_db()
    while True:
        try:
            summary = run_once()
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
        except Exception as error:  # noqa: BLE001 - keep the long-running worker alive
            print(
                json.dumps(
                    {"status": "error", "error_type": type(error).__name__},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            if args.once:
                raise
        if args.once:
            return
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
