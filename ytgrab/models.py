from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class DownloadStatus(str, Enum):
    QUEUED = "Queued"
    FETCHING = "Fetching info"
    DOWNLOADING = "Downloading"
    DONE = "Done"
    ERROR = "Error"
    CANCELED = "Canceled"


@dataclass
class DownloadItem:
    url: str
    output_dir: str
    format_selector: str = "best"
    postprocessors: list[dict] = field(default_factory=list)
    merge_output_format: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    error: str = ""

    def display_title(self) -> str:
        return self.title or self.url
