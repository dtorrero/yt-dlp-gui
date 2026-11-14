"""End-to-end check against the real yt-dlp binary (opt-in: ``-m network``)."""

import subprocess

import pytest

from yt_dlp_gui.downloader import FILE_MARKER, TITLE_MARKER, build_args
from yt_dlp_gui.settings import AppConfig

SAMPLE_URL = "https://download.samplelib.com/mp3/sample-3s.mp3"


@pytest.mark.network
def test_real_download(tmp_path):
    config = AppConfig(download_dir=str(tmp_path), format_preset="best")
    args = build_args(config, SAMPLE_URL)
    result = subprocess.run(args, capture_output=True, text=True, timeout=180)

    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stdout.splitlines()
    assert any(line.startswith(TITLE_MARKER) for line in lines)
    assert any(line.startswith(FILE_MARKER) for line in lines)

    downloaded = [path for path in tmp_path.iterdir() if not path.name.endswith(".part")]
    assert downloaded, result.stderr[-2000:]
    assert downloaded[0].stat().st_size > 0
