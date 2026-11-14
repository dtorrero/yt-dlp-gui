import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "install.sh"


def _env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_BIN_HOME": str(tmp_path / "bin"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "YTDLP_GUI_PYTHON": sys.executable,
            "SKIP_CACHE_UPDATE": "1",
        }
    )
    env.pop("PYTHONPATH", None)
    return env


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=120,
    )


def test_install_creates_menu_entry_icons_and_launcher(tmp_path):
    env = _env(tmp_path)
    result = _run(env)
    assert result.returncode == 0, result.stderr

    data = tmp_path / "data"
    desktop = data / "applications" / "yt-dlp-gui.desktop"
    assert desktop.is_file()
    text = desktop.read_text(encoding="utf-8")
    launcher = tmp_path / "bin" / "yt-dlp-gui"
    assert f'Exec="{launcher}"' in text
    assert "Icon=yt-dlp-gui" in text
    assert "Categories=AudioVideo;Video;" in text
    assert launcher.is_file()
    assert os.access(launcher, os.X_OK)

    icons = sorted((data / "icons" / "hicolor").glob("*/apps/yt-dlp-gui.png"))
    assert len(icons) == 9

    # The generated launcher must actually run the app.
    help_result = subprocess.run(
        [str(launcher), "--help"], capture_output=True, text=True, timeout=60
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "usage:" in help_result.stdout.lower()


def test_uninstall_removes_menu_entry_icons_and_launcher(tmp_path):
    env = _env(tmp_path)
    assert _run(env).returncode == 0

    result = _run(env, "--uninstall")
    assert result.returncode == 0, result.stderr

    data = tmp_path / "data"
    assert not (data / "applications" / "yt-dlp-gui.desktop").exists()
    assert list((data / "icons" / "hicolor").glob("*/apps/yt-dlp-gui.png")) == []
    assert not (tmp_path / "bin" / "yt-dlp-gui").exists()
