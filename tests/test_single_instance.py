"""Single-instance behaviour, exercised with real app processes (offscreen)."""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _app_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONPATH": str(REPO),
            # Keep this test away from the user's real running widget.
            "YTDLP_GUI_SERVER_NAME": f"yt-dlp-gui-test-{os.getpid()}-{tmp_path.name}",
        }
    )
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    return env


def _wait_for_lock(env: dict[str, str], timeout: float = 15.0) -> Path | None:
    data_home = Path(env["XDG_DATA_HOME"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        locks = list(data_home.rglob("instance.lock"))
        if locks:
            return locks[0]
        time.sleep(0.05)
    return None


def test_second_launch_exits_and_first_stays_alive(tmp_path):
    env = _app_env(tmp_path)
    first = subprocess.Popen(
        [sys.executable, "-m", "yt_dlp_gui", "--hidden"],
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert _wait_for_lock(env) is not None, "first instance never created its lock"

        started = time.monotonic()
        second = subprocess.run(
            [sys.executable, "-m", "yt_dlp_gui"],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        elapsed = time.monotonic() - started

        assert second.returncode == 0, second.stderr
        assert elapsed < 8, f"second launch took {elapsed:.1f}s"
        assert first.poll() is None, "first instance exited unexpectedly"
    finally:
        first.terminate()
        try:
            first.wait(timeout=5)
        except subprocess.TimeoutExpired:
            first.kill()
