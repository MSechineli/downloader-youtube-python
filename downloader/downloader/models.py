from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DownloadStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    DONE = auto()
    FAILED = auto()


class OutputFormat(Enum):
    MP3 = "mp3"
    M4A = "m4a"
    MP4 = "mp4"
    WAV = "wav"
    OGG = "ogg"


@dataclass
class DownloadItem:
    url: str
    status: DownloadStatus = DownloadStatus.PENDING
    error_message: Optional[str] = None
    title: Optional[str] = None


@dataclass
class HistoryEntry:
    url: str
    title: str
    fmt: str       # OutputFormat.name  e.g. "MP3"
    status: str    # DownloadStatus.name  e.g. "DONE"
    timestamp: str # ISO 8601 UTC


@dataclass
class ConversionItem:
    input_path: str
    status: DownloadStatus = DownloadStatus.PENDING
    error_message: Optional[str] = None
