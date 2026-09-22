import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Connection, Round, UsageCharge, User
from app.usage import reserve_round_charge


class UsageChargeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_same_round_charge_is_idempotent(self) -> None:
        with Session(self.engine) as db:
            user = User(id="1" * 32, login_identifier="usage-user", status="ACTIVE")
            partner = User(id="2" * 32, login_identifier="usage-partner", status="ACTIVE")
            connection = Connection(id="3" * 32, user_low_id=user.id, user_high_id=partner.id, status="ACTIVE")
            round_item = Round(id="4" * 32, connection_id=connection.id, created_by_id=user.id, status="OPEN", expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
            db.add_all([user, partner, connection, round_item])
            db.commit()

            first = reserve_round_charge(db, user_id=user.id, connection_id=connection.id, round_id=round_item.id)
            db.commit()
            second = reserve_round_charge(db, user_id=user.id, connection_id=connection.id, round_id=round_item.id)

            self.assertEqual(first.id, second.id)
            self.assertEqual(len(db.scalars(select(UsageCharge)).all()), 1)

    def test_connection_limit_rejects_fourth_round(self) -> None:
        with Session(self.engine) as db:
            user = User(id="a" * 32, login_identifier="limit-user", status="ACTIVE")
            partner = User(id="b" * 32, login_identifier="limit-partner", status="ACTIVE")
            connection = Connection(id="c" * 32, user_low_id=user.id, user_high_id=partner.id, status="ACTIVE")
            rounds = [Round(id=f"{index:032d}", connection_id=connection.id, created_by_id=user.id, status="OPEN", expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc)) for index in range(1, 5)]
            db.add_all([user, partner, connection, *rounds])
            db.commit()
            for round_item in rounds[:3]:
                reserve_round_charge(db, user_id=user.id, connection_id=connection.id, round_id=round_item.id)
            db.commit()

            with self.assertRaisesRegex(HTTPException, "Daily round limit"):
                reserve_round_charge(db, user_id=user.id, connection_id=connection.id, round_id=rounds[3].id)


if __name__ == "__main__":
    unittest.main()
