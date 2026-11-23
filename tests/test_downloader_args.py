from pathlib import Path

import pytest

from yt_dlp_gui.downloader import build_args
from yt_dlp_gui.settings import DEFAULT_TEMPLATE, AppConfig


@pytest.fixture
def config():
    cfg = AppConfig()
    cfg.download_dir = "/tmp/videos"
    return cfg


def test_default_arguments(config):
    args = build_args(config, "https://example.com/v", executable="/usr/bin/yt-dlp")
    assert args[0] == "/usr/bin/yt-dlp"
    assert args[-1] == "https://example.com/v"
    assert "--no-playlist" in args
    assert "--split-chapters" not in args
    assert args[args.index("--paths") + 1] == "/tmp/videos"
    assert args[args.index("--output") + 1] == DEFAULT_TEMPLATE
    assert args[args.index("--progress-template") + 1] == "download:%(progress)j"
    assert "--no-simulate" in args
    assert "--progress" in args
    assert "--newline" in args


def test_audio_preset(config):
    config.format_preset = "audio_mp3"
    args = build_args(config, "https://example.com/v")
    assert "--extract-audio" in args
    assert args[args.index("--audio-format") + 1] == "mp3"
    assert "--merge-output-format" not in args


def test_720p_preset(config):
    config.format_preset = "720p"
    args = build_args(config, "https://example.com/v")
    assert args[args.index("--format") + 1] == "bv*[height<=720]+ba/b[height<=720]"


def test_allow_playlist_removes_flag(config):
    config.allow_playlist = True
    args = build_args(config, "https://example.com/v")
    assert "--no-playlist" not in args


def test_split_chapters_adds_flag(config):
    config.split_chapters = True
    args = build_args(config, "https://example.com/v")
    assert "--split-chapters" in args
    assert args[-1] == "https://example.com/v"


def test_download_dir_is_expanded(config):
    config.download_dir = "~/videos"
    args = build_args(config, "https://example.com/v")
    assert args[args.index("--paths") + 1] == str(Path.home() / "videos")


def test_unknown_preset_falls_back(config):
    config.format_preset = "does-not-exist"
    args = build_args(config, "https://example.com/v")
    assert "--merge-output-format" in args
