"""Link checking: filesystem existence and HTTP HEAD/GET with caching.

A single `Checker` instance is used per run. HTTP requests are strictly
sequential (no concurrency), and each unique normalized URL is checked at
most once. The result is cached and reused for every later occurrence.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from .resolver import normalize_http_url

__all__ = ["Checker"]

# HTTP behavior constants (v1 has no flags; these are fixed).
TIMEOUT: float = 10.0
USER_AGENT: str = "markdown-link-checker/0.1"
MAX_RETRIES: int = 2  # 2 retries after the first attempt -> 3 attempts total.
GET_FALLBACK_STATUSES: frozenset[int] = frozenset({405, 403, 501})


class Checker:
    """Caches FS and HTTP checks by resolved path / normalized URL."""

    def __init__(self) -> None:
        self._local_cache: dict[str, bool] = {}
        self._http_cache: dict[str, tuple[bool, str]] = {}
        self._client = httpx.Client(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            verify=True,
        )

    def __enter__(self) -> "Checker":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- local filesystem -------------------------------------------------

    def check_local(self, path: Path) -> bool:
        """Return True if `path` exists (as a file or a directory)."""
        key = str(path)
        cached = self._local_cache.get(key)
        if cached is not None:
            return cached
        ok = path.exists()
        self._local_cache[key] = ok
        return ok

    # -- HTTP --------------------------------------------------------------

    def check_http(self, url: str) -> tuple[bool, str]:
        """Return (ok, status_text) for an HTTP(S) URL, cached per URL."""
        normalized = normalize_http_url(url)
        cached = self._http_cache.get(normalized)
        if cached is not None:
            return cached

        result: tuple[bool, str] = (False, "unknown error")
        for _ in range(MAX_RETRIES + 1):
            ok, status_text, retryable = self._http_attempt(normalized)
            result = (ok, status_text)
            if ok or not retryable:
                break
        self._http_cache[normalized] = result
        return result

    def _request(
        self, method: str, url: str
    ) -> httpx.Response | tuple[bool, str, bool]:
        """Issue a request. On failure return a (ok, status, retryable) tuple."""
        try:
            return self._client.request(method, url)
        except httpx.TimeoutException:
            return (False, "timeout", True)
        except httpx.HTTPError:
            return (False, "network error", True)

    def _http_attempt(self, url: str) -> tuple[bool, str, bool]:
        """One HTTP attempt. Returns (ok, status_text, retryable)."""
        resp = self._request("HEAD", url)
        if isinstance(resp, tuple):
            return resp

        # Some servers reject HEAD with 405/403/501; fall back to GET.
        if resp.status_code in GET_FALLBACK_STATUSES:
            get_resp = self._request("GET", url)
            if isinstance(get_resp, tuple):
                return get_resp
            resp = get_resp

        status = resp.status_code
        reason = (resp.reason_phrase or "").strip()
        status_text = f"{status} {reason}".strip()

        if 200 <= status < 300:
            return (True, status_text, False)
        if status in (401, 403):
            # Closed but exists -> success.
            return (True, status_text, False)
        if status == 429 or 500 <= status < 600:
            return (False, status_text, True)
        return (False, status_text, False)
