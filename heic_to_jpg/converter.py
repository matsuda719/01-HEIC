"""Converter engine: single-file HEIC/HEIF -> JPG conversion.

This module implements the core conversion logic described in ``design.md``
("Components and Interfaces / コンポーネント 3: コンバーター"):

    - :func:`load_heic`        — decode a HEIC/HEIF file into a Pillow ``Image``.
    - :func:`apply_orientation` — upright an image per its EXIF Orientation tag.
    - :func:`extract_exif`     — extract EXIF metadata (Orientation normalized).
    - :func:`convert_file`     — full decode -> upright -> encode pipeline.

The image is always visually uprighted before saving, and the Orientation tag
in any preserved EXIF is normalized to ``1`` so viewers do not rotate the
already-corrected pixels a second time.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from heic_to_jpg._heif import ensure_heif_registered
from heic_to_jpg.models import (
    ConversionOptions,
    ConversionResult,
    ResultStatus,
)

# EXIF tag id for Orientation (0x0112). See EXIF specification.
_ORIENTATION_TAG = 0x0112

# Pillow image modes that JPEG can encode directly without conversion.
_JPEG_SAFE_MODES = {"RGB", "L"}


def load_heic(src: Path) -> Image.Image:
    """Load a HEIC/HEIF file as a Pillow :class:`~PIL.Image.Image`.

    The HEIF opener is registered (idempotently) before opening so that
    ``PIL.Image.open`` recognizes the HEIC/HEIF format.

    Args:
        src: Path to the HEIC/HEIF file to decode.

    Returns:
        A decoded Pillow ``Image``.

    Raises:
        Exception: Any error raised by Pillow / pillow-heif during opening or
            decoding is propagated to the caller (which records it as FAILED).
            Decode errors are intentionally not swallowed here.
    """
    ensure_heif_registered()

    # Open then force decoding via load() so that decode failures surface here
    # rather than lazily later. Errors are intentionally propagated.
    image = Image.open(src)
    image.load()
    return image


def apply_orientation(image: Image.Image) -> Image.Image:
    """Return an image visually uprighted per its EXIF Orientation tag.

    Uses :func:`PIL.ImageOps.exif_transpose`, which correctly handles all eight
    EXIF Orientation values (rotations and mirror/flip variants) and also
    strips the Orientation tag from the returned image's EXIF.

    If the image has no Orientation information, or the Orientation value is
    ``1`` (normal), the image is returned unchanged (no transform applied).

    Args:
        image: A valid Pillow ``Image``.

    Returns:
        The uprighted image. When no transform is needed, the original image
        instance is returned unchanged.
    """
    # exif_transpose returns a new, transposed image when an orientation
    # transform is applied, or a copy/equivalent when orientation is 1 or
    # absent. It returns None only for a None input, which we do not pass.
    transposed = ImageOps.exif_transpose(image)
    return transposed if transposed is not None else image


def extract_exif(image: Image.Image) -> bytes | None:
    """Extract EXIF metadata as a bytes blob, or ``None`` if none exists.

    Because the image is uprighted before saving, the Orientation tag in the
    returned EXIF is normalized to ``1`` (normal) so that downstream viewers do
    not re-apply a rotation to the already-corrected pixels.

    Args:
        image: A valid Pillow ``Image``.

    Returns:
        The EXIF metadata serialized to ``bytes``, or ``None`` when the image
        carries no EXIF metadata.
    """
    exif = image.getexif()

    # An empty Exif mapping means the image has no EXIF metadata to preserve.
    if exif is None or len(exif) == 0:
        return None

    # Normalize Orientation to 1 since the pixels are already uprighted.
    exif[_ORIENTATION_TAG] = 1

    return exif.tobytes()


def convert_file(
    src: Path, dst: Path, options: ConversionOptions
) -> ConversionResult:
    """Convert a single HEIC/HEIF file to JPG.

    Pipeline (see design.md "単一ファイル変換アルゴリズム"):
        1. Decode via :func:`load_heic`.
        2. Correct orientation via :func:`apply_orientation`.
        3. Normalize color mode to ``RGB`` when not already ``RGB``/``L``.
        4. Extract EXIF when ``options.keep_metadata`` is ``True``.
        5. Ensure the destination's parent directory exists.
        6. JPEG-encode at ``options.quality``.

    EXIF extraction/embedding is best-effort: when ``keep_metadata`` is
    ``True`` but extracting or embedding EXIF fails, the conversion still
    proceeds (saving without EXIF) and returns ``SUCCESS``. When
    ``keep_metadata`` is ``False`` no EXIF is written at all.

    Args:
        src: Source HEIC/HEIF path.
        dst: Destination JPG path.
        options: Per-file conversion options (quality, keep_metadata,
            overwrite).

    Returns:
        A :class:`ConversionResult` with status ``SUCCESS`` on completion.

    Raises:
        Exception: Decode failures (from :func:`load_heic`) and write/encode
            failures (from :meth:`PIL.Image.Image.save`) propagate to the
            caller, which records them as ``FAILED``.
    """
    # Step 1: decode.
    image = load_heic(src)

    # Step 2: orientation correction (visually upright the image).
    image = apply_orientation(image)

    # Step 3: color-mode normalization (JPEG supports RGB / L).
    if image.mode not in _JPEG_SAFE_MODES:
        image = image.convert("RGB")

    # Step 4: EXIF extraction (best-effort when metadata preservation is on).
    exif: bytes | None = None
    if options.keep_metadata:
        try:
            exif = extract_exif(image)
        except Exception:
            # EXIF extraction failure must not abort the conversion.
            exif = None

    # Step 5: ensure the destination's parent directory exists.
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Step 6: JPEG encode. Embed EXIF only when we successfully extracted it.
    if exif is not None:
        try:
            image.save(dst, format="JPEG", quality=options.quality, exif=exif)
        except Exception:
            # EXIF embedding failure: retry without EXIF and still succeed.
            image.save(dst, format="JPEG", quality=options.quality)
    else:
        image.save(dst, format="JPEG", quality=options.quality)

    return ConversionResult(src=src, dst=dst, status=ResultStatus.SUCCESS)
