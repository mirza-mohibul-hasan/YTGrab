from __future__ import annotations

import os
import threading
import traceback

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, Signal

from ytgrab.models import DownloadItem, DownloadStatus


class DownloadCanceled(Exception):
    """Raised from a progress hook to abort an in-flight yt-dlp download."""


def format_speed(bytes_per_sec: float | None) -> str:
    if not bytes_per_sec:
        return ""
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.1f}{unit}"
        bytes_per_sec /= 1024
    return f"{bytes_per_sec:.1f}TB/s"


def format_eta(seconds: float | None) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def format_bytes(num_bytes: float | None) -> str:
    if not num_bytes:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


class WorkerSignals(QObject):
    title_known = Signal(str, str)
    status_changed = Signal(str, DownloadStatus)
    progress = Signal(str, float, str, str)  # item_id, percent, speed, eta
    error = Signal(str, str)
    finished = Signal(str)


class ProbeSignals(QObject):
    resolved = Signal(str, dict)  # item_id, yt-dlp info dict
    error = Signal(str, str)


class PlaylistProbeWorker(QRunnable):
    """Resolves a URL to either a single video or a playlist's entries.

    Uses extract_flat so probing a large playlist stays cheap: entries come
    back with id/title/url but without per-video format data.
    """

    def __init__(self, item_id: str, url: str) -> None:
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.signals = ProbeSignals()

    def run(self) -> None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "noplaylist": False,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            self.signals.resolved.emit(self.item_id, info or {})
        except Exception as exc:  # noqa: BLE001 - surface any resolution failure to the UI
            self.signals.error.emit(self.item_id, str(exc))


class FormatListSignals(QObject):
    resolved = Signal(list)
    error = Signal(str)


class FormatListWorker(QRunnable):
    """Fetches the real list of formats yt-dlp reports for a URL."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = FormatListSignals()

    def run(self) -> None:
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            formats = (info or {}).get("formats") or []
            self.signals.resolved.emit(formats)
        except Exception as exc:  # noqa: BLE001 - surface any resolution failure to the UI
            self.signals.error.emit(str(exc))


class DownloadWorker(QRunnable):
    def __init__(self, item: DownloadItem) -> None:
        super().__init__()
        self.item = item
        self.signals = WorkerSignals()
        self._cancel_event = threading.Event()
        self._title_emitted = False

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_canceled(self) -> bool:
        return self._cancel_event.is_set()

    def _build_ydl_opts(self) -> dict:
        opts: dict = {
            "format": self.item.format_selector,
            "outtmpl": os.path.join(self.item.output_dir, "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [self._progress_hook],
        }
        if self.item.postprocessors:
            opts["postprocessors"] = self.item.postprocessors
        if self.item.merge_output_format:
            opts["merge_output_format"] = self.item.merge_output_format
        return opts

    def _progress_hook(self, d: dict) -> None:
        if self._cancel_event.is_set():
            raise DownloadCanceled("Download canceled by user")

        info = d.get("info_dict") or {}
        title = info.get("title")
        if title and not self._title_emitted:
            self._title_emitted = True
            self.signals.title_known.emit(self.item.id, title)

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100) if total else 0.0
            speed = format_speed(d.get("speed"))
            eta = format_eta(d.get("eta"))
            self.signals.progress.emit(self.item.id, percent, speed, eta)
        elif status == "finished":
            self.signals.progress.emit(self.item.id, 100.0, "", "")

    def run(self) -> None:
        self.signals.status_changed.emit(self.item.id, DownloadStatus.DOWNLOADING)
        try:
            with yt_dlp.YoutubeDL(self._build_ydl_opts()) as ydl:
                info = ydl.extract_info(self.item.url, download=True)
            title = (info or {}).get("title")
            if title:
                self.signals.title_known.emit(self.item.id, title)
            self.signals.status_changed.emit(self.item.id, DownloadStatus.DONE)
            self.signals.finished.emit(self.item.id)
        except DownloadCanceled:
            self.signals.status_changed.emit(self.item.id, DownloadStatus.CANCELED)
            self.signals.finished.emit(self.item.id)
        except Exception as exc:  # noqa: BLE001 - surface any yt-dlp/network failure to the UI
            message = str(exc) or traceback.format_exc(limit=1)
            self.signals.error.emit(self.item.id, message)
            self.signals.status_changed.emit(self.item.id, DownloadStatus.ERROR)
            self.signals.finished.emit(self.item.id)
