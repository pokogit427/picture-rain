import os
from pathlib import Path
from uuid import UUID

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/data/uploads"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "/app/data/processed"))
ASSET_DIR = Path(os.getenv("ASSET_DIR", "/app/data/uploads/assets"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

CONTENT_TYPE_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

OUTPUT_FORMATS = {
    "jpg": ("JPEG", "image/jpeg", ".jpg"),
    "webp": ("WEBP", "image/webp", ".webp"),
}


def _validate_photo_id(photo_id: str) -> str:
    try:
        return UUID(photo_id).hex
    except ValueError:
        raise ValueError("Invalid photo id") from None


def photo_path(photo_id: str, content_type: str) -> Path:
    normalized_id = _validate_photo_id(photo_id)
    return UPLOAD_DIR / f"{normalized_id}{ALLOWED_CONTENT_TYPES[content_type]}"


def find_photo(photo_id: str) -> tuple[Path, str] | None:
    try:
        normalized_id = _validate_photo_id(photo_id)
    except ValueError:
        return None

    for content_type, extension in ALLOWED_CONTENT_TYPES.items():
        candidate = UPLOAD_DIR / f"{normalized_id}{extension}"
        if candidate.is_file():
            return candidate, content_type
    return None


def variant_path(photo_id: str, width: int, height: int, output_format: str) -> Path:
    normalized_id = _validate_photo_id(photo_id)
    if output_format not in OUTPUT_FORMATS:
        raise ValueError("Unsupported output format")
    extension = OUTPUT_FORMATS[output_format][2]
    return PROCESSED_DIR / f"{normalized_id}_{width}x{height}{extension}"


def asset_path(asset_id: str, content_type: str) -> Path:
    normalized_id = _validate_photo_id(asset_id)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported asset content type")
    return ASSET_DIR / f"{normalized_id}{ALLOWED_CONTENT_TYPES[content_type]}"


def mosaic_path(asset_id: str) -> Path:
    normalized_id = _validate_photo_id(asset_id)
    return ASSET_DIR / f"{normalized_id}.mosaic.webp"
