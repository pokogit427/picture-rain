import json
from datetime import datetime, timedelta, timezone
from pathlib import Path as FilePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, ImageFilter, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.asset_images import normalize_image
from app.auth import get_current_user
from app.db import get_db
from app.models import Asset, Draft, HistoryEntry, Round, RoundInput, RoundSubmission, User
from app.pairing import find_member_connection
from app.schemas import (
    InboxItem,
    InputAssetResponse,
    DraftResponse,
    HistoryDeleteRequest,
    HistoryItem,
    HistoryTrashItem,
    ResultResponse,
    SubmissionResponse,
    RoundCreateRequest,
    RoundDetail,
    RoundInputRequest,
    RoundSummary,
)
from app.storage import MAX_UPLOAD_BYTES, asset_path, mosaic_path
from app.usage import reserve_round_charge

router = APIRouter(tags=["rounds"])
ROUND_TTL = timedelta(hours=24)
TRASH_TTL = timedelta(days=30)
MAX_DRAFT_DOCUMENT_BYTES = 200_000
MAX_DRAFT_STROKES = 2_000
MAX_DRAFT_LAYERS = 40


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


def _draft_response(db: Session, draft: Draft) -> DraftResponse:
    preview = None
    if draft.preview_asset_id:
        asset = db.get(Asset, draft.preview_asset_id)
        if asset is not None and asset.state == "ACTIVE":
            preview = _asset_response(asset)
    return DraftResponse(
        id=draft.id,
        round_id=draft.round_id,
        version=draft.version,
        document=json.loads(draft.document_json),
        preview=preview,
        updated_at=draft.updated_at,
        expires_at=draft.expires_at,
    )


def _submission_response(db: Session, submission: RoundSubmission) -> SubmissionResponse:
    asset = db.get(Asset, submission.asset_id)
    if asset is None or asset.state != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Submitted result is no longer available.")
    return SubmissionResponse(
        id=submission.id,
        round_id=submission.round_id,
        status=submission.status,
        result=_asset_response(asset),
        submitted_at=submission.submitted_at,
    )


def _existing_submission(db: Session, round_id: str, user_id: str) -> RoundSubmission | None:
    return db.scalar(
        select(RoundSubmission).where(
            RoundSubmission.round_id == round_id,
            RoundSubmission.editor_id == user_id,
        )
    )


def _result_response(round_item: Round, submission: RoundSubmission, user_id: str, db: Session) -> ResultResponse:
    asset = db.get(Asset, submission.asset_id)
    if asset is None or asset.state != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    visibility = "ORIGINAL" if round_item.status == "REVEALED" else "MOSAIC"
    return ResultResponse(
        submission_id=submission.id,
        is_mine=submission.editor_id == user_id,
        visibility=visibility,
        content_type=asset.content_type,
        size=asset.size,
        width=asset.width,
        height=asset.height,
        submitted_at=submission.submitted_at,
        url=f"/rounds/{round_item.id}/results/{submission.id}/content",
    )


