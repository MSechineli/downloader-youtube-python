import pytest
from downloader.url_parser import parse_urls, is_valid_youtube_url, parse_urls_to_items
from downloader.models import DownloadStatus


# --- parse_urls ---

def test_parse_urls_splits_on_newline():
    text = "https://youtube.com/watch?v=a\nhttps://youtube.com/watch?v=b"
    assert parse_urls(text) == [
        "https://youtube.com/watch?v=a",
        "https://youtube.com/watch?v=b",
    ]


def test_parse_urls_splits_on_spaces():
    text = "https://youtu.be/a https://youtu.be/b"
    assert parse_urls(text) == ["https://youtu.be/a", "https://youtu.be/b"]


def test_parse_urls_drops_blank_lines():
    text = "https://youtu.be/a\n\n\nhttps://youtu.be/b\n"
    assert parse_urls(text) == ["https://youtu.be/a", "https://youtu.be/b"]


def test_parse_urls_empty_string():
    assert parse_urls("") == []


def test_parse_urls_whitespace_only():
    assert parse_urls("   \n\t  ") == []


# --- is_valid_youtube_url ---

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "http://youtube.com/watch?v=abc123",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/shorts/abc123",
])
def test_valid_youtube_urls(url):
    assert is_valid_youtube_url(url) is True


@pytest.mark.parametrize("url", [
    "https://vimeo.com/123456",
    "ftp://youtube.com/watch?v=abc",
    "not-a-url",
    "",
    "https://youtube.com/",
    "https://youtube.com/playlist?list=abc",
])
def test_invalid_youtube_urls(url):
    assert is_valid_youtube_url(url) is False


# --- parse_urls_to_items ---

def test_parse_urls_to_items_returns_download_items():
    text = "https://youtube.com/watch?v=abc\nhttps://youtu.be/xyz"
    items = parse_urls_to_items(text)
    assert len(items) == 2
    assert items[0].url == "https://youtube.com/watch?v=abc"
    assert items[0].status == DownloadStatus.PENDING


def test_parse_urls_to_items_validate_marks_invalid_as_failed():
    text = "https://youtube.com/watch?v=abc\nhttps://vimeo.com/123"
    items = parse_urls_to_items(text, validate=True)
    assert items[0].status == DownloadStatus.PENDING
    assert items[1].status == DownloadStatus.FAILED
    assert items[1].error_message is not None


def test_parse_urls_to_items_no_validate_keeps_all_pending():
    text = "https://youtube.com/watch?v=abc\nhttps://vimeo.com/123"
    items = parse_urls_to_items(text, validate=False)
    assert all(item.status == DownloadStatus.PENDING for item in items)


def test_parse_urls_to_items_empty_text():
    assert parse_urls_to_items("") == []
