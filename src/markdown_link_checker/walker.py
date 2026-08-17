"""Recursive discovery of `*.md` files in a directory tree.

Skips a fixed blacklist of directory names and never follows symlinked
directories (so the scan cannot loop).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

# Directory names that are never entered during the walk. These hold
# third-party READMEs and other noise that should not pollute the report.
BLACKLISTED_DIR_NAMES: frozenset[str] = frozenset(
    {".git", "node_modules", ".venv", "__pycache__"}
)


def iter_markdown_files(root: Path) -> Iterator[Path]:
    """Yield `*.md` files under `root`, depth-first, skipping blacklisted dirs.

    Symlinked directories are not followed (os.walk's default behavior with
    `followlinks=False`), which prevents infinite loops.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune blacklisted directories in place so os.walk does not descend
        # into them.
        dirnames[:] = [d for d in dirnames if d not in BLACKLISTED_DIR_NAMES]
        for name in filenames:
            if Path(name).suffix == ".md":
                yield Path(dirpath, name)
