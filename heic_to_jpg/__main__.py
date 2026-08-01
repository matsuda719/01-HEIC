"""Module execution entry point.

Enables running the converter as a module::

    python -m heic_to_jpg ./photos --output ./out --quality 90 --recursive

Delegates to :func:`heic_to_jpg.cli.main` and exits with its return code.
"""

from __future__ import annotations

import sys

from heic_to_jpg.cli import main

if __name__ == "__main__":
    sys.exit(main())
