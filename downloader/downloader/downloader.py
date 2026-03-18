import threading
from pathlib import Path
from typing import Callable, List

from downloader.models import DownloadItem, DownloadStatus


class DownloadService:
    def __init__(self, ydl_factory=None):
        if ydl_factory is None:
            import yt_dlp
            ydl_factory = yt_dlp.YoutubeDL
        self._ydl_factory = ydl_factory

    def download_all(
        self,
        items: List[DownloadItem],
        out_dir: str,
        callback: Callable[[DownloadItem], None],
        playlist: bool = False,
    ) -> None:
        """Start downloading all items in a background thread."""
        thread = threading.Thread(
            target=self._run,
            args=(items, out_dir, callback, playlist),
            daemon=True,
        )
        thread.start()

    def _build_opts(self, out_dir: str, playlist: bool = False) -> dict:
        return {
            "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(Path(out_dir) / "%(title)s.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "ignoreerrors": False,
            "noplaylist": not playlist,
            "extractor_args": {"youtube": {"skip": ["dash", "hls"]}},
        }

    def _run(
        self,
        items: List[DownloadItem],
        out_dir: str,
        callback: Callable[[DownloadItem], None],
        playlist: bool = False,
    ) -> None:
        for item in items:
            if item.status == DownloadStatus.FAILED:
                callback(item)
                continue

            item.status = DownloadStatus.IN_PROGRESS
            callback(item)

            try:
                with self._ydl_factory(self._build_opts(out_dir, playlist)) as ydl:
                    ydl.download([item.url])
                item.status = DownloadStatus.DONE
            except Exception as e:
                item.status = DownloadStatus.FAILED
                item.error_message = str(e)

            callback(item)
