import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from downloader.models import DownloadItem, DownloadStatus, HistoryEntry, OutputFormat

_DEFAULT_PATH = Path.home() / ".yt_downloader" / "history.json"
MAX_ENTRIES = 500


class HistoryService:
    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else _DEFAULT_PATH

    def load(self) -> List[HistoryEntry]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return [HistoryEntry(**e) for e in data]
        except Exception:
            return []

    def record(self, item: DownloadItem, output_format: OutputFormat) -> None:
        entry = HistoryEntry(
            url=item.url,
            title=item.title or item.url,
            fmt=output_format.name,
            status=item.status.name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        entries = self.load()
        # Avoid duplicate entries for the same URL+format combo in the same session
        entries = [e for e in entries if not (e.url == entry.url and e.fmt == entry.fmt
                                              and e.timestamp[:16] == entry.timestamp[:16])]
        entries.insert(0, entry)
        entries = entries[:MAX_ENTRIES]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
