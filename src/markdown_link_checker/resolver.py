"""Classify a link URL and resolve local targets to filesystem paths.

Schemes:
- `http` / `https` -> network check.
- protocol-relative `//host/path` -> normalized to `https://host/path`, network.
- `file://` -> absolute filesystem path.
- `mailto` / `tel` / `data` -> skipped (not an error).
- anything else with a scheme -> broken (unknown scheme).
- no scheme -> local path (relative to the `.md` file's directory, or
  absolute `/path` resolved against the process cwd).
"""

from __future__ import annotations

import enum
import re
import urllib.parse
from pathlib import Path

__all__ = ["LinkKind", "classify", "normalize_http_url", "resolve_local"]


class LinkKind(enum.Enum):
    LOCAL = "local"
    HTTP = "http"
    SKIP = "skip"
    UNKNOWN_SCHEME = "unknown_scheme"


_HTTP_SCHEMES: frozenset[str] = frozenset({"http", "https"})
_SKIP_SCHEMES: frozenset[str] = frozenset({"mailto", "tel", "data"})


def classify(url: str) -> LinkKind:
    """Decide how a URL should be handled."""
    if url.startswith("//"):
        return LinkKind.HTTP
    # A scheme is the part before the first `:` and must be a non-empty
    # sequence of letters/digits/+/-/. per RFC 3986. We detect it for both
    # `scheme://...` and `scheme:...` forms (mailto:, tel:, data:, file:...).
    scheme = _scheme_of(url)
    if scheme is None:
        return LinkKind.LOCAL
    scheme = scheme.lower()
    if scheme in _HTTP_SCHEMES:
        return LinkKind.HTTP
    if scheme == "file":
        return LinkKind.LOCAL
    if scheme in _SKIP_SCHEMES:
        return LinkKind.SKIP
    return LinkKind.UNKNOWN_SCHEME


_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


def _scheme_of(url: str) -> str | None:
    """Return the scheme of `url` (without the trailing `:`), or None."""
    match = _SCHEME_RE.match(url)
    if not match:
        return None
    return match.group(0)[:-1]


def normalize_http_url(url: str) -> str:
    """Normalize an HTTP URL for caching and requesting.

    - protocol-relative `//host/path` -> `https://host/path`
    - fragment stripped (anchors are not checked)
    """
    if url.startswith("//"):
        url = "https:" + url
    parts = urllib.parse.urlsplit(url)
    parts = parts._replace(fragment="")
    return urllib.parse.urlunsplit(parts)


def resolve_local(url: str, md_file: Path) -> Path | None:
    """Resolve a local URL to a filesystem path.

    `file://` URLs use their path component directly. Other local URLs
    (relative or `/`-absolute) have their anchor and query stripped and
    percent-encoding decoded before resolution:

    - `/foo/bar.md` -> `Path.cwd() / "foo/bar.md"`
    - `./bar.md` or `bar.md` -> `md_file.parent / "bar.md"`

    A URL that is empty after stripping anchor/query refers to the file
    itself (e.g. `#heading`); the file we are scanning exists, so we return
    `md_file` as a valid target.

    Returns None if the URL is malformed (e.g. a `file://` URL with no path).
    """
    if url.startswith("file://"):
        parts = urllib.parse.urlsplit(url)
        if not parts.path:
            return None
        return Path(urllib.parse.unquote(parts.path))

    # Strip fragment and query for local paths.
    target = url
    if "#" in target:
        target = target.split("#", 1)[0]
    if "?" in target:
        target = target.split("?", 1)[0]
    target = urllib.parse.unquote(target)

    if not target:
        # Pure anchor like `#heading` -> the file itself, which exists.
        return md_file

    if target.startswith("/"):
        # `/foo.md` resolves against cwd, not the filesystem root.
        return Path.cwd() / target.lstrip("/")

    return md_file.parent / target
