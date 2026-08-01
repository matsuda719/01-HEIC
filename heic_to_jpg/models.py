"""Data models and validation for HEIC to JPG conversion.

This module defines the immutable (frozen) data structures used throughout the
converter:

    - :class:`ConversionConfig`  — top-level configuration (CLI-derived).
    - :class:`ConversionOptions` — per-file conversion options.
    - :class:`ResultStatus`      — outcome enumeration for a single file.
    - :class:`ConversionResult`  — result of converting a single file.
    - :class:`ConversionSummary` — aggregate of all results with exit code.

Validation rules (see design.md "Data Models"):
    - ``quality`` must be an integer in the inclusive range 1..100.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Valid inclusive bounds for JPEG quality.
_QUALITY_MIN = 1
_QUALITY_MAX = 100


def _validate_quality(quality: int) -> None:
    """Validate that ``quality`` is an integer within 1..100 inclusive.

    Raises:
        ValueError: if ``quality`` is not an ``int`` or is out of range.
    """
    # ``bool`` is a subclass of ``int``; reject it explicitly to avoid
    # treating ``True``/``False`` as valid quality values.
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise ValueError(
            f"quality must be an integer, got {type(quality).__name__!r}"
        )
    if quality < _QUALITY_MIN or quality > _QUALITY_MAX:
        raise ValueError(
            f"quality must be in range {_QUALITY_MIN}..{_QUALITY_MAX} "
            f"inclusive, got {quality}"
        )


@dataclass(frozen=True)
class ConversionConfig:
    """Top-level conversion configuration.

    Attributes:
        input_path: Input file or directory.
        output_dir: Output directory (``None`` -> same location as input).
        quality: JPEG quality (1-100).
        recursive: Whether to search directories recursively.
        overwrite: Whether to overwrite existing JPG files.
        keep_metadata: Whether to preserve EXIF metadata.
    """

    input_path: Path
    output_dir: Path | None
    quality: int
    recursive: bool
    overwrite: bool
    keep_metadata: bool

    def __post_init__(self) -> None:
        _validate_quality(self.quality)


@dataclass(frozen=True)
class ConversionOptions:
    """Per-file conversion options.

    Attributes:
        quality: JPEG quality (1-100).
        keep_metadata: Whether to preserve EXIF metadata.
        overwrite: Whether overwriting existing files is permitted.
    """

    quality: int
    keep_metadata: bool
    overwrite: bool

    def __post_init__(self) -> None:
        _validate_quality(self.quality)


class ResultStatus(Enum):
    """Outcome of converting a single HEIC file."""

    SUCCESS = "success"
    SKIPPED = "skipped"  # existing file skipped when overwrite is disabled
    FAILED = "failed"


@dataclass(frozen=True)
class ConversionResult:
    """Result of converting a single HEIC file.

    Attributes:
        src: Source HEIC/HEIF path.
        dst: Destination JPG path (``None`` when no file was produced).
        status: Outcome status.
        error_message: Failure reason when ``status`` is ``FAILED``.
    """

    src: Path
    dst: Path | None
    status: ResultStatus
    error_message: str | None = None


@dataclass(frozen=True)
class ConversionSummary:
    """Aggregate of all per-file conversion results."""

    results: list[ConversionResult]

    @property
    def succeeded(self) -> int:
        """Number of results with status SUCCESS."""
        return sum(1 for r in self.results if r.status is ResultStatus.SUCCESS)

    @property
    def skipped(self) -> int:
        """Number of results with status SKIPPED."""
        return sum(1 for r in self.results if r.status is ResultStatus.SKIPPED)

    @property
    def failed(self) -> int:
        """Number of results with status FAILED."""
        return sum(1 for r in self.results if r.status is ResultStatus.FAILED)

    @property
    def exit_code(self) -> int:
        """Process exit code: 1 if any failures, else 0."""
        return 1 if self.failed > 0 else 0
