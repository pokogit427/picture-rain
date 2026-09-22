from datetime import datetime, timedelta, timezone
from pathlib import Path as FilePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.asset_images import normalize_image
from app.auth import get_current_user
from app.db import get_db
from app.models import Asset, Round, RoundInput, User
from app.pairing import find_member_connection
from app.schemas import (
    InboxItem,
    InputAssetResponse,
    RoundCreateRequest,
    RoundDetail,
    RoundInputRequest,
    RoundSummary,
)
from app.storage import MAX_UPLOAD_BYTES, asset_path

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


def _asset_response(asset: Asset) -> InputAssetResponse:
    return InputAssetResponse(
        id=asset.id,
        content_type=asset.content_type,
        size=asset.size,
        width=asset.width,
        height=asset.height,
        created_at=asset.created_at,
        url=f"/assets/{asset.id}/content",
    )


def _partner_asset(db: Session, round_id: str, user_id: str) -> Asset:
    input_item = db.scalar(
        select(RoundInput).where(
            RoundInput.round_id == round_id,
            RoundInput.sender_id != user_id,
        )
    )
    if input_item is None or input_item.asset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Received photo is not ready.")
    asset = db.get(Asset, input_item.asset_id)
    if asset is None or asset.state != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Received photo is not ready.")
    return asset


async def _read_normalized_upload(file: UploadFile):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        return normalize_image(content, file.content_type or "")
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from None


def _store_asset(
    db: Session,
    *,
    normalized,
    connection_id: str,
    round_id: str,
    owner_id: str,
    kind: str = "INPUT",
) -> Asset:
    asset_id = uuid4().hex
    destination = asset_path(asset_id, normalized.content_type)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(normalized.content)
    asset = Asset(
        id=asset_id,
        connection_id=connection_id,
        round_id=round_id,
        owner_id=owner_id,
        kind=kind,
        content_type=normalized.content_type,
        size=len(normalized.content),
        width=normalized.width,
        height=normalized.height,
        storage_path=str(destination),
        expires_at=_now() + ROUND_TTL,
    )
    db.add(asset)
    return asset


async def _create_round_with_upload(
    *,
    connection_id: str,
    user: User,
    file: UploadFile,
    db: Session,
) -> RoundDetail:
    connection = find_member_connection(db, connection_id, user.id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    normalized = await _read_normalized_upload(file)
    now = _now()
    round_item = Round(connection_id=connection.id, created_by_id=user.id, expires_at=now + ROUND_TTL)
    db.add(round_item)
    db.flush()
    asset = _store_asset(
        db,
        normalized=normalized,
        connection_id=connection.id,
        round_id=round_item.id,
        owner_id=user.id,
    )
    db.add(RoundInput(round_id=round_item.id, sender_id=user.id, asset_id=asset.id))
    try:
        db.commit()
    except Exception:
        db.rollback()
        asset_path(asset.id, asset.content_type).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo input could not be saved.",
        ) from None
    return _round_response(round_item, _load_inputs(db, round_item.id), user.id)


@router.post(
    "/connections/{connection_id}/rounds/upload",
    response_model=RoundDetail,
    status_code=status.HTTP_201_CREATED,
)
async def upload_first_round_input(
    file: UploadFile = File(...),
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoundDetail:
    return await _create_round_with_upload(
        connection_id=connection_id, user=user, file=file, db=db
    )


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


@router.post("/rounds/{round_id}/input-upload", response_model=RoundDetail)
async def upload_partner_round_input(
    file: UploadFile = File(...),
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
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Your round input is already fixed.")
    normalized = await _read_normalized_upload(file)
    asset = _store_asset(
        db,
        normalized=normalized,
        connection_id=round_item.connection_id,
        round_id=round_item.id,
        owner_id=user.id,
    )
    db.add(RoundInput(round_id=round_id, sender_id=user.id, asset_id=asset.id))
    try:
        db.commit()
    except Exception:
        db.rollback()
        asset_path(asset.id, asset.content_type).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo input could not be saved.",
        ) from None
    return _round_response(round_item, _load_inputs(db, round_id), user.id)


@router.post("/rounds/{round_id}/layers", response_model=InputAssetResponse)
async def upload_layer_asset(
    file: UploadFile = File(...),
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InputAssetResponse:
    round_item = _load_member_round(db, round_id, user.id)
    _expire_if_needed(round_item, _now())
    if round_item.status != "OPEN":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Round is no longer editable.")
    layer_count = db.scalar(
        select(func.count()).select_from(Asset).where(
            Asset.round_id == round_id,
            Asset.owner_id == user.id,
            Asset.kind == "INSERT",
            Asset.state == "ACTIVE",
        )
    ) or 0
    if layer_count >= 10:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You can insert at most 10 photos per round.")
    normalized = await _read_normalized_upload(file)
    asset = _store_asset(
        db,
        normalized=normalized,
        connection_id=round_item.connection_id,
        round_id=round_item.id,
        owner_id=user.id,
        kind="INSERT",
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        asset_path(asset.id, asset.content_type).unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Layer photo could not be saved.") from None
    return _asset_response(asset)


@router.get("/connections/{connection_id}/inbox", response_model=list[InboxItem])
def list_inbox(
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InboxItem]:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    now = _now()
    rounds = db.scalars(
        select(Round).where(Round.connection_id == connection_id).order_by(Round.created_at.desc())
    ).all()
    result: list[InboxItem] = []
    for round_item in rounds:
        _expire_if_needed(round_item, now)
        try:
            asset = _partner_asset(db, round_item.id, user.id)
        except HTTPException:
            continue
        result.append(
            InboxItem(
                round_id=round_item.id,
                connection_id=round_item.connection_id,
                status=round_item.status,
                created_at=round_item.created_at,
                expires_at=round_item.expires_at,
                input=_asset_response(asset),
            )
        )
    db.commit()
    return result


@router.get("/rounds/{round_id}/input", response_model=InputAssetResponse)
def get_round_input(
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InputAssetResponse:
    _load_member_round(db, round_id, user.id)
    return _asset_response(_partner_asset(db, round_id, user.id))


@router.get("/assets/{asset_id}/content", response_class=FileResponse)
def download_asset(
    asset_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.state != "ACTIVE" or asset.round_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    round_item = db.get(Round, asset.round_id)
    if round_item is None or find_member_connection(db, asset.connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    if asset.kind == "INSERT" and asset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    path = asset.storage_path
    if not path or not FilePath(path).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=f"{asset.id}",
        headers={"Cache-Control": "private, no-store"},
    )
