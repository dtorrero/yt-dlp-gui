"""Turn pasted or dropped text into yt-dlp URLs.

Browsers put different flavours of data on the clipboard / drag payload:

* ``text/plain``  -- usually just the URL, sometimes ``URL\\nTitle``
* ``text/uri-list`` -- newline separated list of URIs
* ``text/x-moz-url`` -- Firefox: ``URL\\nTitle``

This module extracts every ``http(s)`` URL from any of those and ignores the
rest (titles, notes, arbitrary text).
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# Deliberately conservative: stop at whitespace, quotes and angle brackets
# (which are never valid in an unencoded URL).
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)

_CLOSERS = {")": "(", "]": "[", "}": "{"}
_TRAILING_PUNCTUATION = ".,;:!?'\""


def _strip_trailing_punctuation(url: str) -> str:
    """Remove sentence punctuation that ended up glued to the URL."""
    while url:
        last = url[-1]
        if last in _TRAILING_PUNCTUATION:
            url = url[:-1]
        elif last in _CLOSERS and url.count(last) > url.count(_CLOSERS[last]):
            url = url[:-1]
        else:
            break
    return url


def normalize_url(raw: str) -> str:
    """Strip whitespace and trailing punctuation from a single URL."""
    return _strip_trailing_punctuation(raw.strip())


def is_http_url(url: str) -> bool:
    """Return True when *url* is an absolute http(s) URL with a host."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme.lower() in {"http", "https"} and bool(parts.netloc)


def extract_urls(text: str | None) -> list[str]:
    """Extract unique http(s) URLs from arbitrary pasted/dropped text."""
    urls: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        url = normalize_url(match.group(0))
        if is_http_url(url) and url not in urls:
            urls.append(url)
    return urls
