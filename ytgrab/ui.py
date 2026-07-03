from __future__ import annotations

import functools
import os

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ytgrab.models import DownloadItem, DownloadStatus
from ytgrab.presets import PRESET_CUSTOM, PRESET_LABELS, FormatSpec, resolve_format
from ytgrab.workers import DownloadWorker, PlaylistProbeWorker

(
    COLUMN_TITLE,
    COLUMN_STATUS,
    COLUMN_PROGRESS,
    COLUMN_SPEED,
    COLUMN_ETA,
    COLUMN_ACTIONS,
) = range(6)
COLUMN_HEADERS = ["Title", "Status", "Progress", "Speed", "ETA", "Actions"]

DEFAULT_PARALLEL_DOWNLOADS = 3

# Statuses that mean a worker is no longer running for that item.
TERMINAL_STATUSES = {DownloadStatus.DONE, DownloadStatus.ERROR, DownloadStatus.CANCELED}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YTGrab")
        self.resize(1000, 620)

        self._items: dict[str, DownloadItem] = {}
        self._rows: dict[str, int] = {}
        self._workers: dict[str, DownloadWorker] = {}
        self._progress_bars: dict[str, QProgressBar] = {}
        self._cancel_buttons: dict[str, QPushButton] = {}
        self.output_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(DEFAULT_PARALLEL_DOWNLOADS)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        input_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a video or playlist URL…")
        self.url_input.returnPressed.connect(self._on_add_clicked)
        self.add_button = QPushButton("Add to queue")
        self.add_button.clicked.connect(self._on_add_clicked)
        input_row.addWidget(self.url_input)
        input_row.addWidget(self.add_button)
        layout.addLayout(input_row)

        format_row = QHBoxLayout()
        self.format_combo = QComboBox()
        for preset_key, label in PRESET_LABELS:
            self.format_combo.addItem(label, preset_key)
        self.format_combo.currentIndexChanged.connect(self._on_format_preset_changed)
        self.custom_format_edit = QLineEdit()
        self.custom_format_edit.setPlaceholderText(
            "e.g. bv*[height<=720]+ba/b[height<=720]"
        )
        self.custom_format_edit.setEnabled(False)
        format_row.addWidget(self.format_combo)
        format_row.addWidget(self.custom_format_edit)
        layout.addLayout(format_row)

        output_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit(self.output_dir)
        self.output_dir_edit.setReadOnly(True)
        self.browse_button = QPushButton("Choose output folder…")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(self.browse_button)

        output_row.addWidget(QLabel("Parallel downloads:"))
        self.parallel_spinbox = QSpinBox()
        self.parallel_spinbox.setRange(1, 10)
        self.parallel_spinbox.setValue(DEFAULT_PARALLEL_DOWNLOADS)
        self.parallel_spinbox.valueChanged.connect(self.thread_pool.setMaxThreadCount)
        output_row.addWidget(self.parallel_spinbox)

        layout.addLayout(output_row)

        self.queue_table = QTableWidget(0, len(COLUMN_HEADERS))
        self.queue_table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.queue_table.horizontalHeader().setSectionResizeMode(
            COLUMN_TITLE, QHeaderView.Stretch
        )
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.queue_table)

    def _on_browse_clicked(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_dir)
        if chosen:
            self.output_dir = chosen
            self.output_dir_edit.setText(chosen)

    def _on_format_preset_changed(self, _index: int) -> None:
        preset_key = self.format_combo.currentData()
        self.custom_format_edit.setEnabled(preset_key == PRESET_CUSTOM)

    def _current_format_spec(self) -> FormatSpec:
        preset_key = self.format_combo.currentData()
        return resolve_format(preset_key, self.custom_format_edit.text())

    def _on_add_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        self.add_item(url, self._current_format_spec())
        self.url_input.clear()

    def add_item(self, url: str, format_spec: FormatSpec | None = None) -> DownloadItem:
        format_spec = format_spec or resolve_format(PRESET_LABELS[0][0])
        item = DownloadItem(
            url=url,
            output_dir=self.output_dir,
            format_selector=format_spec.format_selector,
            postprocessors=format_spec.postprocessors,
            merge_output_format=format_spec.merge_output_format,
            status=DownloadStatus.FETCHING,
        )
        self._items[item.id] = item
        self._append_row(item)
        self._probe_url(item)
        return item

    def _probe_url(self, item: DownloadItem) -> None:
        probe = PlaylistProbeWorker(item.id, item.url)
        probe.signals.resolved.connect(self._on_probe_resolved)
        probe.signals.error.connect(self._on_probe_error)
        self.thread_pool.start(probe)

    def _on_probe_error(self, item_id: str, message: str) -> None:
        self._on_error(item_id, message)
        self._on_status_changed(item_id, DownloadStatus.ERROR)

    def _on_probe_resolved(self, item_id: str, info: dict) -> None:
        item = self._items.get(item_id)
        if item is None:
            return

        entries = info.get("entries")
        if info.get("_type") == "playlist" and entries:
            self._expand_playlist(item, entries)
            return

        canonical_url = info.get("webpage_url") or item.url
        item.url = canonical_url
        title = info.get("title")
        if title:
            item.title = title
            row = self._rows[item_id]
            self.queue_table.item(row, COLUMN_TITLE).setText(item.display_title())
        self._start_download(item)

    def _expand_playlist(self, placeholder: DownloadItem, entries: list[dict]) -> None:
        format_spec = FormatSpec(
            placeholder.format_selector,
            placeholder.postprocessors,
            placeholder.merge_output_format,
        )
        output_dir = placeholder.output_dir
        self._remove_row(placeholder.id)

        for entry in entries:
            if not entry:
                continue
            entry_url = entry.get("url") or entry.get("webpage_url")
            if not entry_url:
                continue
            child = DownloadItem(
                url=entry_url,
                output_dir=output_dir,
                format_selector=format_spec.format_selector,
                postprocessors=format_spec.postprocessors,
                merge_output_format=format_spec.merge_output_format,
            )
            if entry.get("title"):
                child.title = entry["title"]
            self._items[child.id] = child
            self._append_row(child)
            self._start_download(child)

    def _remove_row(self, item_id: str) -> None:
        row = self._rows.pop(item_id, None)
        if row is None:
            return
        self.queue_table.removeRow(row)
        self._progress_bars.pop(item_id, None)
        self._cancel_buttons.pop(item_id, None)
        self._items.pop(item_id, None)
        self._workers.pop(item_id, None)
        for other_id, other_row in self._rows.items():
            if other_row > row:
                self._rows[other_id] = other_row - 1

    def _append_row(self, item: DownloadItem) -> None:
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        self._rows[item.id] = row

        self.queue_table.setItem(row, COLUMN_TITLE, QTableWidgetItem(item.display_title()))
        self.queue_table.setItem(row, COLUMN_STATUS, QTableWidgetItem(item.status.value))

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(item.progress))
        self.queue_table.setCellWidget(row, COLUMN_PROGRESS, progress_bar)
        self._progress_bars[item.id] = progress_bar

        self.queue_table.setItem(row, COLUMN_SPEED, QTableWidgetItem(item.speed))
        self.queue_table.setItem(row, COLUMN_ETA, QTableWidgetItem(item.eta))

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(functools.partial(self._on_cancel_clicked, item.id))
        self.queue_table.setCellWidget(row, COLUMN_ACTIONS, cancel_button)
        self._cancel_buttons[item.id] = cancel_button

    def _start_download(self, item: DownloadItem) -> None:
        worker = DownloadWorker(item)
        worker.signals.title_known.connect(self._on_title_known)
        worker.signals.status_changed.connect(self._on_status_changed)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(self._on_worker_finished)
        self._workers[item.id] = worker
        self.thread_pool.start(worker)

    def _on_cancel_clicked(self, item_id: str) -> None:
        worker = self._workers.get(item_id)
        if worker is not None:
            worker.cancel()

    def _on_title_known(self, item_id: str, title: str) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        item.title = title
        row = self._rows[item_id]
        self.queue_table.item(row, COLUMN_TITLE).setText(item.display_title())

    def _on_status_changed(self, item_id: str, status: DownloadStatus) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        item.status = status
        row = self._rows[item_id]
        self.queue_table.item(row, COLUMN_STATUS).setText(status.value)
        if status in TERMINAL_STATUSES:
            button = self._cancel_buttons.get(item_id)
            if button is not None:
                button.setEnabled(False)

    def _on_progress(self, item_id: str, percent: float, speed: str, eta: str) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        item.progress = percent
        item.speed = speed
        item.eta = eta
        row = self._rows[item_id]
        self._progress_bars[item_id].setValue(int(percent))
        self.queue_table.item(row, COLUMN_SPEED).setText(speed)
        self.queue_table.item(row, COLUMN_ETA).setText(eta)

    def _on_error(self, item_id: str, message: str) -> None:
        item = self._items.get(item_id)
        if item is None:
            return
        item.error = message
        row = self._rows[item_id]
        status_item = self.queue_table.item(row, COLUMN_STATUS)
        status_item.setToolTip(message)

    def _on_worker_finished(self, item_id: str) -> None:
        self._workers.pop(item_id, None)
