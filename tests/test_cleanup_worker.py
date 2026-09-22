import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.cleanup_worker as cleanup_worker
from app.db import Base


class CleanupWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_run_once_is_idempotent_on_empty_store(self) -> None:
        summary = cleanup_worker.run_once(
            now=datetime.now(timezone.utc),
            session_factory=lambda: Session(self.engine),
        )

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["deleted_connections"], 0)

    def test_run_once_skips_when_postgres_lock_is_held(self) -> None:
        class FakeDialect:
            name = "postgresql"

        class FakeBind:
            dialect = FakeDialect()

        class FakeSession:
            bind = FakeBind()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def scalar(self, statement, params):
                self.statement = str(statement)
                self.params = params
                return False

        cleanup_called = False

        def cleanup(_db, _now):
            nonlocal cleanup_called
            cleanup_called = True
            return {}

        summary = cleanup_worker.run_once(
            session_factory=FakeSession,
            cleanup_fn=cleanup,
        )

        self.assertEqual(summary, {"status": "skipped", "reason": "already_running"})
        self.assertFalse(cleanup_called)

    def test_run_once_releases_postgres_lock_after_cleanup(self) -> None:
        class FakeDialect:
            name = "postgresql"

        class FakeBind:
            dialect = FakeDialect()

        class FakeSession:
            bind = FakeBind()

            def __init__(self):
                self.executed = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def scalar(self, statement, params):
                self.executed.append((str(statement), params))
                return True

            def execute(self, statement, params):
                self.executed.append((str(statement), params))

            def rollback(self):
                self.executed.append(("rollback", {}))

        session = FakeSession()

        summary = cleanup_worker.run_once(
            now=datetime.now(timezone.utc),
            session_factory=lambda: session,
            cleanup_fn=lambda _db, _now: {"deleted_connections": 0},
        )

        self.assertEqual(summary, {"status": "completed", "deleted_connections": 0})
        self.assertEqual(len(session.executed), 3)
        self.assertIn("pg_try_advisory_lock", session.executed[0][0])
        self.assertEqual(session.executed[1][0], "rollback")
        self.assertIn("pg_advisory_unlock", session.executed[2][0])


if __name__ == "__main__":
    unittest.main()
