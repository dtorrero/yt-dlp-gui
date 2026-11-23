"""Persistent application settings and the quality presets."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, QStandardPaths

from .media_player import DEFAULT_MEDIA_PLAYER, MEDIA_PLAYERS

ORGANIZATION = "yt-dlp-gui"
APPLICATION = "yt-dlp-gui"

DEFAULT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"
DEFAULT_PRESET = "best_mp4"

#: yt-dlp arguments for each quality preset.  ``label`` is shown in the UI.
FORMAT_PRESETS: dict[str, dict[str, Any]] = {
    "best_mp4": {
        "label": "Best quality (MP4)",
        "arguments": [
            "--format",
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
            "--merge-output-format",
            "mp4",
        ],
    },
    "best": {
        "label": "Best quality (any container)",
        "arguments": ["--format", "bv*+ba/b"],
    },
    "1080p": {
        "label": "Up to 1080p",
        "arguments": ["--format", "bv*[height<=1080]+ba/b[height<=1080]"],
    },
    "720p": {
        "label": "Up to 720p",
        "arguments": ["--format", "bv*[height<=720]+ba/b[height<=720]"],
    },
    "audio_mp3": {
        "label": "Audio only (MP3)",
        "arguments": [
            "--format",
            "ba/b",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
        ],
    },
}


def default_download_dir() -> str:
    """XDG download directory (localised!), falling back to ``~/Downloads``."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return location or str(Path.home() / "Downloads")


@dataclass
class AppConfig:
    """All user-configurable state of the widget."""

    download_dir: str = field(default_factory=default_download_dir)
    format_preset: str = DEFAULT_PRESET
    filename_template: str = DEFAULT_TEMPLATE
    always_on_top: bool = True
    start_with_session: bool = False
    clipboard_watch: bool = False
    allow_playlist: bool = False
    split_chapters: bool = False
    max_concurrent: int = 1
    media_player: str = DEFAULT_MEDIA_PLAYER
    yt_dlp_path: str = ""

    def copy(self) -> "AppConfig":
        return replace(self)


def load_config(settings: QSettings | None = None) -> AppConfig:
    """Read the configuration, tolerating missing or malformed values."""
    settings = settings or QSettings()
    config = AppConfig()

    folder = settings.value("downloads/folder", config.download_dir)
    if isinstance(folder, str) and folder.strip():
        config.download_dir = folder.strip()

    preset = settings.value("downloads/format_preset", config.format_preset)
    if isinstance(preset, str) and preset in FORMAT_PRESETS:
        config.format_preset = preset

    template = settings.value("downloads/filename_template", config.filename_template)
    if isinstance(template, str) and template.strip():
        config.filename_template = template.strip()

    config.always_on_top = bool(settings.value("ui/always_on_top", config.always_on_top, type=bool))
    config.clipboard_watch = bool(settings.value("ui/clipboard_watch", config.clipboard_watch, type=bool))
    config.start_with_session = bool(
        settings.value("ui/start_with_session", config.start_with_session, type=bool)
    )
    config.allow_playlist = bool(
        settings.value("downloads/allow_playlist", config.allow_playlist, type=bool)
    )
    config.split_chapters = bool(
        settings.value("downloads/split_chapters", config.split_chapters, type=bool)
    )

    try:
        concurrent = int(settings.value("downloads/max_concurrent", config.max_concurrent))
    except (TypeError, ValueError):
        concurrent = config.max_concurrent
    config.max_concurrent = min(5, max(1, concurrent))

    player = settings.value("media/player", config.media_player)
    if isinstance(player, str) and player in MEDIA_PLAYERS:
        config.media_player = player

    yt_dlp_path = settings.value("tools/yt_dlp_path", "")
    if isinstance(yt_dlp_path, str):
        config.yt_dlp_path = yt_dlp_path.strip()

    return config


def save_config(config: AppConfig, settings: QSettings | None = None) -> None:
    """Persist *config* with QSettings."""
    settings = settings or QSettings()
    settings.setValue("downloads/folder", config.download_dir)
    settings.setValue("downloads/format_preset", config.format_preset)
    settings.setValue("downloads/filename_template", config.filename_template)
    settings.setValue("downloads/allow_playlist", config.allow_playlist)
    settings.setValue("downloads/split_chapters", config.split_chapters)
    settings.setValue("downloads/max_concurrent", config.max_concurrent)
    settings.setValue("ui/always_on_top", config.always_on_top)
    settings.setValue("ui/clipboard_watch", config.clipboard_watch)
    settings.setValue("ui/start_with_session", config.start_with_session)
    settings.setValue("media/player", config.media_player)
    settings.setValue("tools/yt_dlp_path", config.yt_dlp_path)
    settings.sync()
