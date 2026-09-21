import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Connection, InviteAttempt, InviteCode, User
from app.pairing import create_connection, find_connection
from app.schemas import ConnectionRequest, ConnectionResponse, InviteResponse

router = APIRouter(tags=["pairing"])

INVITE_CODE_TTL = timedelta(minutes=5)
INVITE_ATTEMPT_WINDOW = timedelta(minutes=15)
INVITE_MAX_ATTEMPTS = 5
_INVITE_CODE_PATTERN = re.compile(r"^\d{4}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _invite_pepper() -> str:
    return os.getenv("INVITE_CODE_PEPPER", "picture-rain-local-invite-pepper")


def hash_invite_code(code: str) -> str:
    return hashlib.sha256(f"{_invite_pepper()}:{code}".encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10_000):04d}"


def _issue_invite(db: Session, owner_id: str) -> InviteResponse:
    now = _now()
    current_codes = db.scalars(
        select(InviteCode)
        .where(
            InviteCode.owner_id == owner_id,
            InviteCode.revoked_at.is_(None),
            InviteCode.used_at.is_(None),
            InviteCode.expires_at > now,
        )
        .with_for_update()
    ).all()
    for current in current_codes:
        current.revoked_at = now

    code = _generate_code()
    expires_at = now + INVITE_CODE_TTL
    db.add(
        InviteCode(
            id=uuid4().hex,
            owner_id=owner_id,
            code_hash=hash_invite_code(code),
            expires_at=expires_at,
        )
    )
    db.commit()
    return InviteResponse(code=code, expires_at=expires_at)


@router.post(
    "/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_invite(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InviteResponse:
    return _issue_invite(db, user.id)


@router.get("/connections", response_model=list[ConnectionResponse])
def list_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConnectionResponse]:
    connections = db.scalars(
        select(Connection)
        .where(
            Connection.status == "ACTIVE",
            or_(Connection.user_low_id == user.id, Connection.user_high_id == user.id),
        )
        .order_by(Connection.created_at.desc())
    ).all()
    return [
        ConnectionResponse(
            id=connection.id,
            partner_user_id=(
                connection.user_high_id
                if connection.user_low_id == user.id
                else connection.user_low_id
            ),
            status=connection.status,
            created_at=connection.created_at,
        )
        for connection in connections
    ]


@router.get("/invites/current", response_model=InviteResponse)
def current_invite(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InviteResponse:
    """Issue a fresh displayable code without touching existing connections."""
    return _issue_invite(db, user.id)


@router.post("/invites/rotate", response_model=InviteResponse)
def rotate_invite(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InviteResponse:
    return _issue_invite(db, user.id)


def _scope_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enforce_attempt_limit(db: Session, scope_key: str, now: datetime) -> None:
    attempt = db.scalar(
        select(InviteAttempt)
        .where(InviteAttempt.scope_key == scope_key)
        .with_for_update()
    )
    if attempt is None:
        return
    if attempt.window_started_at + INVITE_ATTEMPT_WINDOW <= now:
        attempt.window_started_at = now
        attempt.attempts = 0
        attempt.blocked_until = None
        db.flush()
        return
    if attempt.blocked_until is not None and attempt.blocked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many invite code attempts. Try again later.",
            headers={"Retry-After": str(int((attempt.blocked_until - now).total_seconds()))},
        )


def _record_failed_attempt(db: Session, scope_key: str, now: datetime) -> None:
    attempt = db.scalar(
        select(InviteAttempt)
        .where(InviteAttempt.scope_key == scope_key)
        .with_for_update()
    )
    if attempt is None:
        attempt = InviteAttempt(
            id=uuid4().hex,
            scope_key=scope_key,
            window_started_at=now,
            attempts=0,
        )
        db.add(attempt)
    elif attempt.window_started_at + INVITE_ATTEMPT_WINDOW <= now:
        attempt.window_started_at = now
        attempt.attempts = 0
        attempt.blocked_until = None
    attempt.attempts += 1
    if attempt.attempts >= INVITE_MAX_ATTEMPTS:
        attempt.blocked_until = now + INVITE_ATTEMPT_WINDOW
    db.commit()


@router.post(
    "/connections",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept_invite(
    payload: ConnectionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    if not _INVITE_CODE_PATTERN.fullmatch(payload.invite_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invite code must be four digits.",
        )

    now = _now()
    scope_key = _scope_key(request)
    _enforce_attempt_limit(db, scope_key, now)
    invite = db.scalar(
        select(InviteCode)
        .where(
            InviteCode.code_hash == hash_invite_code(payload.invite_code),
            InviteCode.revoked_at.is_(None),
            InviteCode.used_at.is_(None),
        )
        .with_for_update()
    )
    if invite is None or invite.expires_at <= now:
        _record_failed_attempt(db, scope_key, now)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code is invalid or expired.",
        )
    if invite.owner_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot connect to yourself.",
        )
    existing = find_connection(db, user.id, invite.owner_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active connection already exists.",
        )

    connection = create_connection(db, user.id, invite.owner_id)
    invite.used_at = now
    db.add(connection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active connection already exists.",
        ) from None

    db.execute(delete(InviteAttempt).where(InviteAttempt.scope_key == scope_key))
    db.commit()
    return ConnectionResponse(
        id=connection.id,
        partner_user_id=invite.owner_id,
        status=connection.status,
        created_at=connection.created_at or now,
    )
