"""heic_to_jpg — Convert HEIC/HEIF images to JPG.

This package exposes a small public API for converting HEIC/HEIF images to
JPG, either as single files or in bulk over directories.

Public API:
    - :class:`ConversionConfig`  — top-level configuration (CLI-derived).
    - :class:`ConversionOptions` — per-file conversion options.
    - :class:`ConversionResult`  — result of converting a single file.
    - :class:`ConversionSummary` — aggregate of all results with exit code.
    - :class:`ResultStatus`      — per-file outcome enumeration.
    - :func:`run`                — execute the end-to-end conversion workflow.

Importing this package registers the HEIF opener with Pillow (idempotently)
via :func:`ensure_heif_registered`, so the public API works out of the box
without callers needing to perform any manual setup.
"""

from __future__ import annotations

from ._heif import ensure_heif_registered
from .models import (
    ConversionConfig,
    ConversionOptions,
    ConversionResult,
    ConversionSummary,
    ResultStatus,
)
from .orchestrator import run

__version__ = "0.1.0"

# Register the HEIF opener on import so that HEIC/HEIF files can be opened via
# ``PIL.Image.open`` as soon as the package is imported. This is idempotent and
# safe to trigger repeatedly.
ensure_heif_registered()

# Public API surface. Also drives ``from heic_to_jpg import *``.
__all__ = [
    "ConversionConfig",
    "ConversionOptions",
    "ConversionResult",
    "ConversionSummary",
    "ResultStatus",
    "run",
    "ensure_heif_registered",
    "__version__",
]
