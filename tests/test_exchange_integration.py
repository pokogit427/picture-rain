import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.retention as retention
from app.db import Base
from app.entitlement import current_policy
from app.models import Asset, Connection, Draft, HistoryEntry, Round, RoundInput, RoundSubmission, UsageCharge, User
from app.round_api import _result_response, delete_history, list_history, list_results, submit_round
from app.schemas import HistoryDeleteRequest
from app.usage import get_usage_summary, reserve_round_charge


class ExchangeIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        retention.asset_path = lambda asset_id, _content_type: root / f"{asset_id}.bin"
        retention.mosaic_path = lambda asset_id: root / f"{asset_id}.mosaic.webp"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _asset(self, connection_id: str, round_id: str, owner_id: str, asset_id: str, kind: str) -> Asset:
        return Asset(
            id=asset_id,
            connection_id=connection_id,
            round_id=round_id,
            owner_id=owner_id,
            kind=kind,
            content_type="image/png",
            size=1,
            width=1,
            height=1,
            storage_path=f"{asset_id}.png",
        )

    def _prepare_round(self, db: Session, connection: Connection, first: User, second: User, prefix: str, now: datetime) -> Round:
        round_item = Round(
            id=prefix + "0" * (32 - len(prefix)),
            connection_id=connection.id,
            created_by_id=first.id,
            status="OPEN",
            created_at=now,
            expires_at=now + timedelta(days=1),
        )
        first_input = self._asset(connection.id, round_item.id, first.id, prefix + "1" * (32 - len(prefix)), "INPUT")
        second_input = self._asset(connection.id, round_item.id, second.id, prefix + "2" * (32 - len(prefix)), "INPUT")
        first_preview = self._asset(connection.id, round_item.id, first.id, prefix + "3" * (32 - len(prefix)), "DRAFT_PREVIEW")
        second_preview = self._asset(connection.id, round_item.id, second.id, prefix + "4" * (32 - len(prefix)), "DRAFT_PREVIEW")
        db.add_all([
            round_item,
            first_input,
            second_input,
            first_preview,
            second_preview,
            RoundInput(round_id=round_item.id, sender_id=first.id, asset_id=first_input.id),
            RoundInput(round_id=round_item.id, sender_id=second.id, asset_id=second_input.id),
            Draft(round_id=round_item.id, editor_id=first.id, preview_asset_id=first_preview.id, document_json="{}", expires_at=now + timedelta(hours=1)),
            Draft(round_id=round_item.id, editor_id=second.id, preview_asset_id=second_preview.id, document_json="{}", expires_at=now + timedelta(hours=1)),
        ])
        reserve_round_charge(db, user_id=first.id, connection_id=connection.id, round_id=round_item.id)
        return round_item

    def test_two_connections_reveal_delete_and_disconnect_in_isolation(self) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with Session(self.engine) as db:
            alice = User(id="1" * 32, login_identifier="alice", status="ACTIVE")
            bob = User(id="2" * 32, login_identifier="bob", status="ACTIVE")
            carol = User(id="3" * 32, login_identifier="carol", status="ACTIVE")
            connection_ab = Connection(id="4" * 32, user_low_id=alice.id, user_high_id=bob.id, status="ACTIVE")
            connection_ac = Connection(id="5" * 32, user_low_id=alice.id, user_high_id=carol.id, status="ACTIVE")
            db.add_all([alice, bob, carol, connection_ab, connection_ac])
            db.commit()

            round_ab = self._prepare_round(db, connection_ab, alice, bob, "a", now)
            round_ac = self._prepare_round(db, connection_ac, alice, carol, "b", now)
            db.commit()
            reserve_round_charge(db, user_id=alice.id, connection_id=connection_ac.id, round_id=round_ac.id)
            db.commit()

            with patch("app.round_api._now", return_value=now):
                first_submission = submit_round(round_ab.id, user=alice, db=db)
            self.assertEqual(first_submission.status, "SUBMITTED")
            self.assertEqual(db.get(Round, round_ab.id).status, "OPEN")
            first_result = db.get(RoundSubmission, first_submission.id)
            self.assertEqual(_result_response(db.get(Round, round_ab.id), first_result, alice.id, db).visibility, "MOSAIC")

            with patch("app.round_api._now", return_value=now):
                second_submission = submit_round(round_ab.id, user=bob, db=db)
            self.assertEqual(db.get(Round, round_ab.id).status, "REVEALED")
            self.assertEqual(len(list_results(round_ab.id, user=alice, db=db)), 2)
            self.assertTrue(all(item.visibility == "ORIGINAL" for item in list_results(round_ab.id, user=bob, db=db)))

            with patch("app.round_api._now", return_value=now):
                submit_round(round_ac.id, user=alice, db=db)
                submit_round(round_ac.id, user=carol, db=db)
            self.assertEqual(len(list_results(round_ac.id, user=carol, db=db)), 2)
            with self.assertRaises(HTTPException) as outsider:
                list_results(round_ab.id, user=carol, db=db)
            self.assertEqual(outsider.exception.status_code, 404)

            alice_ab_history = list_history(connection_ab.id, user=alice, db=db)
            bob_ab_history = list_history(connection_ab.id, user=bob, db=db)
            alice_ac_history = list_history(connection_ac.id, user=alice, db=db)
            self.assertEqual(len(alice_ab_history), 2)
            self.assertEqual(len(bob_ab_history), 2)
            self.assertEqual(len(alice_ac_history), 2)

            deleted_ids = [item.entry_id for item in alice_ab_history]
            self.assertEqual(
                set(delete_history(HistoryDeleteRequest(entry_ids=deleted_ids), connection_ab.id, user=alice, db=db)),
                set(deleted_ids),
            )
            self.assertEqual(list_history(connection_ab.id, user=alice, db=db), [])
            self.assertEqual(len(list_history(connection_ab.id, user=bob, db=db)), 2)

            ab_usage = get_usage_summary(db, user_id=alice.id, connection_id=connection_ab.id)
            ac_usage = get_usage_summary(db, user_id=alice.id, connection_id=connection_ac.id)
            self.assertEqual((ab_usage.connection_used, ac_usage.connection_used), (1, 1))
            self.assertEqual(ab_usage.account_used, 2)
            self.assertEqual((current_policy().daily_rounds_per_connection, current_policy().total_rounds_per_account), (3, 30))

            connection_ab.status = "DISCONNECTED"
            connection_ab.disconnected_at = now
            db.commit()
            cleanup = retention.cleanup_expired_data(db, now.replace(tzinfo=timezone.utc))

            self.assertEqual(cleanup["deleted_connections"], 1)
            self.assertIsNone(db.get(Connection, connection_ab.id))
            self.assertIsNone(db.get(Round, round_ab.id))
            self.assertIsNone(db.get(RoundSubmission, first_submission.id))
            self.assertIsNone(db.get(RoundSubmission, second_submission.id))
            self.assertEqual(db.scalars(select(UsageCharge).where(UsageCharge.connection_id == connection_ab.id)).all(), [])
            self.assertIsNotNone(db.get(Connection, connection_ac.id))
            self.assertIsNotNone(db.get(Round, round_ac.id))
            self.assertEqual(len(list_history(connection_ac.id, user=alice, db=db)), 2)


if __name__ == "__main__":
    unittest.main()
