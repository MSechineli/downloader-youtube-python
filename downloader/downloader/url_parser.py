import re
from typing import List
from downloader.models import DownloadItem, DownloadStatus

_YOUTUBE_PATTERNS = [
    re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?.*v=[\w-]+"),
    re.compile(r"^https?://youtu\.be/[\w-]+"),
    re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/[\w-]+"),
]


def parse_urls(text: str) -> List[str]:
    return [token for token in text.split() if token]


def is_valid_youtube_url(url: str) -> bool:
    return any(p.match(url) for p in _YOUTUBE_PATTERNS)


def parse_urls_to_items(text: str, validate: bool = True) -> List[DownloadItem]:
    urls = parse_urls(text)
    items = []
    for url in urls:
        if validate and not is_valid_youtube_url(url):
            item = DownloadItem(
                url=url,
                status=DownloadStatus.FAILED,
                error_message=f"Invalid YouTube URL: {url}",
            )
        else:
            item = DownloadItem(url=url)
        items.append(item)
    return items
