from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Connection


class PairingValidationError(ValueError):
    """Raised when a pair cannot represent two distinct users."""


@dataclass(frozen=True)
class MemberPair:
    low_id: str
    high_id: str


def normalize_member_pair(user_a_id: str, user_b_id: str) -> MemberPair:
    if not user_a_id or not user_b_id or user_a_id == user_b_id:
        raise PairingValidationError("A connection requires two distinct users.")
    low_id, high_id = sorted((user_a_id, user_b_id))
    return MemberPair(low_id=low_id, high_id=high_id)


def find_connection(
    db: Session,
    user_a_id: str,
    user_b_id: str,
    *,
    active_only: bool = True,
) -> Connection | None:
    pair = normalize_member_pair(user_a_id, user_b_id)
    statement = select(Connection).where(
        Connection.user_low_id == pair.low_id,
        Connection.user_high_id == pair.high_id,
    )
    if active_only:
        statement = statement.where(Connection.status == "ACTIVE")
    return db.scalar(statement)


def create_connection(db: Session, user_a_id: str, user_b_id: str) -> Connection:
    pair = normalize_member_pair(user_a_id, user_b_id)
    connection = Connection(user_low_id=pair.low_id, user_high_id=pair.high_id)
    db.add(connection)
    return connection


def find_member_connection(
    db: Session, connection_id: str, user_id: str
) -> Connection | None:
    return db.scalar(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.status == "ACTIVE",
            or_(Connection.user_low_id == user_id, Connection.user_high_id == user_id),
        )
    )
