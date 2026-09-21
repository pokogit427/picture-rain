from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Path, Query, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import router as auth_router
from app.db import check_db, get_db, init_db
from app.models import Photo, PhotoVariant
from app.storage import (
    ALLOWED_CONTENT_TYPES,
    CONTENT_TYPE_BY_FORMAT,
    MAX_UPLOAD_BYTES,
    OUTPUT_FORMATS,
    PROCESSED_DIR,
    UPLOAD_DIR,
    find_photo,
    photo_path,
    variant_path,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Picture Rain API",
    version="0.4.0",
    description="Photo upload, transformation, and sharing service.",
    lifespan=lifespan,
)
app.include_router(auth_router)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _created_at(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "picture-rain", "message": "API is running"}


@app.get("/health")
def health(session: Session = Depends(get_db)) -> dict[str, str]:
    check_db(session)
    return {
        "status": "ok",
        "database": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/photos")
def list_photos(
    limit: int = Query(default=100, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[dict[str, str | int | None]]:
    photos = session.scalars(
        select(Photo).order_by(Photo.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": photo.id,
            "filename": photo.original_filename,
            "content_type": photo.content_type,
            "size": photo.size,
            "width": photo.width,
            "height": photo.height,
            "created_at": _created_at(photo.created_at),
            "url": f"/photos/{photo.id}",
        }
        for photo in photos
    ]


@app.post("/photos", status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> dict[str, str | int | None]:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are supported.",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image_format = image.format or ""
            width, height = image.size
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid image.",
        ) from None

    detected_content_type = CONTENT_TYPE_BY_FORMAT.get(image_format.upper())
    if detected_content_type != content_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The file content does not match its content type.",
        )

    photo_id = uuid4().hex
    destination = photo_path(photo_id, content_type)
    destination.write_bytes(content)

    photo = Photo(
        id=photo_id,
        original_filename=file.filename,
        content_type=content_type,
        size=len(content),
        width=width,
        height=height,
        storage_path=str(destination),
    )
    session.add(photo)
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo metadata could not be saved.",
        ) from None

    return {
        "id": photo.id,
        "filename": photo.original_filename or destination.name,
        "content_type": photo.content_type,
        "size": photo.size,
        "width": photo.width,
        "height": photo.height,
        "created_at": _created_at(photo.created_at),
        "url": f"/photos/{photo.id}",
    }


@app.post("/photos/{photo_id}/transform")
def transform_photo(
    photo_id: str,
    width: int = Query(default=800, ge=64, le=2048),
    height: int = Query(default=800, ge=64, le=2048),
    output_format: Literal["jpg", "webp"] = Query(default="webp"),
    session: Session = Depends(get_db),
) -> dict[str, str | int | None]:
    photo = session.get(Photo, photo_id)
    resolved = find_photo(photo_id)
    if photo is None or resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found.",
        )

    source_path, _ = resolved
    destination = variant_path(photo_id, width, height, output_format)
    output_pillow_format, output_content_type, _ = OUTPUT_FORMATS[output_format]

    try:
        with Image.open(source_path) as source:
            source.load()
            transformed = ImageOps.contain(source, (width, height))
            if output_pillow_format == "JPEG" and transformed.mode not in ("RGB", "L"):
                transformed = transformed.convert("RGB")
            destination.parent.mkdir(parents=True, exist_ok=True)
            transformed.save(
                destination,
                format=output_pillow_format,
                quality=85,
                optimize=True,
            )
            actual_width, actual_height = transformed.size
    except (OSError, UnidentifiedImageError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The source image could not be transformed.",
        ) from None

    variant = session.scalar(
        select(PhotoVariant).where(
            PhotoVariant.photo_id == photo_id,
            PhotoVariant.width == width,
            PhotoVariant.height == height,
            PhotoVariant.output_format == output_format,
        )
    )
    if variant is None:
        variant = PhotoVariant(
            photo_id=photo_id,
            width=width,
            height=height,
            output_format=output_format,
            content_type=output_content_type,
            size=destination.stat().st_size,
            storage_path=str(destination),
        )
        session.add(variant)
    else:
        variant.content_type = output_content_type
        variant.width = actual_width
        variant.height = actual_height
        variant.size = destination.stat().st_size
        variant.storage_path = str(destination)

    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo variant metadata could not be saved.",
        ) from None

    return {
        "photo_id": photo_id,
        "content_type": output_content_type,
        "width": actual_width,
        "height": actual_height,
        "size": destination.stat().st_size,
        "created_at": _created_at(variant.created_at),
        "url": f"/photos/{photo_id}/variants/{width}x{height}.{output_format}",
    }


@app.get("/photos/{photo_id}/variants/{width}x{height}.{output_format}")
def download_variant(
    photo_id: str,
    width: int = Path(ge=64, le=2048),
    height: int = Path(ge=64, le=2048),
    output_format: Literal["jpg", "webp"] = Path(),
) -> FileResponse:
    try:
        candidate = variant_path(photo_id, width, height, output_format)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo variant not found.",
        ) from None

    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo variant not found. Generate it first.",
        )

    return FileResponse(
        candidate,
        media_type=OUTPUT_FORMATS[output_format][1],
        filename=candidate.name,
    )


@app.get("/photos/{photo_id}")
def download_photo(photo_id: str) -> FileResponse:
    resolved = find_photo(photo_id)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found.",
        )

    path, content_type = resolved
    return FileResponse(path, media_type=content_type, filename=path.name)
