"""Application bootstrap: tray icon, single instance, autostart and wiring."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys
import textwrap
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QSettings, QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QSystemTrayIcon

from . import __version__
from .downloader import DownloadManager, JobStatus, find_ytdlp
from .resources import app_icon
from .settings import APPLICATION, ORGANIZATION, load_config, save_config
from .settings_dialog import SettingsDialog
from .widget import WidgetWindow

#: Overridable so automated tests can run an app instance without colliding
#: with the user's real running widget (QLocalServer names are global).
SERVER_NAME = os.environ.get("YTDLP_GUI_SERVER_NAME", "yt-dlp-gui-widget")
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "yt-dlp-gui.desktop"


def set_autostart(enabled: bool) -> None:
    """Create or remove the XDG autostart entry (KDE/GNOME compatible)."""
    if not enabled:
        try:
            AUTOSTART_FILE.unlink()
        except FileNotFoundError:
            pass
        return
    executable = shutil.which("yt-dlp-gui")
    if executable:
        command = f"{shlex.quote(executable)} --hidden"
    else:
        command = f"{shlex.quote(sys.executable)} -m yt_dlp_gui --hidden"
    content = textwrap.dedent(
        f"""\
        [Desktop Entry]
        Type=Application
        Name=yt-dlp widget
        Comment=Small always-on-top widget to download videos with yt-dlp
        Exec={command}
        Icon=video-x-generic
        Terminal=false
        Categories=AudioVideo;Video;
        X-GNOME-Autostart-enabled=true
        StartupNotify=false
        """
    )
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(content, encoding="utf-8")


def _open_download_folder(window: WidgetWindow) -> None:
    folder = Path(window.config.download_dir).expanduser()
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def _notify_running_instance(timeout_ms: int = 3000) -> bool:
    """Ask the already running widget to show itself; False if nobody answers.

    Retries briefly: when the app is launched twice in quick succession the
    first instance may still be creating its local server.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
            return True
        socket.abort()
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yt-dlp-gui",
        description="Always-on-top widget to download videos with yt-dlp",
    )
    parser.add_argument("--hidden", action="store_true", help="start hidden in the system tray")
    args = parser.parse_args(argv)

    QApplication.setOrganizationName(ORGANIZATION)
    QApplication.setApplicationName(APPLICATION)
    QApplication.setApplicationVersion(__version__)

    app = QApplication(sys.argv[:1])
    app.setApplicationDisplayName("yt-dlp widget")
    app.setDesktopFileName(APPLICATION)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    settings = QSettings()
    config = load_config(settings)

    app_data = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    )
    try:
        app_data.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    # Keep the lock referenced for the whole lifetime of the process.
    lock = QLockFile(str(app_data / "instance.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(200):
        if _notify_running_instance():
            return 0
        # The lock exists but nobody answered: likely an abandoned/stale lock.
        lock.removeStaleLockFile()
        if not lock.tryLock(200):
            message = (
                "Another yt-dlp widget instance seems to be running but is not "
                "responding. Quit it from its tray menu and try again, or remove "
                "this file if it is stale:\n\n" + lock.fileName()
            )
            print(message, file=sys.stderr)
            if QApplication.platformName() not in {"offscreen", "minimal"}:
                QMessageBox.warning(None, "yt-dlp widget", message)
            return 1

    manager = DownloadManager(config)
    window = WidgetWindow(config, manager, settings)

    def open_settings() -> None:
        dialog = SettingsDialog(window.config, window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_config = dialog.result_config()
        window.apply_config(new_config)
        save_config(new_config, settings)
        try:
            set_autostart(new_config.start_with_session)
        except OSError as exc:
            window.show_message(f"Could not update the autostart entry: {exc}")

    window.settings_requested.connect(open_settings)
    window.config_changed.connect(lambda: save_config(window.config, settings))

    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip("yt-dlp widget")

    quit_state = {"done": False}

    def quit_app() -> None:
        if quit_state["done"]:
            return
        quit_state["done"] = True
        window.allow_close()
        window.save_geometry()
        manager.shutdown()
        tray.hide()
        app.quit()

    hide_state = {"hint_shown": False}

    def hide_to_tray() -> None:
        window.hide()
        if not hide_state["hint_shown"]:
            hide_state["hint_shown"] = True
            tray.showMessage(
                "yt-dlp widget",
                "Still running in the system tray. Use the tray icon to reopen it.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    window.hide_requested.connect(hide_to_tray)

    menu = QMenu()
    show_action = QAction("Show widget", menu)
    show_action.triggered.connect(window.show_and_raise)
    settings_action = QAction("Settings…", menu)
    settings_action.triggered.connect(open_settings)
    folder_action = QAction("Open download folder", menu)
    folder_action.triggered.connect(lambda: _open_download_folder(window))
    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(quit_app)
    menu.addAction(show_action)
    menu.addAction(settings_action)
    menu.addAction(folder_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if window.isVisible():
                window.hide()
            else:
                window.show_and_raise()

    tray.activated.connect(on_tray_activated)
    tray.show()

    def notify_finished(job_id: str, succeeded: bool) -> None:
        job = manager.get(job_id)
        if job is None or job.status == JobStatus.CANCELED:
            return
        if succeeded:
            tray.showMessage(
                "Download finished",
                job.display_title,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
        else:
            tray.showMessage(
                "Download failed",
                job.error or job.display_title,
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    manager.job_finished.connect(notify_finished)

    def on_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is None:
            return
        connection.disconnected.connect(connection.deleteLater)
        connection.readyRead.connect(connection.readAll)
        window.show_and_raise()

    server = QLocalServer(app)
    QLocalServer.removeServer(SERVER_NAME)
    if server.listen(SERVER_NAME):
        server.newConnection.connect(on_connection)

    available = find_ytdlp(config.yt_dlp_path)
    if not available:
        QTimer.singleShot(
            200,
            lambda: window.show_message(
                "yt-dlp was not found. Install it (e.g. 'sudo pacman -S yt-dlp') "
                "or set its path in Settings.",
                15000,
            ),
        )
        tray.showMessage(
            "yt-dlp not found",
            "Install yt-dlp (e.g. 'sudo pacman -S yt-dlp') or set its path in Settings.",
            QSystemTrayIcon.MessageIcon.Warning,
            8000,
        )

    if not args.hidden:
        window.show_and_raise()

    app.aboutToQuit.connect(window.save_geometry)
    exit_code = app.exec()
    manager.shutdown()
    tray.hide()
    return exit_code
