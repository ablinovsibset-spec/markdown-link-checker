"""Extraction of inline links and images from Markdown text.

The text is first "masked" so that links inside fenced code blocks, inline
code, and HTML comments are not picked up as real links. Masking preserves
line numbers (removed characters become spaces, removed lines become empty
lines) so that reported line numbers point at the original source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Link", "extract_links"]


@dataclass(frozen=True, slots=True)
class Link:
    """A single inline link/image occurrence with its source line (1-based)."""

    url: str
    line: int


# Inline code: `` `...` `` or `` ``...`` ``. Non-greedy, may span lines.
_INLINE_CODE_RE = re.compile(r"(`{1,2})[\s\S]*?\1")

# HTML comments: `<!-- ... -->`, may span multiple lines.
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")

# CommonMark inline link/image: optional `!`, then `[text](url)`. No space
# between `]` and `(` is allowed by the pattern (the `]` is immediately
# followed by `(`). The URL group may not contain whitespace or `)`. An
# optional title (` "title"` or `'title'`) after the URL is allowed and
# ignored.
_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\)")

# Opening fence of a fenced code block: 3+ backticks or tildies, optionally
# preceded by up to a tab/spaces (we just lstrip in code).
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")


def _mask(match: re.Match[str]) -> str:
    """Replace a match with spaces/newlines so line/column layout is preserved."""
    text = match.group(0)
    return "".join("\n" if c == "\n" else " " for c in text)


def _strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks (``` and ~~~), preserving line numbers."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    fence_char = ""
    for line in lines:
        stripped = line.lstrip(" \t")
        fence_match = _FENCE_OPEN_RE.match(stripped)
        if not in_fence:
            if fence_match:
                in_fence = True
                fence_char = fence_match.group(1)[0]
                out.append("")
            else:
                out.append(line)
        else:
            # A line starting with the same fence char (3+) closes the block.
            if fence_match and fence_match.group(1)[0] == fence_char:
                in_fence = False
                fence_char = ""
            out.append("")
    return "\n".join(out)


def _strip_inline_code(text: str) -> str:
    return _INLINE_CODE_RE.sub(_mask, text)


def _strip_html_comments(text: str) -> str:
    return _HTML_COMMENT_RE.sub(_mask, text)


def _mask_non_link_text(text: str) -> str:
    # Order: fenced blocks first (line-based), then inline code, then HTML
    # comments. This way backticks inside HTML comments are masked before the
    # comment is removed, and HTML-comment-like text inside inline code is
    # masked before the comment regex runs.
    text = _strip_fenced_blocks(text)
    text = _strip_inline_code(text)
    text = _strip_html_comments(text)
    return text


def extract_links(text: str) -> list[Link]:
    """Return all inline link/image occurrences in `text`, with source lines."""
    cleaned = _mask_non_link_text(text)
    links: list[Link] = []
    for m in _LINK_RE.finditer(cleaned):
        url = m.group(3)
        if not url:
            continue
        line = cleaned.count("\n", 0, m.start()) + 1
        links.append(Link(url=url, line=line))
    return links
