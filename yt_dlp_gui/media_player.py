"""Launch the configured external media player for a finished download."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

MEDIA_PLAYERS: dict[str, dict[str, str]] = {
    "vlc": {"label": "VLC", "executable": "vlc"},
    "mpv": {"label": "MPV", "executable": "mpv"},
}
DEFAULT_MEDIA_PLAYER = "vlc"


def resolve_executable(player: str) -> str:
    """Absolute path of the player binary, or ``""`` if it is not installed."""
    meta = MEDIA_PLAYERS.get(player)
    if meta is None:
        return ""
    return shutil.which(meta["executable"]) or ""


def open_in_player(player: str, file_path: str) -> tuple[bool, str]:
    """Open *file_path* in *player*.

    Returns ``(True, "")`` on success, or ``(False, human_readable_error)``.
    The player is detached from the widget, so it keeps running when the
    widget quits.
    """
    meta = MEDIA_PLAYERS.get(player)
    if meta is None:
        return False, f"Unknown media player setting: {player!r}."
    path = Path(file_path).expanduser()
    if not file_path or not path.is_file():
        return False, f"The downloaded file no longer exists:\n{path}"
    executable = shutil.which(meta["executable"])
    if not executable:
        return False, (
            f"{meta['label']} was not found on PATH. Install it or choose "
            "another player in Settings."
        )
    try:
        subprocess.Popen(
            [executable, str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        return False, f"Could not start {meta['label']}: {exc}"
    return True, ""
