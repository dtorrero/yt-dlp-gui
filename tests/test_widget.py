import pytest
from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QPointF, QUrl, Qt, Signal
from PySide6.QtGui import QCloseEvent, QDropEvent, QGuiApplication, QMouseEvent

from yt_dlp_gui.downloader import DownloadJob, JobStatus
from yt_dlp_gui.settings import AppConfig
from yt_dlp_gui.widget import WidgetWindow


class FakeManager(QObject):
    """Minimal stand-in for DownloadManager (no subprocesses)."""

    job_added = Signal(str)
    job_changed = Signal(str)
    job_finished = Signal(str, bool)

    def __init__(self):
        super().__init__()
        self.config = AppConfig(download_dir="/tmp/yt-dlp-gui-tests")
        self._jobs: dict[str, DownloadJob] = {}
        self.enqueued: list[str] = []

    def enqueue(self, url: str) -> str:
        self.enqueued.append(url)
        job = DownloadJob(id=f"job{len(self.enqueued)}", url=url)
        self._jobs[job.id] = job
        self.job_added.emit(job.id)
        return job.id

    def get(self, job_id: str) -> DownloadJob | None:
        return self._jobs.get(job_id)

    def remove(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    def cancel(self, job_id: str) -> None:
        pass

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def shutdown(self) -> None:
        pass


@pytest.fixture
def window(qapp, ini_settings):
    manager = FakeManager()
    win = WidgetWindow(manager.config, manager, ini_settings)
    yield win
    win.deleteLater()


def _drop_event(mime: QMimeData) -> QDropEvent:
    return QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_drop_plain_text_url(window):
    mime = QMimeData()
    mime.setText("Check this out: https://youtu.be/abc123")
    window.dropEvent(_drop_event(mime))
    assert window.manager.enqueued == ["https://youtu.be/abc123"]


def test_drop_uri_list(window):
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/one"), QUrl("https://example.com/two")])
    window.dropEvent(_drop_event(mime))
    assert window.manager.enqueued == ["https://example.com/one", "https://example.com/two"]


def test_drop_without_url_is_ignored(window):
    mime = QMimeData()
    mime.setText("no links here")
    event = _drop_event(mime)
    window.dropEvent(event)
    assert window.manager.enqueued == []
    assert not event.isAccepted()


def test_download_button_enqueues_typed_url(window):
    window.url_edit.setText("https://example.com/v")
    window.download_button.click()
    assert window.manager.enqueued == ["https://example.com/v"]
    assert window.url_edit.text() == ""


def test_invalid_input_shows_message(window):
    window.url_edit.setText("not a link")
    window.download_button.click()
    assert window.manager.enqueued == []
    assert window.status_label.text()


def test_job_row_is_added(window):
    window.manager.enqueue("https://example.com/v")
    assert len(window._rows) == 1
    row = next(iter(window._rows.values()))
    assert row.action_button.text() == "Cancel"
    assert not row.action_button.isHidden()
    assert row.play_button.isHidden()
    assert row.folder_button.isHidden()
    assert not window.queue_box.isHidden()


def test_done_job_shows_play_and_folder_icons(window, tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    job = DownloadJob(
        id="done1",
        url="https://example.com/v",
        title="Finished video",
        status=JobStatus.DONE,
        percent=100.0,
        output_path=str(video),
    )
    window.manager._jobs[job.id] = job
    window.manager.job_added.emit(job.id)
    row = window._rows[job.id]
    row.update_from(job)

    assert not row.play_button.isHidden()
    assert not row.folder_button.isHidden()
    assert row.action_button.isHidden()
    assert row.play_button.isEnabled()

    calls = []
    monkeypatch.setattr(
        "yt_dlp_gui.widget.open_in_player",
        lambda player, path: calls.append((player, path)) or (True, ""),
    )
    row.play_button.click()
    assert calls == [("vlc", str(video))]


def test_play_failure_is_shown_in_status(window, tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"data")
    job = DownloadJob(
        id="done2",
        url="https://example.com/v",
        title="Finished video",
        status=JobStatus.DONE,
        percent=100.0,
        output_path=str(video),
    )
    window.manager._jobs[job.id] = job
    window.manager.job_added.emit(job.id)
    row = window._rows[job.id]
    row.update_from(job)

    monkeypatch.setattr(
        "yt_dlp_gui.widget.open_in_player",
        lambda player, path: (False, "VLC was not found on PATH."),
    )
    row.play_button.click()
    assert "VLC was not found" in window.status_label.text()


def test_show_and_raise_shows_hidden_window(window):
    window.hide()
    assert not window.isVisible()
    window.show_and_raise()
    assert window.isVisible()


def test_paste_button_reads_clipboard(window, qapp):
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText("https://example.com/clip")
    window.paste_button.click()
    assert window.url_edit.text() == "https://example.com/clip"


def test_clear_finished_restores_base_height(window, tmp_path, qapp):
    for index in range(2):
        job = DownloadJob(
            id=f"done{index}",
            url=f"https://example.com/{index}",
            title=f"Finished {index}",
            status=JobStatus.DONE,
            percent=100.0,
            output_path=str(tmp_path / f"video{index}.mp4"),
        )
        window.manager._jobs[job.id] = job
        window.manager.job_added.emit(job.id)

    window.show()
    qapp.processEvents()
    tall_height = window.height()
    assert tall_height > 200

    window._clear_finished()
    qapp.processEvents()

    assert window.height() == window._content_height()
    assert window.height() < 200
    assert window.height() < tall_height
    assert window.queue_box.isHidden()


def test_saved_tall_geometry_does_not_stretch_layout(qapp, ini_settings):
    """A geometry saved while the queue had rows must not leave empty bands."""
    from PySide6.QtWidgets import QWidget

    dummy = QWidget()
    dummy.resize(470, 500)
    dummy.show()
    qapp.processEvents()
    ini_settings.setValue("window/geometry", dummy.saveGeometry())
    ini_settings.sync()
    dummy.deleteLater()

    manager = FakeManager()
    win = WidgetWindow(manager.config, manager, ini_settings)
    try:
        win.show()
        qapp.processEvents()
        assert win.height() == win._content_height()
        assert win.height() < 200
        assert win.header.height() < 40
        # Header and URL field remain adjacent (only the layout spacing between).
        gap = win.url_edit.geometry().top() - win.header.geometry().bottom()
        assert gap < 40
    finally:
        win.deleteLater()


def test_window_flags_follow_always_on_top():
    on_top = WidgetWindow._window_flags(True)
    assert on_top & Qt.WindowType.WindowStaysOnTopHint
    assert on_top & Qt.WindowType.FramelessWindowHint
    assert on_top & Qt.WindowType.Tool
    assert not WidgetWindow._window_flags(False) & Qt.WindowType.WindowStaysOnTopHint


def test_pin_toggle_keeps_the_window_position(window, qapp):
    window.show()
    window.move(120, 80)
    qapp.processEvents()

    window.set_always_on_top(False)
    qapp.processEvents()
    assert not window.config.always_on_top
    assert not window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.pos() == QPoint(120, 80)

    window.set_always_on_top(True)
    qapp.processEvents()
    assert window.config.always_on_top
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.pos() == QPoint(120, 80)


def test_default_position_is_the_top_right_corner(window):
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    area = screen.availableGeometry()

    window._move_to_default_position()

    pos = window.pos()
    assert area.contains(pos)
    assert pos.x() + window.width() <= area.right() + 1
    assert pos.y() == area.top() + 48


def test_system_move_is_not_used_off_wayland(window):
    window.show()
    assert not window.header._start_system_move()


def test_titlebar_prefers_system_move_when_available(window, monkeypatch):
    window.show()
    calls = []
    monkeypatch.setattr(
        window.header, "_start_system_move", lambda: calls.append(True) or True
    )

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        QPointF(105, 105),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.header.mousePressEvent(press)

    assert calls == [True]
    assert window.header._drag_offset is None


def test_titlebar_drags_window_without_system_move(window, qapp):
    window.show()
    window.move(100, 100)
    qapp.processEvents()

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        QPointF(105, 105),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.header.mousePressEvent(press)

    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(35, 25),
        QPointF(135, 125),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.header.mouseMoveEvent(move)

    assert window.pos() == QPoint(130, 120)

    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(35, 25),
        QPointF(135, 125),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.header.mouseReleaseEvent(release)
    assert window.header._drag_offset is None




def test_close_hides_to_tray_until_a_quit_allows_it(window):
    hidden = []
    window.hide_requested.connect(lambda: hidden.append(True))

    hide_event = QCloseEvent()
    window.closeEvent(hide_event)
    assert not hide_event.isAccepted()
    assert hidden == [True]

    window.allow_close()
    quit_event = QCloseEvent()
    window.closeEvent(quit_event)
    assert quit_event.isAccepted()
