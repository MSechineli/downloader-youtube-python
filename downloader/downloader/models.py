from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DownloadStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    DONE = auto()
    FAILED = auto()


@dataclass
class DownloadItem:
    url: str
    status: DownloadStatus = DownloadStatus.PENDING
    error_message: Optional[str] = None
