"""Orchestration layer: input resolution, discovery, and job execution.

This module coordinates the conversion workflow described in ``design.md``
("Components and Interfaces / コンポーネント 2: オーケストレーター"):

    - :func:`discover_heic_files` — enumerate HEIC/HEIF files under a path.
    - :func:`resolve_output_path` — decide the output JPG path for an input.
    - :func:`run`                 — execute the end-to-end conversion workflow.

Responsibilities include distinguishing single-file vs. directory inputs,
filtering candidate files by extension, deciding output paths and applying the
overwrite policy, and aggregating per-file results into a summary.
"""

from __future__ import annotations

from pathlib import Path

from heic_to_jpg.converter import convert_file
from heic_to_jpg.models import (
    ConversionConfig,
    ConversionOptions,
    ConversionResult,
    ConversionSummary,
    ResultStatus,
)

# Recognized HEIC/HEIF file extensions (compared case-insensitively).
_HEIC_SUFFIXES = frozenset({".heic", ".heif"})

# Lowercase target extension for all produced JPG files.
_JPG_SUFFIX = ".jpg"


def discover_heic_files(path: Path, recursive: bool) -> list[Path]:
    """Enumerate HEIC/HEIF files located under ``path``.

    Only regular files whose extension matches ``.heic`` or ``.heif``
    (compared case-insensitively, e.g. ``.HEIC``/``.HEIF``) are returned.

    Args:
        path: Directory to search for HEIC/HEIF files.
        recursive: When ``True``, files in all subdirectories are included;
            when ``False``, only files directly within ``path`` are considered.

    Returns:
        A deterministically sorted list of matching file paths. When ``path``
        contains no matching files, an empty list is returned.
    """
    # Choose top-level (glob) vs. recursive (rglob) enumeration.
    candidates = path.rglob("*") if recursive else path.glob("*")

    matches = [
        entry
        for entry in candidates
        if entry.is_file() and entry.suffix.lower() in _HEIC_SUFFIXES
    ]

    # Return a stable, deterministic ordering for reproducible results.
    return sorted(matches)


def resolve_output_path(src: Path, config: ConversionConfig) -> Path:
    """Determine the output JPG path for a given input HEIC/HEIF file.

    Follows design.md "出力パス解決アルゴリズム":
        - The output file name is the input file name with its extension
          replaced by the lowercase ``.jpg``.
        - When ``config.output_dir`` is ``None``, the JPG is written next to
          the input file (same directory).
        - When ``config.output_dir`` is set and ``config.recursive`` is enabled
          with a directory input, the input directory's relative structure is
          preserved beneath the output directory.
        - Otherwise, the JPG is written directly into ``config.output_dir``.

    Args:
        src: Source HEIC/HEIF path.
        config: Conversion configuration (output_dir, recursive, input_path).

    Returns:
        The destination JPG path. The returned path always has a ``.jpg``
        suffix.
    """
    # Output file name: input name with the extension replaced by ".jpg".
    base_name = src.with_suffix(_JPG_SUFFIX).name

    if config.output_dir is None:
        # No output directory: write alongside the input file.
        return src.parent / base_name

    if config.recursive and config.input_path.is_dir():
        # Preserve the input directory's relative structure under output_dir.
        rel = src.relative_to(config.input_path)
        return (config.output_dir / rel).with_suffix(_JPG_SUFFIX)

    # Output directory specified (flat): write directly into output_dir.
    return config.output_dir / base_name


def run(config: ConversionConfig) -> ConversionSummary:
    """Execute the end-to-end HEIC/HEIF -> JPG conversion workflow.

    Follows design.md "メイン変換ワークフロー":
        1. Determine the target files: a single-file input yields a one-element
           list; a directory input is enumerated via
           :func:`discover_heic_files` (honoring ``config.recursive``).
        2. For each source file, resolve its destination via
           :func:`resolve_output_path`. When the destination already exists and
           ``config.overwrite`` is disabled, the file is recorded as
           ``SKIPPED`` and the existing file is left untouched. Otherwise the
           file is converted via :func:`convert_file`.
        3. Every per-file conversion is wrapped in ``try``/``except`` so a
           failure is recorded as ``FAILED`` (with its error message) without
           aborting the processing of the remaining files (failure isolation).
        4. All per-file results are aggregated into a
           :class:`ConversionSummary`.

    Args:
        config: Conversion configuration (input path, output dir, quality,
            recursive, overwrite, keep_metadata).

    Returns:
        A :class:`ConversionSummary` whose ``results`` count always equals the
        number of target files. When no target files are found, an empty
        summary (``exit_code`` 0) is returned.
    """
    # Step 1: determine the set of target files.
    if config.input_path.is_file():
        files = [config.input_path]
    else:
        files = discover_heic_files(config.input_path, config.recursive)

    # Per-file options derived from the top-level configuration.
    options = ConversionOptions(
        quality=config.quality,
        keep_metadata=config.keep_metadata,
        overwrite=config.overwrite,
    )

    results: list[ConversionResult] = []

    # Step 2: convert each file independently.
    #
    # Loop invariant: at the start of each iteration, ``results`` contains
    # exactly one valid ConversionResult per already-processed file and none
    # for the unprocessed files.
    for src in files:
        dst = resolve_output_path(src, config)

        if dst.exists() and not config.overwrite:
            # Overwrite disabled and destination exists: skip and preserve the
            # existing file's contents (no conversion is attempted).
            results.append(
                ConversionResult(src=src, dst=dst, status=ResultStatus.SKIPPED)
            )
            continue

        try:
            results.append(convert_file(src, dst, options))
        except Exception as exc:
            # Failure isolation: record the failure and continue with the
            # remaining files. No (partial) file is produced by convert_file
            # for callers to clean up here.
            results.append(
                ConversionResult(
                    src=src,
                    dst=None,
                    status=ResultStatus.FAILED,
                    error_message=str(exc),
                )
            )

    # Step 3: aggregate. The result count matches the target file count.
    return ConversionSummary(results=results)
