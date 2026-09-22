"""Low-cost, repeatable cleanup for temporary exchange data."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import Asset, Connection, Draft, HistoryEntry, Round, RoundSubmission
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
        "purged_history": 0,
        "deleted_unreferenced_results": 0,
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

    purged_by_submission: dict[str, set[str]] = {}
    trash_entries = db.scalars(
        select(HistoryEntry).where(HistoryEntry.status.in_(["TRASH", "PURGED"]))
    ).all()
    for entry in trash_entries:
        purged_by_submission.setdefault(entry.submission_id, set()).add(entry.viewer_id)
        if entry.status == "TRASH":
            if entry.purge_at is None or not _is_expired(entry.purge_at, current):
                purged_by_submission[entry.submission_id].discard(entry.viewer_id)
                if not purged_by_submission[entry.submission_id]:
                    del purged_by_submission[entry.submission_id]
                continue
            entry.status = "PURGED"
            result["purged_history"] += 1

    db.flush()
    for submission_id, purged_viewers in purged_by_submission.items():
        submission = db.get(RoundSubmission, submission_id)
        if submission is None:
            continue
        round_item = db.get(Round, submission.round_id)
        connection = db.get(Connection, round_item.connection_id) if round_item else None
        if round_item is None or connection is None:
            continue
        remaining_viewers = set(
            db.scalars(
                select(HistoryEntry.viewer_id).where(
                    HistoryEntry.submission_id == submission_id,
                    HistoryEntry.status.in_(["ACTIVE", "TRASH"]),
                )
            ).all()
        )
        member_ids = {connection.user_low_id, connection.user_high_id}
        if remaining_viewers or not member_ids.issubset(remaining_viewers | purged_viewers):
            continue
        asset = db.get(Asset, submission.asset_id)
        if asset is not None:
            if _queue_asset_delete(asset, paths, deleted_asset_ids):
                result["deleted_assets"] += 1
        db.execute(delete(RoundSubmission).where(RoundSubmission.id == submission.id))
        if asset is not None:
            db.execute(delete(Asset).where(Asset.id == asset.id))
        db.execute(delete(HistoryEntry).where(HistoryEntry.submission_id == submission.id))
        result["deleted_unreferenced_results"] += 1

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
