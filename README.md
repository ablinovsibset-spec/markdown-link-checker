# markdown-link-checker

A small CLI utility that scans a directory tree for `*.md` files, extracts
inline links and images, checks local paths against the filesystem and
HTTP(S) URLs against the network, and prints a colored report of broken
links.

## Install (local, editable)

```bash
python3 -m pip install -e .
```

## Usage

```bash
python3 -m markdown_link_checker PATH
```

`PATH` is a required positional argument: the directory to scan recursively.

### Exit codes

- `0` — scan completed, no broken links (includes the case of zero `.md` files).
- `1` — scan completed, at least one broken link found.
- `2` — startup failure: wrong arguments, missing path, path is a file or not a directory.

### What is checked

- Inline links `[text](url)` and images `![alt](url)` (CommonMark inline syntax,
  no space between `]` and `(`).
- Local paths: relative (resolved against the `.md` file's directory),
  absolute (`/foo` resolved against the process cwd), and `file://` URLs.
  Anchor fragments and query strings are stripped before the FS check;
  percent-encoding is decoded.
- HTTP(S) URLs and protocol-relative `//host/path` (treated as `https://`).
- `mailto:`, `tel:`, `data:` are skipped (not errors). Unknown schemes
  (`htps:`, `javascript:`, `ftp:`) are reported as broken.

### What is not checked

- Reference-style links, autolinks, bare URLs, HTML `<a href>` / `<img src>`.
- Anchor existence (a `#heading` is ignored).
- Links inside fenced code blocks, inline code, and HTML comments.

### HTTP behavior

- HEAD first; GET fallback on 405 / 403 / 501.
- Redirects are followed; success is a final 2xx.
- Final 401 and 403 are treated as "available but closed" (success).
- 429 / 5xx / timeout / network error: up to 2 retries, then broken.
- 10 second per-request timeout, User-Agent `markdown-link-checker/0.1`,
  TLS verification on, requests strictly sequential, one check per unique URL.