def _ensure_mosaic(asset: Asset) -> FilePath:
    source = FilePath(asset.storage_path)
    if not source.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    destination = mosaic_path(asset.id)
    if destination.is_file():
        return destination
    try:
        with Image.open(source) as original:
            image = original.convert("RGB")
            image.thumbnail((32, 32), Image.Resampling.LANCZOS)
            image = image.resize((max(image.width * 8, 128), max(image.height * 8, 128)), Image.Resampling.NEAREST)
            image = image.filter(ImageFilter.GaussianBlur(radius=5))
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, format="WEBP", quality=45, method=4)
    except (OSError, UnidentifiedImageError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Result could not be prepared.") from None
    return destination


def _history_response(db: Session, entry: HistoryEntry, round_item: Round, submission: RoundSubmission, user_id: str) -> HistoryItem:
    asset = db.get(Asset, submission.asset_id)
    if asset is None or asset.state != "ACTIVE" or round_item.revealed_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found.")
    return HistoryItem(
        entry_id=entry.id,
        connection_id=entry.connection_id,
        round_id=entry.round_id,
        submission_id=submission.id,
        is_mine=submission.editor_id == user_id,
        content_type=asset.content_type,
        size=asset.size,
        width=asset.width,
        height=asset.height,
        submitted_at=submission.submitted_at,
        revealed_at=round_item.revealed_at,
        url=f"/connections/{entry.connection_id}/history/{entry.id}/content",
    )


def _history_trash_response(db: Session, entry: HistoryEntry, round_item: Round, submission: RoundSubmission, user_id: str) -> HistoryTrashItem:
    if entry.deleted_at is None or entry.purge_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trash item not found.")
    item = _history_response(db, entry, round_item, submission, user_id)
    return HistoryTrashItem(
        **item.model_dump(),
        deleted_at=entry.deleted_at,
        purge_at=entry.purge_at,
    )


def _parse_draft_document(document_json: str) -> dict:
    if len(document_json.encode("utf-8")) > MAX_DRAFT_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Editor draft is too large.",
        )
    try:
        document = json.loads(document_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Editor draft is invalid.") from None
    if not isinstance(document, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Editor draft is invalid.")
    strokes = document.get("strokes", [])
    layers = document.get("layers", [])
    if not isinstance(strokes, list) or not isinstance(layers, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Editor draft is invalid.")
    if len(strokes) > MAX_DRAFT_STROKES or len(layers) > MAX_DRAFT_LAYERS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Editor draft has too many layers.")
    return document


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
    round_item = Round(
        id=uuid4().hex,
        connection_id=connection.id,
        created_by_id=user.id,
        expires_at=now + ROUND_TTL,
    )
    db.add(round_item)
    db.flush()
    reserve_round_charge(
        db,
        user_id=user.id,
        connection_id=connection.id,
        round_id=round_item.id,
    )
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
        id=uuid4().hex,
        connection_id=connection.id,
        created_by_id=user.id,
        expires_at=now + ROUND_TTL,
    )
    db.add(round_item)
    db.flush()
    reserve_round_charge(
        db,
        user_id=user.id,
        connection_id=connection.id,
        round_id=round_item.id,
    )
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
    if _existing_submission(db, round_id, user.id) is not None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already submitted this round.")
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


@router.get("/rounds/{round_id}/draft", response_model=DraftResponse)
def get_draft(
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DraftResponse:
    _load_member_round(db, round_id, user.id)
    if _existing_submission(db, round_id, user.id) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    draft = db.scalar(
        select(Draft).where(
            Draft.round_id == round_id,
            Draft.editor_id == user.id,
            Draft.status == "ACTIVE",
        )
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    if draft.expires_at <= _now():
        draft.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    return _draft_response(db, draft)


@router.put("/rounds/{round_id}/draft", response_model=DraftResponse)
async def save_draft(
    document_json: str = Form(...),
    version: int = Form(default=1, ge=1),
    file: UploadFile | None = File(default=None),
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DraftResponse:
    round_item = _load_member_round(db, round_id, user.id)
    _expire_if_needed(round_item, _now())
    if round_item.status != "OPEN":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Round is no longer editable.")
    if _existing_submission(db, round_id, user.id) is not None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already submitted this round.")
    document = _parse_draft_document(document_json)
    draft = db.scalar(
        select(Draft).where(Draft.round_id == round_id, Draft.editor_id == user.id)
    )
    old_asset = None
    if draft is None:
        draft = Draft(
            round_id=round_id,
            editor_id=user.id,
            version=1,
            document_json=json.dumps(document, ensure_ascii=False, separators=(",", ":")),
            expires_at=_now() + ROUND_TTL,
        )
        db.add(draft)
    else:
        old_asset = db.get(Asset, draft.preview_asset_id) if draft.preview_asset_id else None
        draft.version = max(draft.version + 1, version)
        draft.document_json = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        draft.status = "ACTIVE"
        draft.expires_at = _now() + ROUND_TTL
    new_asset = None
    try:
        if file is not None:
            normalized = await _read_normalized_upload(file)
            new_asset = _store_asset(
                db,
                normalized=normalized,
                connection_id=round_item.connection_id,
                round_id=round_id,
                owner_id=user.id,
                kind="DRAFT_PREVIEW",
            )
            draft.preview_asset_id = new_asset.id
        draft.updated_at = _now()
        db.commit()
    except Exception:
        db.rollback()
        if new_asset is not None:
            asset_path(new_asset.id, new_asset.content_type).unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Draft could not be saved.") from None
    if old_asset is not None and new_asset is not None:
        old_asset.state = "DELETED"
        db.commit()
        asset_path(old_asset.id, old_asset.content_type).unlink(missing_ok=True)
    return _draft_response(db, draft)


@router.post("/rounds/{round_id}/submit", response_model=SubmissionResponse)
def submit_round(
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    round_item = _load_member_round(db, round_id, user.id)
    locked_round = db.scalar(
        select(Round).where(Round.id == round_id).with_for_update()
    )
    if locked_round is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found.")
    round_item = locked_round
    existing = _existing_submission(db, round_id, user.id)
    if existing is not None:
        return _submission_response(db, existing)
    _expire_if_needed(round_item, _now())
    if round_item.status != "OPEN":
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Round is no longer accepting submissions.")
    draft = db.scalar(
        select(Draft).where(
            Draft.round_id == round_id,
            Draft.editor_id == user.id,
            Draft.status == "ACTIVE",
        )
    )
    if draft is None or draft.expires_at <= _now() or draft.preview_asset_id is None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Save a composed draft before submitting.")
    asset = db.get(Asset, draft.preview_asset_id)
    if asset is None or asset.state != "ACTIVE" or asset.owner_id != user.id:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft preview is no longer available.")
    asset.kind = "SUBMISSION"
    submission = RoundSubmission(
        round_id=round_id,
        editor_id=user.id,
        asset_id=asset.id,
    )
    draft.preview_asset_id = None
    db.add(submission)
    db.delete(draft)
    try:
        db.flush()
        submission_count = db.scalar(
            select(func.count()).select_from(RoundSubmission).where(
                RoundSubmission.round_id == round_id,
            )
        ) or 0
        if submission_count >= 2:
            round_item.status = "REVEALED"
            round_item.revealed_at = _now()
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = _existing_submission(db, round_id, user.id)
        if raced is not None:
            return _submission_response(db, raced)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The round submission already exists.") from None
    return _submission_response(db, submission)


@router.get("/rounds/{round_id}/results", response_model=list[ResultResponse])
def list_results(
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResultResponse]:
    round_item = _load_member_round(db, round_id, user.id)
    submissions = db.scalars(
        select(RoundSubmission)
        .where(RoundSubmission.round_id == round_id)
        .order_by(RoundSubmission.submitted_at.asc())
    ).all()
    return [_result_response(round_item, submission, user.id, db) for submission in submissions]


@router.get("/rounds/{round_id}/results/{submission_id}/content", response_class=FileResponse)
def download_result(
    round_id: str = Path(min_length=32, max_length=32),
    submission_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    round_item = _load_member_round(db, round_id, user.id)
    submission = db.scalar(
        select(RoundSubmission).where(
            RoundSubmission.id == submission_id,
            RoundSubmission.round_id == round_id,
        )
    )
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    asset = db.get(Asset, submission.asset_id)
    if asset is None or asset.state != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    history_entry = db.scalar(
        select(HistoryEntry).where(
            HistoryEntry.submission_id == submission.id,
            HistoryEntry.viewer_id == user.id,
        )
    )
    if history_entry is not None and history_entry.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    if round_item.status == "REVEALED":
        path = FilePath(asset.storage_path)
        media_type = asset.content_type
    else:
        path = _ensure_mosaic(asset)
        media_type = "image/webp"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})


@router.get("/connections/{connection_id}/history", response_model=list[HistoryItem])
def list_history(
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryItem]:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    rounds = db.scalars(
        select(Round)
        .where(Round.connection_id == connection_id, Round.status == "REVEALED")
        .order_by(Round.revealed_at.desc())
    ).all()
    result: list[HistoryItem] = []
    for round_item in rounds:
        submissions = db.scalars(
            select(RoundSubmission).where(RoundSubmission.round_id == round_item.id)
        ).all()
        for submission in submissions:
            entry = db.scalar(
                select(HistoryEntry).where(
                    HistoryEntry.viewer_id == user.id,
                    HistoryEntry.submission_id == submission.id,
                )
            )
            if entry is None:
                entry = HistoryEntry(
                    connection_id=connection_id,
                    round_id=round_item.id,
                    submission_id=submission.id,
                    viewer_id=user.id,
                )
                db.add(entry)
                db.flush()
            if entry.status == "ACTIVE":
                result.append(_history_response(db, entry, round_item, submission, user.id))
    db.commit()
    return result


@router.post("/connections/{connection_id}/history/delete", response_model=list[str])
def delete_history(
    payload: HistoryDeleteRequest,
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    target_ids = set(payload.entry_ids)
    entries = db.scalars(
        select(HistoryEntry).where(
            HistoryEntry.id.in_(target_ids),
            HistoryEntry.connection_id == connection_id,
            HistoryEntry.viewer_id == user.id,
            HistoryEntry.status == "ACTIVE",
        )
    ).all()
    if len(entries) != len(target_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more history items were not found.")
    now = _now()
    for entry in entries:
        entry.status = "TRASH"
        entry.deleted_at = now
        entry.purge_at = now + TRASH_TTL
    db.commit()
    return [entry.id for entry in entries]


@router.delete("/connections/{connection_id}/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history_item(
    connection_id: str = Path(min_length=32, max_length=32),
    entry_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_history(
        HistoryDeleteRequest(entry_ids=[entry_id]),
        connection_id=connection_id,
        user=user,
        db=db,
    )


@router.get("/connections/{connection_id}/trash", response_model=list[HistoryTrashItem])
def list_trash(
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryTrashItem]:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    entries = db.scalars(
        select(HistoryEntry)
        .where(
            HistoryEntry.connection_id == connection_id,
            HistoryEntry.viewer_id == user.id,
            HistoryEntry.status == "TRASH",
        )
        .order_by(HistoryEntry.purge_at.asc())
    ).all()
    result: list[HistoryTrashItem] = []
    for entry in entries:
        if entry.purge_at is None or entry.purge_at <= _now():
            continue
        round_item = db.get(Round, entry.round_id)
        submission = db.get(RoundSubmission, entry.submission_id)
        if round_item is not None and submission is not None and round_item.status == "REVEALED":
            result.append(_history_trash_response(db, entry, round_item, submission, user.id))
    return result


@router.post("/connections/{connection_id}/trash/{entry_id}/restore", response_model=HistoryItem)
def restore_history_item(
    connection_id: str = Path(min_length=32, max_length=32),
    entry_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryItem:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    entry = db.scalar(
        select(HistoryEntry).where(
            HistoryEntry.id == entry_id,
            HistoryEntry.connection_id == connection_id,
            HistoryEntry.viewer_id == user.id,
            HistoryEntry.status == "TRASH",
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trash item not found.")
    if entry.purge_at is None or entry.purge_at <= _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Trash item can no longer be restored.")
    round_item = db.get(Round, entry.round_id)
    submission = db.get(RoundSubmission, entry.submission_id)
    if round_item is None or submission is None or round_item.status != "REVEALED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found.")
    entry.status = "ACTIVE"
    entry.deleted_at = None
    entry.purge_at = None
    db.commit()
    return _history_response(db, entry, round_item, submission, user.id)


@router.get("/connections/{connection_id}/history/{entry_id}/content", response_class=FileResponse)
def download_history_item(
    connection_id: str = Path(min_length=32, max_length=32),
    entry_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found.")
    entry = db.scalar(
        select(HistoryEntry).where(
            HistoryEntry.id == entry_id,
            HistoryEntry.connection_id == connection_id,
            HistoryEntry.viewer_id == user.id,
            HistoryEntry.status == "ACTIVE",
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found.")
    round_item = db.get(Round, entry.round_id)
    submission = db.get(RoundSubmission, entry.submission_id)
    asset = db.get(Asset, submission.asset_id) if submission else None
    if round_item is None or round_item.status != "REVEALED" or asset is None or asset.state != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found.")
    path = FilePath(asset.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History item not found.")
    return FileResponse(path, media_type=asset.content_type, headers={"Cache-Control": "private, no-store"})


@router.delete("/rounds/{round_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
def cancel_draft(
    round_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _load_member_round(db, round_id, user.id)
    if _existing_submission(db, round_id, user.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Submitted rounds cannot cancel drafts.")
    draft = db.scalar(
        select(Draft).where(Draft.round_id == round_id, Draft.editor_id == user.id)
    )
    if draft is None:
        return
    preview = db.get(Asset, draft.preview_asset_id) if draft.preview_asset_id else None
    preview_path = asset_path(preview.id, preview.content_type) if preview else None
    if preview is not None:
        preview.state = "DELETED"
    db.delete(draft)
    db.commit()
    if preview_path is not None:
        preview_path.unlink(missing_ok=True)


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
    if asset.kind == "SUBMISSION" and round_item.status != "REVEALED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    if asset.kind == "SUBMISSION":
        history_entry = db.scalar(
            select(HistoryEntry)
            .join(RoundSubmission, RoundSubmission.id == HistoryEntry.submission_id)
            .where(
                RoundSubmission.asset_id == asset.id,
                HistoryEntry.viewer_id == user.id,
            )
        )
        if history_entry is not None and history_entry.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    if asset.kind in {"INSERT", "DRAFT_PREVIEW"} and asset.owner_id != user.id:
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
