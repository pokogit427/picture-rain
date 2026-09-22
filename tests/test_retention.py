import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.retention as retention
from app.db import Base
from app.models import Asset, Connection, Draft, HistoryEntry, Round, RoundInput, RoundSubmission, User


class RetentionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        retention.asset_path = lambda asset_id, _content_type: root / f"{asset_id}.bin"
        retention.mosaic_path = lambda asset_id: root / f"{asset_id}.mosaic.webp"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_released_round_keeps_only_result_asset(self) -> None:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            first = User(id="1" * 32, login_identifier="first", status="ACTIVE")
            second = User(id="2" * 32, login_identifier="second", status="ACTIVE")
            connection = Connection(id="3" * 32, user_low_id=first.id, user_high_id=second.id, status="ACTIVE")
            round_item = Round(
                id="4" * 32,
                connection_id=connection.id,
                created_by_id=first.id,
                status="REVEALED",
                expires_at=now + timedelta(days=1),
                revealed_at=now,
            )
            input_asset = Asset(
                id="5" * 32, connection_id=connection.id, round_id=round_item.id, owner_id=first.id,
                kind="INPUT", content_type="image/png", size=1, width=1, height=1, storage_path="input.png",
            )
            result_asset = Asset(
                id="6" * 32, connection_id=connection.id, round_id=round_item.id, owner_id=second.id,
                kind="SUBMISSION", content_type="image/png", size=1, width=1, height=1, storage_path="result.png",
            )
            submission = RoundSubmission(id="7" * 32, round_id=round_item.id, editor_id=second.id, asset_id=result_asset.id)
            db.add_all([first, second, connection, round_item, input_asset, result_asset, submission])
            db.commit()
            input_path = retention.asset_path(input_asset.id, input_asset.content_type)
            input_path.write_bytes(b"input")
            retention.mosaic_path(input_asset.id).write_bytes(b"mosaic")

            result = retention.cleanup_expired_data(db, now)

            self.assertEqual(result["deleted_assets"], 1)
            self.assertEqual(db.get(Asset, input_asset.id).state, "DELETED")
            self.assertEqual(db.get(Asset, result_asset.id).state, "ACTIVE")
            self.assertFalse(input_path.exists())

    def test_expired_round_removes_private_submission_and_draft(self) -> None:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            first = User(id="a" * 32, login_identifier="expired-first", status="ACTIVE")
            second = User(id="b" * 32, login_identifier="expired-second", status="ACTIVE")
            connection = Connection(id="c" * 32, user_low_id=first.id, user_high_id=second.id, status="ACTIVE")
            round_item = Round(
                id="d" * 32, connection_id=connection.id, created_by_id=first.id, status="OPEN",
                expires_at=now - timedelta(minutes=1),
            )
            preview = Asset(
                id="e" * 32, connection_id=connection.id, round_id=round_item.id, owner_id=first.id,
                kind="DRAFT_PREVIEW", content_type="image/png", size=1, width=1, height=1, storage_path="preview.png",
            )
            submission_asset = Asset(
                id="f" * 32, connection_id=connection.id, round_id=round_item.id, owner_id=first.id,
                kind="SUBMISSION", content_type="image/png", size=1, width=1, height=1, storage_path="private.png",
            )
            draft = Draft(
                id="1" * 31 + "0", round_id=round_item.id, editor_id=first.id, preview_asset_id=preview.id,
                document_json="{}", expires_at=now - timedelta(minutes=1),
            )
            submission = RoundSubmission(id="2" * 32, round_id=round_item.id, editor_id=first.id, asset_id=submission_asset.id)
            db.add_all([first, second, connection, round_item, preview, submission_asset, draft, submission])
            db.commit()

            result = retention.cleanup_expired_data(db, now)

            self.assertEqual(result["expired_rounds"], 1)
            self.assertEqual(result["deleted_drafts"], 1)
            self.assertEqual(result["deleted_submissions"], 1)
            self.assertEqual(db.get(round_item.__class__, round_item.id).status, "EXPIRED")
            self.assertEqual(db.get(preview.__class__, preview.id).state, "DELETED")
            self.assertEqual(db.get(submission_asset.__class__, submission_asset.id).state, "DELETED")
            self.assertIsNone(db.scalar(select(RoundSubmission).where(RoundSubmission.id == submission.id)))

    def test_trash_purge_preserves_counterpart_then_removes_unreferenced_result(self) -> None:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            first = User(id="1" * 32, login_identifier="trash-first", status="ACTIVE")
            second = User(id="2" * 32, login_identifier="trash-second", status="ACTIVE")
            connection = Connection(id="3" * 32, user_low_id=first.id, user_high_id=second.id, status="ACTIVE")
            round_item = Round(
                id="4" * 32, connection_id=connection.id, created_by_id=first.id, status="REVEALED",
                expires_at=now + timedelta(days=1), revealed_at=now,
            )
            result_asset = Asset(
                id="5" * 32, connection_id=connection.id, round_id=round_item.id, owner_id=first.id,
                kind="SUBMISSION", content_type="image/png", size=1, width=1, height=1, storage_path="result.png",
            )
            submission = RoundSubmission(id="6" * 32, round_id=round_item.id, editor_id=first.id, asset_id=result_asset.id)
            first_entry = HistoryEntry(
                id="7" * 32, connection_id=connection.id, round_id=round_item.id, submission_id=submission.id,
                viewer_id=first.id, status="TRASH", deleted_at=now - timedelta(days=31), purge_at=now - timedelta(days=1),
            )
            second_entry = HistoryEntry(
                id="8" * 32, connection_id=connection.id, round_id=round_item.id, submission_id=submission.id,
                viewer_id=second.id, status="ACTIVE",
            )
            db.add_all([first, second, connection, round_item, result_asset, submission, first_entry, second_entry])
            db.commit()
            result_path = retention.asset_path(result_asset.id, result_asset.content_type)
            result_path.write_bytes(b"result")

            first_cleanup = retention.cleanup_expired_data(db, now)
            self.assertEqual(first_cleanup["purged_history"], 1)
            self.assertEqual(first_cleanup["deleted_unreferenced_results"], 0)
            self.assertIsNotNone(db.get(Asset, result_asset.id))

            second_entry = db.get(HistoryEntry, second_entry.id)
            second_entry.status = "TRASH"
            second_entry.deleted_at = now - timedelta(days=31)
            second_entry.purge_at = now - timedelta(days=1)
            db.commit()
            second_cleanup = retention.cleanup_expired_data(db, now)
            self.assertEqual(second_cleanup["purged_history"], 1)
            self.assertEqual(second_cleanup["deleted_unreferenced_results"], 1)
            self.assertIsNone(db.get(Asset, result_asset.id))
            self.assertIsNone(db.get(RoundSubmission, submission.id))
            self.assertFalse(result_path.exists())

            retry = retention.cleanup_expired_data(db, now)
            self.assertEqual(retry["purged_history"], 0)
            self.assertEqual(retry["deleted_unreferenced_results"], 0)

    def test_disconnected_connection_is_fully_removed_without_touching_other_data(self) -> None:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            first = User(id="1" * 32, login_identifier="disconnect-first", status="ACTIVE")
            second = User(id="2" * 32, login_identifier="disconnect-second", status="ACTIVE")
            third = User(id="3" * 32, login_identifier="other-third", status="ACTIVE")
            fourth = User(id="4" * 32, login_identifier="other-fourth", status="ACTIVE")
            disconnected = Connection(id="5" * 32, user_low_id=first.id, user_high_id=second.id, status="DISCONNECTED")
            preserved = Connection(id="6" * 32, user_low_id=third.id, user_high_id=fourth.id, status="ACTIVE")
            round_item = Round(
                id="7" * 32, connection_id=disconnected.id, created_by_id=first.id, status="REVEALED",
                expires_at=now + timedelta(days=1), revealed_at=now,
            )
            asset = Asset(
                id="8" * 32, connection_id=disconnected.id, round_id=round_item.id, owner_id=first.id,
                kind="INPUT", content_type="image/png", size=1, width=1, height=1, storage_path="input.png",
            )
            round_input = RoundInput(id="9" * 32, round_id=round_item.id, sender_id=first.id, asset_id=asset.id)
            db.add_all([first, second, third, fourth, disconnected, preserved, round_item, asset, round_input])
            db.commit()
            asset_path = retention.asset_path(asset.id, asset.content_type)
            asset_path.write_bytes(b"input")

            result = retention.cleanup_expired_data(db, now)

            self.assertEqual(result["deleted_connections"], 1)
            self.assertIsNone(db.get(Connection, disconnected.id))
            self.assertIsNotNone(db.get(Connection, preserved.id))
            self.assertIsNone(db.get(Round, round_item.id))
            self.assertIsNone(db.get(Asset, asset.id))
            self.assertFalse(asset_path.exists())

            retry = retention.cleanup_expired_data(db, now)
            self.assertEqual(retry["deleted_connections"], 0)


if __name__ == "__main__":
    unittest.main()
