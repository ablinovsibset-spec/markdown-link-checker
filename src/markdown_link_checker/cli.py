"""CLI entry point — the single seam of the tool.

Usage: `python -m markdown_link_checker PATH`

Exit codes:
- 0: scan completed, no broken links.
- 1: scan completed, at least one broken link (or a file could not be read).
- 2: startup failure (wrong arguments, missing path, path is not a directory).
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

from .checker import Checker
from .extractor import Link, extract_links
from .reporter import BrokenRow, print_report
from .resolver import LinkKind, classify, resolve_local
from .walker import iter_markdown_files

__all__ = ["main"]


def _display_path(md_file: Path, root: Path) -> str:
    """Show `md_file` relative to the scanned `root` when possible."""
    try:
        return str(md_file.relative_to(root))
    except ValueError:
        return str(md_file)


def _broken(md_file: Path, root: Path, link: Link, status: str) -> BrokenRow:
    """Build a broken-link row for a link occurrence in `md_file`."""
    return BrokenRow(
        file=_display_path(md_file, root),
        line=link.line,
        url=link.url,
        status=status,
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)

    if len(args) != 1:
        print(
            "usage: python -m markdown_link_checker PATH",
            file=sys.stderr,
        )
        if args:
            print(f"error: expected exactly one argument, got {len(args)}", file=sys.stderr)
        else:
            print("error: missing required PATH argument", file=sys.stderr)
        return 2

    root = Path(args[0])
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    console = Console()
    broken_rows: list[BrokenRow] = []
    files_count = 0
    links_count = 0

    with Checker() as checker:
        for md_file in iter_markdown_files(root):
            files_count += 1
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                # A single unreadable file must not look like "all ok".
                console.print(
                    f"[red]error:[/red] could not read {md_file}: {exc}",
                    style=None,
                )
                broken_rows.append(
                    BrokenRow(
                        file=_display_path(md_file, root),
                        line=0,
                        url="",
                        status=f"read error: {exc.__class__.__name__}",
                    )
                )
                continue

            for link in extract_links(text):
                links_count += 1
                kind = classify(link.url)

                if kind is LinkKind.SKIP:
                    continue

                if kind is LinkKind.UNKNOWN_SCHEME:
                    broken_rows.append(_broken(md_file, root, link, "unknown scheme"))
                    continue

                if kind is LinkKind.HTTP:
                    ok, status_text = checker.check_http(link.url)
                    if not ok:
                        broken_rows.append(_broken(md_file, root, link, status_text))
                    continue

                # LinkKind.LOCAL
                resolved = resolve_local(link.url, md_file)
                if resolved is None:
                    broken_rows.append(_broken(md_file, root, link, "malformed local URL"))
                    continue
                if not checker.check_local(resolved):
                    broken_rows.append(_broken(md_file, root, link, "not found"))

    print_report(console, files_count, links_count, broken_rows)
    return 1 if broken_rows else 0
