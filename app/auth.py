import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.models import User, UserSession
from app.schemas import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE_NAME = "picture_rain_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
MIN_PASSWORD_LENGTH = 12
_LOGIN_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")
_password_hasher = PasswordHasher()


def normalize_login_identifier(value: str) -> str:
    normalized = value.strip().lower()
    if not _LOGIN_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Username must be 3-32 characters using lowercase letters, "
                "numbers, or underscores."
            ),
        )
    return normalized


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _session_cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=_session_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=_session_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _new_session(user_id: str, db: DbSession) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            id=uuid4().hex,
            token_hash=hash_session_token(raw_token),
            user_id=user_id,
            expires_at=utc_now() + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
        )
    )
    return raw_token


def _user_response(user: User) -> UserResponse:
    if user.created_at is None or user.login_identifier is None:
        raise RuntimeError("Authenticated user has incomplete identity data")
    return UserResponse(
        id=user.id,
        login_identifier=user.login_identifier,
        status=user.status,
        created_at=user.created_at,
    )


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
) -> User:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    now = utc_now()
    user = db.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_session_token(raw_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            User.status == "ACTIVE",
        )
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: DbSession = Depends(get_db),
) -> UserResponse:
    login_identifier = normalize_login_identifier(payload.login_identifier)
    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )

    user = User(
        login_identifier=login_identifier,
        password_hash=hash_password(payload.password),
        status="ACTIVE",
    )
    db.add(user)
    try:
        db.flush()
        raw_token = _new_session(user.id, db)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already registered.",
        ) from None

    _set_session_cookie(response, raw_token)
    return _user_response(user)


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession = Depends(get_db),
) -> UserResponse:
    login_identifier = normalize_login_identifier(payload.login_identifier)
    user = db.scalar(
        select(User).where(
            User.login_identifier == login_identifier,
            User.status == "ACTIVE",
        )
    )
    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    raw_token = _new_session(user.id, db)
    db.commit()
    _set_session_cookie(response, raw_token)
    return _user_response(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout(
    request: Request,
    db: DbSession = Depends(get_db),
) -> Response:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if raw_token:
        user_session = db.scalar(
            select(UserSession).where(
                UserSession.token_hash == hash_session_token(raw_token),
                UserSession.revoked_at.is_(None),
            )
        )
        if user_session is not None:
            user_session.revoked_at = utc_now()
            db.commit()
    logout_response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookie(logout_response)
    return logout_response


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)
