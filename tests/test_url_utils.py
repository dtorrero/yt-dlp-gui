import pytest

from yt_dlp_gui.url_utils import extract_urls, is_http_url, normalize_url


@pytest.mark.parametrize(
    "text, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]),
        ("https://youtu.be/abc123", ["https://youtu.be/abc123"]),
        # Firefox text/x-moz-url: URL then title
        (
            "https://youtu.be/abc123\nNever Gonna Give You Up",
            ["https://youtu.be/abc123"],
        ),
        # text/uri-list with several entries
        (
            "https://example.com/one\nhttps://example.com/two",
            ["https://example.com/one", "https://example.com/two"],
        ),
        # duplicated URLs are collapsed
        (
            "https://example.com/v https://example.com/v",
            ["https://example.com/v"],
        ),
        # trailing sentence punctuation is removed
        ("See (https://example.com/video).", ["https://example.com/video"]),
        # balanced parentheses inside a URL are preserved
        (
            "https://en.wikipedia.org/wiki/Foo_(bar)",
            ["https://en.wikipedia.org/wiki/Foo_(bar)"],
        ),
        # non-http schemes and plain text are ignored
        ("ftp://example.com/file", []),
        ("just some words", []),
        ("", []),
    ],
)
def test_extract_urls(text, expected):
    assert extract_urls(text) == expected


def test_extract_urls_keeps_order_and_case():
    urls = extract_urls("HTTPS://Example.com/Video and https://example.com/Other")
    assert urls == ["HTTPS://Example.com/Video", "https://example.com/Other"]


def test_normalize_url_strips_whitespace_and_punctuation():
    assert normalize_url("  https://example.com/v,  ") == "https://example.com/v"


@pytest.mark.parametrize(
    "url, valid",
    [
        ("https://example.com", True),
        ("http://example.com/a?b=c", True),
        ("ftp://example.com", False),
        ("https://", False),
        ("not-a-url", False),
    ],
)
def test_is_http_url(url, valid):
    assert is_http_url(url) is valid
