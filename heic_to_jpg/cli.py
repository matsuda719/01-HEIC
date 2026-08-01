"""CLI layer: argument parsing and program entry point.

This module implements the command-line interface described in ``design.md``
("Components and Interfaces / コンポーネント 1: CLI"):

    - :func:`parse_args` — parse argv into a validated :class:`ConversionConfig`.
    - :func:`main`        — entry point returning a process exit code.

Exit codes (see requirements.md "Exit_Code"):
    - ``0`` — all files succeeded (or zero target files).
    - ``1`` — partial failure (one or more files failed).
    - ``2`` — argument error (invalid input path, out-of-range/non-integer
      quality, etc.). Emitted by ``argparse`` via ``parser.error``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from heic_to_jpg.models import ConversionConfig, ResultStatus
from heic_to_jpg.orchestrator import run

# Default JPEG quality when ``--quality`` is not supplied.
_DEFAULT_QUALITY = 90

# Inclusive valid bounds for JPEG quality.
_QUALITY_MIN = 1
_QUALITY_MAX = 100

_PROG = "heic_to_jpg"


def _quality_type(value: str) -> int:
    """argparse ``type`` for ``--quality``.

    Ensures the value is an integer within ``1..100`` inclusive. Raising
    :class:`argparse.ArgumentTypeError` causes argparse to exit with code 2.

    Args:
        value: Raw string from the command line.

    Returns:
        The parsed integer quality.

    Raises:
        argparse.ArgumentTypeError: When ``value`` is not an integer or is out
            of the inclusive range 1..100.
    """
    try:
        quality = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"quality must be an integer, got {value!r}"
        )

    if quality < _QUALITY_MIN or quality > _QUALITY_MAX:
        raise argparse.ArgumentTypeError(
            f"quality must be in range {_QUALITY_MIN}..{_QUALITY_MAX} "
            f"inclusive, got {quality}"
        )

    return quality


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="Convert HEIC/HEIF images to JPG.",
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Input HEIC/HEIF file or a directory containing them.",
    )
    parser.add_argument(
        "--output",
        dest="output_dir",
        type=Path,
        default=None,
        help=(
            "Output directory. When omitted, JPGs are written next to their "
            "input files."
        ),
    )
    parser.add_argument(
        "--quality",
        type=_quality_type,
        default=_DEFAULT_QUALITY,
        help=(
            f"JPEG quality, an integer in {_QUALITY_MIN}..{_QUALITY_MAX} "
            f"(default: {_DEFAULT_QUALITY})."
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories when the input is a directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JPG files (default: skip existing).",
    )
    parser.add_argument(
        "--keep-metadata",
        dest="keep_metadata",
        action="store_true",
        help="Preserve EXIF metadata in the output JPG.",
    )
    return parser


def parse_args(argv: list[str]) -> ConversionConfig:
    """Parse command-line arguments into a validated :class:`ConversionConfig`.

    Args:
        argv: Argument list (excluding the program name).

    Returns:
        A :class:`ConversionConfig` built from the parsed arguments.

    Raises:
        SystemExit: With code ``2`` when arguments are invalid — including a
            non-existent input path or an out-of-range/non-integer
            ``--quality`` (raised via :meth:`argparse.ArgumentParser.error`).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Validate that the input path exists; otherwise this is an argument error.
    if not args.input_path.exists():
        parser.error(f"input path does not exist: {args.input_path}")

    return ConversionConfig(
        input_path=args.input_path,
        output_dir=args.output_dir,
        quality=args.quality,
        recursive=args.recursive,
        overwrite=args.overwrite,
        keep_metadata=args.keep_metadata,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Parses arguments, runs the conversion workflow, prints a summary to stdout,
    and returns a process exit code.

    Args:
        argv: Optional argument list (excluding the program name). When
            ``None``, ``sys.argv[1:]`` is used.

    Returns:
        Exit code: ``0`` for all-success (or zero target files), ``1`` for
        partial failure. An argument error surfaces as ``SystemExit(2)`` from
        :func:`parse_args`.
    """
    if argv is None:
        argv = sys.argv[1:]

    # Argument errors raise SystemExit(2) from argparse; let that propagate.
    config = parse_args(argv)

    summary = run(config)

    total = len(summary.results)
    if total == 0:
        # No target files found: warn and succeed (exit code 0).
        print("warning: no HEIC/HEIF files found to convert.")
        return 0

    # Summary line with the three counts.
    print(
        f"succeeded: {summary.succeeded}, "
        f"skipped: {summary.skipped}, "
        f"failed: {summary.failed}"
    )

    # Report each failed file's identifying info and error message.
    if summary.failed > 0:
        print("failures:")
        for result in summary.results:
            if result.status is ResultStatus.FAILED:
                print(f"  {result.src}: {result.error_message}")

    return summary.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
