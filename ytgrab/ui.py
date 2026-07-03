from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ytgrab.models import DownloadItem, DownloadStatus

COLUMN_TITLE, COLUMN_STATUS, COLUMN_PROGRESS, COLUMN_SPEED, COLUMN_ETA = range(5)
COLUMN_HEADERS = ["Title", "Status", "Progress", "Speed", "ETA"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YTGrab")
        self.resize(1000, 620)

        self._items: dict[str, DownloadItem] = {}
        self._rows: dict[str, int] = {}
        self.output_dir = os.path.join(os.path.expanduser("~"), "Downloads")

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

        output_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit(self.output_dir)
        self.output_dir_edit.setReadOnly(True)
        self.browse_button = QPushButton("Choose output folder…")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(self.browse_button)
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

    def _on_add_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        self.add_item(url)
        self.url_input.clear()

    def add_item(self, url: str, format_selector: str = "best") -> DownloadItem:
        item = DownloadItem(url=url, output_dir=self.output_dir, format_selector=format_selector)
        self._items[item.id] = item
        self._append_row(item)
        return item

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

        self.queue_table.setItem(row, COLUMN_SPEED, QTableWidgetItem(item.speed))
        self.queue_table.setItem(row, COLUMN_ETA, QTableWidgetItem(item.eta))

    def _row_for(self, item_id: str) -> int | None:
        return self._rows.get(item_id)
