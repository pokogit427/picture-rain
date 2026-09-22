"""Low-cost, repeatable cleanup for temporary exchange data."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import Asset, Draft, Round, RoundSubmission
from app.storage import asset_path, mosaic_path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(value: datetime, current: datetime) -> bool:
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return normalized <= current


def _queue_asset_delete(asset: Asset, paths: list[Path], deleted_ids: set[str]) -> bool:
    if asset.id in deleted_ids:
        return False
    deleted_ids.add(asset.id)
    paths.append(asset_path(asset.id, asset.content_type))
    paths.append(mosaic_path(asset.id))
    asset.state = "DELETED"
    return True


def cleanup_expired_data(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Delete temporary files/rows while keeping only released result assets."""
    current = now or _now()
    paths: list[Path] = []
    deleted_asset_ids: set[str] = set()
    result = {
        "expired_rounds": 0,
        "deleted_drafts": 0,
        "deleted_submissions": 0,
        "deleted_assets": 0,
    }

    rounds = db.scalars(select(Round)).all()
    for round_item in rounds:
        if round_item.status == "OPEN" and _is_expired(round_item.expires_at, current):
            round_item.status = "EXPIRED"
            result["expired_rounds"] += 1

        if round_item.status == "REVEALED":
            assets = db.scalars(
                select(Asset).where(
                    Asset.round_id == round_item.id,
                    Asset.kind.in_(["INPUT", "INSERT"]),
                    Asset.state == "ACTIVE",
                )
            ).all()
            for asset in assets:
                if _queue_asset_delete(asset, paths, deleted_asset_ids):
                    result["deleted_assets"] += 1
        elif round_item.status == "EXPIRED" and round_item.revealed_at is None:
            submissions = db.scalars(
                select(RoundSubmission).where(RoundSubmission.round_id == round_item.id)
            ).all()
            for submission in submissions:
                asset = db.get(Asset, submission.asset_id)
                if asset is not None and _queue_asset_delete(asset, paths, deleted_asset_ids):
                    result["deleted_assets"] += 1
                db.delete(submission)
                result["deleted_submissions"] += 1
            assets = db.scalars(
                select(Asset).where(
                    Asset.round_id == round_item.id,
                    Asset.kind.in_(["INPUT", "INSERT", "DRAFT_PREVIEW"]),
                    Asset.state == "ACTIVE",
                )
            ).all()
            for asset in assets:
                if _queue_asset_delete(asset, paths, deleted_asset_ids):
                    result["deleted_assets"] += 1

    drafts = db.scalars(
        select(Draft).where(Draft.status == "ACTIVE")
    ).all()
    for draft in drafts:
        if not _is_expired(draft.expires_at, current):
            continue
        asset = db.get(Asset, draft.preview_asset_id) if draft.preview_asset_id else None
        if asset is not None and _queue_asset_delete(asset, paths, deleted_asset_ids):
            result["deleted_assets"] += 1
        draft.status = "EXPIRED"
        db.delete(draft)
        result["deleted_drafts"] += 1

    db.flush()
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    return result


def main() -> None:
    init_db()
    with SessionLocal() as db:
        print(json.dumps(cleanup_expired_data(db), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
