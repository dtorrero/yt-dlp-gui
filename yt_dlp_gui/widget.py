"""The frameless, always-on-top widget window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .downloader import DownloadJob, DownloadManager, JobStatus
from .media_player import open_in_player
from .resources import app_icon, tinted_icon
from .settings import AppConfig
from .url_utils import extract_urls

ACCENT_COLOR = "#5b7cfa"

APP_STYLE = """
QWidget {
    color: #e5e7eb;
    font-size: 13px;
}
#card {
    background-color: #161821;
    border: 1px solid #2a2d3a;
    border-radius: 14px;
}
#card[dragActive="true"] {
    background-color: #1a1e2b;
    border: 1px solid #7c9eff;
}
#titlebar {
    background: transparent;
}
QLabel#title {
    font-weight: 600;
}
QLabel#sectionTitle {
    color: #aab1c5;
    font-size: 11px;
    font-weight: 600;
}
QLabel#jobTitle {
    font-weight: 600;
}
QLabel#muted {
    color: #8a90a2;
    font-size: 11px;
}
QLineEdit {
    background-color: #0f1117;
    border: 1px solid #2a2d3a;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #4c6ef5;
}
QLineEdit:focus {
    border-color: #5b7cfa;
}
QPushButton {
    background-color: #5b7cfa;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #6b8afd;
}
QPushButton:pressed {
    background-color: #4c6ef5;
}
QPushButton#secondary {
    background-color: #262a38;
    color: #e5e7eb;
}
QPushButton#secondary:hover {
    background-color: #303548;
}
QPushButton:disabled {
    background-color: #33374a;
    color: #8a90a2;
}
QToolButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 2px 6px;
    color: #aab1c5;
}
QToolButton:hover {
    background-color: #262a38;
    color: #e5e7eb;
}
QToolButton:checked {
    background-color: #2b3552;
    color: #8ea6ff;
}
QFrame#jobRow {
    background-color: #11131b;
    border: 1px solid #232634;
    border-radius: 10px;
}
QProgressBar {
    background-color: #0f1117;
    border: none;
    border-radius: 3px;
}
QProgressBar::chunk {
    background-color: #5b7cfa;
    border-radius: 3px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2f3446;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QCheckBox {
    spacing: 8px;
}
QComboBox, QSpinBox {
    background-color: #0f1117;
    border: 1px solid #2a2d3a;
    border-radius: 8px;
    padding: 5px 8px;
}
QDialog {
    background-color: #161821;
}
"""


class TitleBar(QWidget):
    """Draggable header with pin, settings, minimise-to-tray and close buttons."""

    def __init__(self, window: "WidgetWindow") -> None:
        super().__init__(window)
        self._window = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("titlebar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(18, 18))
        icon.setFixedSize(18, 18)
        title = QLabel("yt-dlp widget")
        title.setObjectName("title")
        title.setCursor(Qt.CursorShape.SizeAllCursor)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addStretch(1)

        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(window.settings_requested.emit)

        self.pin_button = QToolButton()
        self.pin_button.setText("📌")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(window.config.always_on_top)
        self.pin_button.setToolTip("Keep the widget on top")
        self.pin_button.toggled.connect(window.set_always_on_top)

        self.minimize_button = QToolButton()
        self.minimize_button.setText("–")
        self.minimize_button.setToolTip("Hide to the system tray")
        self.minimize_button.clicked.connect(window.hide_requested.emit)

        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("Hide to the system tray (quit from the tray menu)")
        self.close_button.clicked.connect(window.hide_requested.emit)

        for button in (
            self.settings_button,
            self.pin_button,
            self.minimize_button,
            self.close_button,
        ):
            layout.addWidget(button)

    # -- window dragging -------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class JobRow(QFrame):
    """One download in the queue: title, progress, speed/ETA and an action."""

    cancel_clicked = Signal(str)
    open_clicked = Signal(str)
    dismiss_clicked = Signal(str)
    play_clicked = Signal(str)

    def __init__(self, job: DownloadJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("jobRow")
        self._job = job
        self.setToolTip(job.url)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        self.title_label = QLabel()
        self.title_label.setObjectName("jobTitle")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.detail_label = QLabel()
        self.detail_label.setObjectName("muted")
        self.detail_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.progress)
        text_layout.addWidget(self.detail_label)
        layout.addLayout(text_layout, 1)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(4)

        self.play_button = QToolButton()
        self.play_button.setIcon(
            tinted_icon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
                ACCENT_COLOR,
            )
        )
        self.play_button.setIconSize(QSize(16, 16))
        self.play_button.setFixedSize(32, 30)
        self.play_button.setToolTip("Play the downloaded file")
        self.play_button.clicked.connect(self._on_play)

        self.folder_button = QToolButton()
        self.folder_button.setIcon(
            tinted_icon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
                ACCENT_COLOR,
            )
        )
        self.folder_button.setIconSize(QSize(16, 16))
        self.folder_button.setFixedSize(32, 30)
        self.folder_button.setToolTip("Open the containing folder")
        self.folder_button.clicked.connect(self._on_open)

        self.action_button = QPushButton()
        self.action_button.setObjectName("secondary")
        self.action_button.setFixedWidth(96)
        self.action_button.clicked.connect(self._on_action)

        actions_layout.addWidget(self.play_button)
        actions_layout.addWidget(self.folder_button)
        actions_layout.addWidget(self.action_button)
        layout.addWidget(actions, 0, Qt.AlignmentFlag.AlignTop)

        self.update_from(job)

    # -- signals ---------------------------------------------------------

    def _on_action(self) -> None:
        if self._job.status in (
            JobStatus.QUEUED,
            JobStatus.DOWNLOADING,
            JobStatus.PROCESSING,
        ):
            self.cancel_clicked.emit(self._job.id)
        else:
            self.dismiss_clicked.emit(self._job.id)

    def _on_play(self) -> None:
        self.play_clicked.emit(self._job.id)

    def _on_open(self) -> None:
        self.open_clicked.emit(self._job.id)

    # -- rendering -------------------------------------------------------

    def update_from(self, job: DownloadJob) -> None:
        self._job = job
        self.setToolTip(job.url)
        title_width = max(120, self.title_label.width() or 260)
        self.title_label.setText(
            self.title_label.fontMetrics().elidedText(
                job.display_title, Qt.TextElideMode.ElideRight, title_width
            )
        )
        self.title_label.setToolTip(job.display_title)
        self.detail_label.setStyleSheet("")
        self.action_button.setEnabled(True)

        status = job.status
        is_done = status == JobStatus.DONE
        self.action_button.setVisible(not is_done)
        self.play_button.setVisible(is_done)
        self.folder_button.setVisible(is_done)
        self.play_button.setEnabled(is_done and bool(job.output_path))

        if status == JobStatus.QUEUED:
            self.progress.setRange(0, 0)
            self._set_detail("Queued")
            self.action_button.setText("Cancel")
        elif status == JobStatus.DOWNLOADING:
            self.progress.setRange(0, 1000)
            percent = job.percent if job.percent is not None else 0.0
            self.progress.setValue(int(percent * 10))
            parts = [f"{percent:.1f}%"]
            if job.total_text:
                parts.append(f"of {job.total_text}")
            if job.speed_text:
                parts.append(job.speed_text)
            if job.eta_text:
                parts.append(f"ETA {job.eta_text}")
            self._set_detail("  ·  ".join(parts))
            self.action_button.setText("Cancel")
        elif status == JobStatus.PROCESSING:
            self.progress.setRange(0, 1000)
            self.progress.setValue(1000)
            self._set_detail("Processing (merging / converting)…")
            self.action_button.setText("Cancel")
        elif status == JobStatus.DONE:
            self.progress.setRange(0, 1000)
            self.progress.setValue(1000)
            detail = f"Saved to {job.output_path}" if job.output_path else "Saved"
            self._set_detail(detail)
        elif status == JobStatus.ERROR:
            self.progress.setRange(0, 1000)
            self.progress.setValue(0)
            self._set_detail(job.error or "Download failed.")
            self.detail_label.setStyleSheet("color: #ff8a8a;")
            self.action_button.setText("Dismiss")
        else:  # CANCELED
            self.progress.setRange(0, 1000)
            self.progress.setValue(0)
            self._set_detail("Canceled")
            self.action_button.setText("Dismiss")

    def _set_detail(self, text: str) -> None:
        self.detail_label.setText(
            self.detail_label.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, max(120, self.detail_label.width() or 300)
            )
        )
        self.detail_label.setToolTip(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-elide the labels for the final available width.
        self.update_from(self._job)


class WidgetWindow(QWidget):
    """Frameless widget: URL input, drop target, queue and tray-friendly hiding."""

    settings_requested = Signal()
    hide_requested = Signal()
    config_changed = Signal()

    def __init__(
        self,
        config: AppConfig,
        manager: DownloadManager,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.manager = manager
        self._settings = settings or QSettings()
        self._rows: dict[str, JobRow] = {}
        self._drag_active = False
        self._clipboard_connected = False
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.setInterval(0)
        self._height_timer.timeout.connect(self._apply_content_height)

        self.setWindowTitle("yt-dlp widget")
        self.setWindowIcon(app_icon())
        self.setFixedWidth(470)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(self._window_flags(config.always_on_top))
        self.setAcceptDrops(True)
        self.setStyleSheet(APP_STYLE)

        self._build_ui()
        self._connect_manager()
        self.set_clipboard_watch(config.clipboard_watch)
        self._restore_geometry()
        self._sync_height()

    # -- construction ----------------------------------------------------

    @staticmethod
    def _window_flags(always_on_top: bool) -> Qt.WindowType:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        return flags

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.header = TitleBar(self)
        layout.addWidget(self.header)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a video URL or drop a link here")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.returnPressed.connect(self._download_from_input)
        self.paste_button = QPushButton("Paste")
        self.paste_button.setObjectName("secondary")
        self.paste_button.setToolTip("Use the link currently in the clipboard")
        self.paste_button.clicked.connect(self._paste_from_clipboard)
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self._download_from_input)
        input_row.addWidget(self.url_edit, 1)
        input_row.addWidget(self.paste_button)
        input_row.addWidget(self.download_button)
        layout.addLayout(input_row)

        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        self.queue_box = QWidget()
        queue_outer = QVBoxLayout(self.queue_box)
        queue_outer.setContentsMargins(0, 2, 0, 0)
        queue_outer.setSpacing(6)

        queue_header = QHBoxLayout()
        queue_title = QLabel("Downloads")
        queue_title.setObjectName("sectionTitle")
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear finished")
        self.clear_button.clicked.connect(self._clear_finished)
        queue_header.addWidget(queue_title)
        queue_header.addStretch(1)
        queue_header.addWidget(self.clear_button)
        queue_outer.addLayout(queue_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(0)
        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(6)
        self.queue_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.queue_container)
        queue_outer.addWidget(self.scroll)

        layout.addWidget(self.queue_box)
        self.queue_box.hide()

    def _connect_manager(self) -> None:
        self.manager.job_added.connect(self._on_job_added)
        self.manager.job_changed.connect(self._on_job_changed)
        self.manager.job_finished.connect(self._on_job_finished)

    # -- queue rendering -------------------------------------------------

    def _on_job_added(self, job_id: str) -> None:
        job = self.manager.get(job_id)
        if job is None:
            return
        row = JobRow(job)
        row.cancel_clicked.connect(self._cancel_job)
        row.open_clicked.connect(self._open_job_folder)
        row.dismiss_clicked.connect(self._dismiss_job)
        row.play_clicked.connect(self._play_job)
        self._rows[job_id] = row
        self.queue_layout.addWidget(row)
        self.queue_box.show()
        self._refresh_queue_height()

    def _on_job_changed(self, job_id: str) -> None:
        row = self._rows.get(job_id)
        job = self.manager.get(job_id)
        if row is None or job is None:
            return
        row.update_from(job)

    def _on_job_finished(self, job_id: str, succeeded: bool) -> None:
        self._on_job_changed(job_id)
        self._refresh_queue_height()

    def _refresh_queue_height(self) -> None:
        rows = list(self._rows.values())
        total = sum(row.sizeHint().height() for row in rows)
        total += max(0, len(rows) - 1) * self.queue_layout.spacing()
        self.scroll.setFixedHeight(min(240, total) if rows else 0)
        self.queue_box.setVisible(bool(rows))
        terminal = any(
            (job := self.manager.get(job_id)) is not None and job.status.is_terminal
            for job_id in self._rows
        )
        self.clear_button.setVisible(terminal)
        self._sync_height()

    # -- job actions -----------------------------------------------------

    def _cancel_job(self, job_id: str) -> None:
        self.manager.cancel(job_id)

    def _dismiss_job(self, job_id: str) -> None:
        row = self._rows.pop(job_id, None)
        if row is not None:
            self.queue_layout.removeWidget(row)
            row.deleteLater()
        self.manager.remove(job_id)
        self._refresh_queue_height()

    def _clear_finished(self) -> None:
        for job_id in list(self._rows):
            job = self.manager.get(job_id)
            if job is not None and job.status.is_terminal:
                self._dismiss_job(job_id)

    def _open_job_folder(self, job_id: str) -> None:
        job = self.manager.get(job_id)
        if job is not None and job.output_path:
            folder = Path(job.output_path).expanduser().parent
        else:
            folder = Path(self.config.download_dir).expanduser()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _play_job(self, job_id: str) -> None:
        job = self.manager.get(job_id)
        if job is None or not job.output_path:
            self.show_message("No downloaded file is available for this item.")
            return
        started, error = open_in_player(self.config.media_player, job.output_path)
        if not started:
            self.show_message(error, 10000)

    # -- input & drag and drop -------------------------------------------

    def _download_from_input(self) -> None:
        urls = extract_urls(self.url_edit.text())
        if not urls:
            self.show_message("That does not look like an http(s) link.")
            return
        for url in urls:
            self.manager.enqueue(url)
        self.url_edit.clear()
        if len(urls) > 1:
            self.show_message(f"Queued {len(urls)} links.")
        else:
            self.show_message("")

    def _paste_from_clipboard(self) -> None:
        urls = extract_urls(QGuiApplication.clipboard().text())
        if not urls:
            self.show_message("No link found in the clipboard.")
            return
        self.url_edit.setText(urls[0])
        self.url_edit.setFocus()
        if len(urls) > 1:
            self.show_message(
                f"The clipboard contains {len(urls)} links; press Download to queue them all."
            )

    @staticmethod
    def _mime_urls(mime: QMimeData) -> list[str]:
        chunks: list[str] = []
        if mime.hasText():
            chunks.append(mime.text())
        if mime.hasUrls():
            chunks.extend(url.toString() for url in mime.urls())
        if mime.hasFormat("text/x-moz-url"):
            chunks.append(bytes(mime.data("text/x-moz-url")).decode("utf-8", "replace"))
        return extract_urls("\n".join(chunks))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._mime_urls(event.mimeData()):
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._mime_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        urls = self._mime_urls(event.mimeData())
        self._set_drag_active(False)
        if not urls:
            event.ignore()
            return
        event.acceptProposedAction()
        for url in urls:
            self.manager.enqueue(url)
        self.url_edit.clear()
        self.show_message(f"Queued {len(urls)} link(s).")

    def _set_drag_active(self, active: bool) -> None:
        if self._drag_active == active:
            return
        self._drag_active = active
        self.card.setProperty("dragActive", active)
        style = self.card.style()
        style.unpolish(self.card)
        style.polish(self.card)
        self.card.update()

    # -- configuration ---------------------------------------------------

    def apply_config(self, config: AppConfig) -> None:
        self.config = config
        self.manager.update_config(config)
        blocked = self.header.pin_button.blockSignals(True)
        self.header.pin_button.setChecked(config.always_on_top)
        self.header.pin_button.blockSignals(blocked)
        self.apply_always_on_top(config.always_on_top)
        self.set_clipboard_watch(config.clipboard_watch)

    def set_always_on_top(self, enabled: bool) -> None:
        self.config.always_on_top = bool(enabled)
        self.apply_always_on_top(bool(enabled))
        self.config_changed.emit()

    def apply_always_on_top(self, enabled: bool) -> None:
        current = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if current == enabled:
            return
        visible = self.isVisible()
        self.setWindowFlags(self._window_flags(enabled))
        if visible:
            self.show()

    def set_clipboard_watch(self, enabled: bool) -> None:
        clipboard = QGuiApplication.clipboard()
        if enabled and not self._clipboard_connected:
            clipboard.dataChanged.connect(self._on_clipboard_changed)
            self._clipboard_connected = True
        elif not enabled and self._clipboard_connected:
            clipboard.dataChanged.disconnect(self._on_clipboard_changed)
            self._clipboard_connected = False

    def _on_clipboard_changed(self) -> None:
        if not self.config.clipboard_watch:
            return
        # Give the clipboard owner a moment to publish the data (X11 selection).
        QTimer.singleShot(60, self._fill_from_clipboard)

    def _fill_from_clipboard(self) -> None:
        if not self.config.clipboard_watch or self.url_edit.text().strip():
            return
        urls = extract_urls(QGuiApplication.clipboard().text())
        if urls:
            self.url_edit.setText(urls[0])

    # -- messages & window state -----------------------------------------

    def show_message(self, text: str, timeout_ms: int = 7000) -> None:
        if not text:
            self.status_label.clear()
            self.status_label.hide()
            self._sync_height()
            return
        self.status_label.setText(text)
        self.status_label.show()
        self._sync_height()
        QTimer.singleShot(timeout_ms, lambda expected=text: self._clear_message(expected))

    def _clear_message(self, expected: str) -> None:
        if self.status_label.text() == expected:
            self.status_label.clear()
            self.status_label.hide()
            self._sync_height()

    def _content_height(self) -> int:
        """Height the layout actually needs at the current width."""
        layout = self.layout()
        if layout is None:
            return self.sizeHint().height()
        layout.activate()
        width = self.width() or self.sizeHint().width()
        if layout.hasHeightForWidth():
            return max(1, layout.heightForWidth(width))
        return max(1, layout.sizeHint().height())

    def _sync_height(self) -> None:
        """Schedule a content-height update for the next event-loop turn.

        Qt refreshes layout size hints asynchronously after rows are removed
        or the queue is hidden; measuring immediately would still return the
        old (larger) height and pin the window to it. Coalesce quick
        consecutive requests into a single zero-delay timer.
        """
        if not self._height_timer.isActive():
            self._height_timer.start()

    def _apply_content_height(self) -> None:
        self.setFixedHeight(self._content_height())

    def save_geometry(self) -> None:
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.sync()

    def _restore_geometry(self) -> None:
        stored = self._settings.value("window/geometry")
        restored = False
        if isinstance(stored, QByteArray) and not stored.isEmpty():
            restored = self.restoreGeometry(stored)
        if not restored or not self._geometry_on_screen():
            self._move_to_default_position()

    def _geometry_on_screen(self) -> bool:
        frame = self.frameGeometry()
        return any(
            screen.availableGeometry().intersects(frame)
            for screen in QGuiApplication.screens()
        )

    def _move_to_default_position(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self._sync_height()
        self.move(area.right() - self.width() - 32, area.top() + 48)

    def show_and_raise(self) -> None:
        """Bring the widget (or an open settings dialog) to the foreground."""
        self.show()
        if self.windowState() & Qt.WindowState.WindowMinimized:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        target = QApplication.activeModalWidget() or self
        target.raise_()
        target.activateWindow()
        handle = target.windowHandle()
        if handle is not None:
            handle.requestActivate()

    def closeEvent(self, event) -> None:
        self.save_geometry()
        event.ignore()
        self.hide_requested.emit()

