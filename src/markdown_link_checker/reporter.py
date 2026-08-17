"""Output: a one-line summary and, if needed, a colored table of broken links.

`rich` is used for both. A single `Console` is shared; rich automatically
disables colors when stdout is not a TTY (e.g. piped to a file or `cat`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

__all__ = ["BrokenRow", "print_report"]


@dataclass(frozen=True, slots=True)
class BrokenRow:
    file: str
    line: int
    url: str
    status: str


def print_report(
    console: Console,
    files: int,
    links: int,
    broken_rows: Sequence[BrokenRow],
) -> None:
    """Print the summary line, then the broken-links table if any."""
    broken = len(broken_rows)
    console.print(
        f"Checked [bold]{files}[/bold] files, "
        f"[bold]{links}[/bold] links, "
        f"[bold{'red' if broken else 'green'}]{broken}[/] broken"
    )

    if not broken:
        return

    table = Table(title="Broken links")
    table.add_column("File", overflow="fold")
    table.add_column("Line", justify="right")
    table.add_column("URL", overflow="fold")
    table.add_column("Status")
    for row in broken_rows:
        table.add_row(row.file, str(row.line), row.url, row.status)
    console.print(table)
