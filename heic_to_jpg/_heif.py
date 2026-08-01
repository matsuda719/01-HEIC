"""HEIF/HEIC opener registration hook.

This module provides an idempotent initialization hook that registers the
HEIF opener from ``pillow_heif`` with Pillow so that HEIC/HEIF files can be
opened via ``PIL.Image.open``.

Call :func:`ensure_heif_registered` before attempting to load HEIC images.
"""

from __future__ import annotations

# Tracks whether the HEIF opener has already been registered so that repeated
# calls are cheap and side-effect free (idempotent).
_registered = False


def ensure_heif_registered() -> None:
    """Register the HEIF opener with Pillow exactly once.

    Safe to call multiple times; the underlying registration only runs on the
    first invocation. Subsequent calls are no-ops.
    """
    global _registered
    if _registered:
        return

    # Imported lazily so that merely importing the package does not require
    # pillow-heif to be installed until conversion is actually attempted.
    from pillow_heif import register_heif_opener

    register_heif_opener()
    _registered = True
