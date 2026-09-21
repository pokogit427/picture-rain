from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.storage import ALLOWED_CONTENT_TYPES, CONTENT_TYPE_BY_FORMAT, MAX_UPLOAD_BYTES

MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_EDGE = 2048


@dataclass(frozen=True)
class NormalizedImage:
    content: bytes
    content_type: str
    width: int
    height: int


def normalize_image(content: bytes, declared_content_type: str) -> NormalizedImage:
    declared = (declared_content_type or "").lower()
    if declared not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Only JPEG, PNG, and WebP images are supported.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Image must be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.load()
            image_format = image.format or ""
            detected_content_type = CONTENT_TYPE_BY_FORMAT.get(image_format.upper())
            if detected_content_type != declared:
                raise ValueError("The file content does not match its content type.")
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError("Image pixel count is too large.")
            if max(width, height) > MAX_IMAGE_EDGE:
                raise ValueError("Image longest edge must be at most 2048 pixels.")
            normalized = ImageOps.exif_transpose(image).copy()
    except (UnidentifiedImageError, OSError):
        raise ValueError("The uploaded file is not a valid image.") from None

    output = BytesIO()
    output_format = image_format.upper()
    if output_format == "JPEG" and normalized.mode not in ("RGB", "L"):
        normalized = normalized.convert("RGB")
    save_kwargs: dict[str, object] = {}
    if output_format == "JPEG":
        save_kwargs = {"quality": 92, "optimize": True}
    elif output_format == "PNG":
        save_kwargs = {"optimize": True}
    elif output_format == "WEBP":
        save_kwargs = {"quality": 92, "method": 4}
    normalized.save(output, format=output_format, **save_kwargs)
    normalized.close()
    return NormalizedImage(
        content=output.getvalue(),
        content_type=declared,
        width=width,
        height=height,
    )
