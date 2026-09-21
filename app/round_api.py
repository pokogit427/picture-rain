from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Round, RoundInput, User
from app.pairing import find_member_connection
from app.schemas import RoundCreateRequest, RoundDetail, RoundInputRequest, RoundSummary

router = APIRouter(tags=["rounds"])
ROUND_TTL = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expire_if_needed(round_item: Round, now: datetime) -> None:
    if round_item.status == "OPEN" and round_item.expires_at <= now:
        round_item.status = "EXPIRED"


def _round_response(round_item: Round, inputs: list[RoundInput], user_id: str) -> RoundDetail:
    mine = next((item for item in inputs if item.sender_id == user_id), None)
    partner = next((item for item in inputs if item.sender_id != user_id), None)
    return RoundDetail(
        id=round_item.id,
        connection_id=round_item.connection_id,
        status=round_item.status,
        created_at=round_item.created_at,
        expires_at=round_item.expires_at,
        has_my_input=mine is not None,
        has_partner_input=partner is not None,
        my_asset_id=mine.asset_id if mine else None,
        partner_asset_id=partner.asset_id if partner else None,
    )


def _load_inputs(db: Session, round_id: str) -> list[RoundInput]:
    return db.scalars(select(RoundInput).where(RoundInput.round_id == round_id)).all()


def _load_member_round(db: Session, round_id: str, user_id: str) -> Round:
    round_item = db.get(Round, round_id)
    if round_item is None or find_member_connection(db, round_item.connection_id, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found.")
    return round_item


@router.post(
    "/connections/{connection_id}/rounds",
    response_model=RoundDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_round(
    payload: RoundCreateRequest,
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoundDetail:
    connection = find_member_connection(db, connection_id, user.id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    now = _now()
    round_item = Round(
        connection_id=connection.id,
        created_by_id=user.id,
        expires_at=now + ROUND_TTL,
    )
    db.add(round_item)
    db.flush()
    db.add(RoundInput(round_id=round_item.id, sender_id=user.id, asset_id=payload.asset_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The round could not be created.") from None
    return _round_response(round_item, _load_inputs(db, round_item.id), user.id)


@router.get("/connections/{connection_id}/rounds", response_model=list[RoundSummary])
def list_rounds(
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RoundSummary]:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    now = _now()
    rounds = db.scalars(
        select(Round).where(Round.connection_id == connection_id).order_by(Round.created_at.desc())
    ).all()
    result: list[RoundSummary] = []
    for round_item in rounds:
        _expire_if_needed(round_item, now)
        inputs = _load_inputs(db, round_item.id)
        result.append(
            RoundSummary(
                id=round_item.id,
                connection_id=round_item.connection_id,
                status=round_item.status,
                created_at=round_item.created_at,
                expires_at=round_item.expires_at,
                has_my_input=any(item.sender_id == user.id for item in inputs),
                has_partner_input=any(item.sender_id != user.id for item in inputs),
            )
        )
    db.commit()
    return result


@router.get("/rounds/{round_id}", response_model=RoundDetail)
def get_round(
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoundDetail:
    round_item = _load_member_round(db, round_id, user.id)
    _expire_if_needed(round_item, _now())
    inputs = _load_inputs(db, round_item.id)
    db.commit()
    return _round_response(round_item, inputs, user.id)


@router.post("/rounds/{round_id}/inputs", response_model=RoundDetail)
def add_round_input(
    payload: RoundInputRequest,
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoundDetail:
    round_item = _load_member_round(db, round_id, user.id)
    _expire_if_needed(round_item, _now())
    if round_item.status != "OPEN":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Round is no longer accepting inputs.")
    existing = db.scalar(
        select(RoundInput).where(RoundInput.round_id == round_id, RoundInput.sender_id == user.id)
    )
    if existing is not None:
        if existing.asset_id == payload.asset_id:
            inputs = _load_inputs(db, round_id)
            db.rollback()
            return _round_response(round_item, inputs, user.id)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Your round input is already fixed.")
    db.add(RoundInput(round_id=round_id, sender_id=user.id, asset_id=payload.asset_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Your round input is already fixed.") from None
    return _round_response(round_item, _load_inputs(db, round_id), user.id)
