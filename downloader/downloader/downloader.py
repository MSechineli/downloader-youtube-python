import threading
from pathlib import Path
from typing import Callable, List, Optional

from downloader.models import DownloadItem, DownloadStatus, OutputFormat


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
        output_format: Optional[OutputFormat] = None,
    ) -> None:
        """Start downloading all items in a background thread."""
        thread = threading.Thread(
            target=self._run,
            args=(items, out_dir, callback, playlist, output_format),
            daemon=True,
        )
        thread.start()

    def _build_opts(
        self,
        out_dir: str,
        playlist: bool = False,
        output_format: Optional[OutputFormat] = None,
        item=None,
    ) -> dict:
        if output_format is None:
            output_format = OutputFormat.MP3

        def _title_hook(d):
            if item is not None and d.get("status") == "finished" and not item.title:
                item.title = d.get("info_dict", {}).get("title") or None

        base = {
            "outtmpl": str(Path(out_dir) / "%(title)s.%(ext)s"),
            "quiet": True,
            "ignoreerrors": False,
            "noplaylist": not playlist,
            "progress_hooks": [_title_hook],
        }

        if output_format == OutputFormat.MP4:
            base["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            base["merge_output_format"] = "mp4"
            base["postprocessors"] = []
        elif output_format == OutputFormat.M4A:
            base["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            base["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
        elif output_format == OutputFormat.WAV:
            base["format"] = "bestaudio/best"
            base["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}]
        elif output_format == OutputFormat.OGG:
            base["format"] = "bestaudio/best"
            base["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "vorbis"}]
        else:  # MP3 (default)
            base["format"] = "bestaudio/best"
            base["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]

        return base

    def _run(
        self,
        items: List[DownloadItem],
        out_dir: str,
        callback: Callable[[DownloadItem], None],
        playlist: bool = False,
        output_format: Optional[OutputFormat] = None,
    ) -> None:
        for item in items:
            if item.status == DownloadStatus.FAILED:
                callback(item)
                continue

            item.status = DownloadStatus.IN_PROGRESS
            callback(item)

            try:
                with self._ydl_factory(self._build_opts(out_dir, playlist, output_format, item)) as ydl:
                    ydl.download([item.url])
                item.status = DownloadStatus.DONE
            except Exception as e:
                item.status = DownloadStatus.FAILED
                item.error_message = str(e)

            callback(item)
