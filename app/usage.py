from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.entitlement import current_policy
from app.models import UsageCharge, User


@dataclass(frozen=True)
class UsageSummary:
    usage_date: date
    connection_used: int
    connection_limit: int
    account_used: int
    account_limit: int


def _today() -> date:
    return datetime.now(timezone.utc).date()


def reserve_round_charge(
    db: Session,
    *,
    user_id: str,
    connection_id: str,
    round_id: str,
) -> UsageCharge:
    existing = db.scalar(
        select(UsageCharge).where(UsageCharge.round_id == round_id).with_for_update()
    )
    if existing is not None:
        if existing.user_id != user_id or existing.connection_id != connection_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Round usage charge does not match.")
        return existing

    locked_user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if locked_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    policy = current_policy()
    usage_date = _today()
    connection_used = db.scalar(
        select(func.coalesce(func.sum(UsageCharge.units), 0)).where(
            UsageCharge.user_id == user_id,
            UsageCharge.connection_id == connection_id,
            UsageCharge.usage_date == usage_date,
        )
    ) or 0
    account_used = db.scalar(
        select(func.coalesce(func.sum(UsageCharge.units), 0)).where(
            UsageCharge.user_id == user_id,
        )
    ) or 0
    if connection_used >= policy.daily_rounds_per_connection:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily round limit for this connection has been reached.")
    if account_used >= policy.total_rounds_per_account:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account round limit has been reached.")

    charge = UsageCharge(
        id=uuid4().hex,
        user_id=user_id,
        connection_id=connection_id,
        round_id=round_id,
        usage_date=usage_date,
        units=1,
    )
    db.add(charge)
    return charge


def get_usage_summary(db: Session, *, user_id: str, connection_id: str) -> UsageSummary:
    policy = current_policy()
    usage_date = _today()
    connection_used = db.scalar(
        select(func.coalesce(func.sum(UsageCharge.units), 0)).where(
            UsageCharge.user_id == user_id,
            UsageCharge.connection_id == connection_id,
            UsageCharge.usage_date == usage_date,
        )
    ) or 0
    account_used = db.scalar(
        select(func.coalesce(func.sum(UsageCharge.units), 0)).where(
            UsageCharge.user_id == user_id,
        )
    ) or 0
    return UsageSummary(
        usage_date=usage_date,
        connection_used=connection_used,
        connection_limit=policy.daily_rounds_per_connection,
        account_used=account_used,
        account_limit=policy.total_rounds_per_account,
    )
