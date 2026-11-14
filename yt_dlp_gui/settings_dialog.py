"""Settings dialog: download folder, quality, tools and behaviour toggles."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .downloader import find_ffmpeg, find_ytdlp
from .media_player import MEDIA_PLAYERS, resolve_executable
from .settings import FORMAT_PRESETS, AppConfig


def _row(*widgets: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for index, widget in enumerate(widgets):
        layout.addWidget(widget, 1 if index == 0 else 0)
    return container


class SettingsDialog(QDialog):
    """Collects a new :class:`AppConfig`; nothing is written here."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("yt-dlp widget settings")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._config = config.copy()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        self.folder_edit = QLineEdit(self._config.download_dir)
        browse_folder = QPushButton("Browse…")
        browse_folder.clicked.connect(self._browse_folder)
        form.addRow("Download folder", _row(self.folder_edit, browse_folder))

        self.preset_combo = QComboBox()
        for key, meta in FORMAT_PRESETS.items():
            self.preset_combo.addItem(str(meta["label"]), key)
        self.preset_combo.setCurrentIndex(
            max(0, self.preset_combo.findData(self._config.format_preset))
        )
        form.addRow("Quality", self.preset_combo)

        self.player_combo = QComboBox()
        for key, meta in MEDIA_PLAYERS.items():
            self.player_combo.addItem(meta["label"], key)
        self.player_combo.setCurrentIndex(
            max(0, self.player_combo.findData(self._config.media_player))
        )
        self.player_combo.currentIndexChanged.connect(self._update_player_status)
        form.addRow("Media player", self.player_combo)

        self.player_status = QLabel()
        self.player_status.setObjectName("muted")
        self.player_status.setWordWrap(True)
        form.addRow("", self.player_status)

        self.template_edit = QLineEdit(self._config.filename_template)
        self.template_edit.setToolTip("yt-dlp output template, e.g. %(title)s [%(id)s].%(ext)s")
        form.addRow("Filename template", self.template_edit)

        self.ytdlp_edit = QLineEdit(self._config.yt_dlp_path)
        self.ytdlp_edit.setPlaceholderText("Auto-detect (leave empty)")
        self.ytdlp_edit.editingFinished.connect(self._update_tool_status)
        browse_ytdlp = QPushButton("Browse…")
        browse_ytdlp.clicked.connect(self._browse_executable)
        form.addRow("yt-dlp binary", _row(self.ytdlp_edit, browse_ytdlp))

        self.tool_status = QLabel()
        self.tool_status.setObjectName("muted")
        self.tool_status.setWordWrap(True)
        form.addRow("", self.tool_status)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 5)
        self.concurrent_spin.setValue(self._config.max_concurrent)
        form.addRow("Simultaneous downloads", self.concurrent_spin)

        self.on_top_check = QCheckBox("Keep the widget always on top")
        self.on_top_check.setChecked(self._config.always_on_top)
        layout.addWidget(self.on_top_check)

        self.autostart_check = QCheckBox("Start with the desktop session (hidden in the tray)")
        self.autostart_check.setChecked(self._config.start_with_session)
        layout.addWidget(self.autostart_check)

        self.clipboard_check = QCheckBox("Watch the clipboard and pre-fill video links")
        self.clipboard_check.setChecked(self._config.clipboard_watch)
        layout.addWidget(self.clipboard_check)

        self.playlist_check = QCheckBox("Download whole playlists instead of a single video")
        self.playlist_check.setChecked(self._config.allow_playlist)
        layout.addWidget(self.playlist_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_tool_status()
        self._update_player_status()

    # -- actions --------------------------------------------------------

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose download folder", self.folder_edit.text() or str(Path.home())
        )
        if folder:
            self.folder_edit.setText(folder)

    def _browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select the yt-dlp binary", "/usr/bin")
        if path:
            self.ytdlp_edit.setText(path)
            self._update_tool_status()

    def _update_tool_status(self) -> None:
        ytdlp = find_ytdlp(self.ytdlp_edit.text().strip())
        if not ytdlp:
            self.tool_status.setText(
                "yt-dlp was not found — install it (e.g. 'sudo pacman -S yt-dlp') "
                "or choose the binary above."
            )
            return
        version = "unknown"
        try:
            result = subprocess.run(
                [ytdlp, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError):
            version = "could not be run"
        message = f"yt-dlp {version} detected."
        if not find_ffmpeg():
            message += " ffmpeg was not found; merging and audio extraction will fail."
        self.tool_status.setText(message)

    def _update_player_status(self) -> None:
        key = str(self.player_combo.currentData())
        label = MEDIA_PLAYERS.get(key, {}).get("label", key)
        executable = resolve_executable(key)
        if executable:
            self.player_status.setText(f"{label} found at {executable}.")
        else:
            self.player_status.setText(
                f"{label} was not found on PATH; install it or choose another player."
            )

    def _on_accept(self) -> None:
        folder_text = self.folder_edit.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "Invalid folder", "Please choose a download folder.")
            return
        folder = Path(folder_text).expanduser()
        if not folder.is_dir():
            answer = QMessageBox.question(
                self,
                "Create folder?",
                f"The folder\n\n{folder}\n\ndoes not exist. Create it?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "Cannot create folder", str(exc))
                return

        self._config = replace(
            self._config,
            download_dir=str(folder),
            format_preset=str(self.preset_combo.currentData()),
            filename_template=self.template_edit.text().strip() or self._config.filename_template,
            always_on_top=self.on_top_check.isChecked(),
            start_with_session=self.autostart_check.isChecked(),
            clipboard_watch=self.clipboard_check.isChecked(),
            allow_playlist=self.playlist_check.isChecked(),
            max_concurrent=self.concurrent_spin.value(),
            media_player=str(self.player_combo.currentData()),
            yt_dlp_path=self.ytdlp_edit.text().strip(),
        )
        self.accept()

    def result_config(self) -> AppConfig:
        return self._config
