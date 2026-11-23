from yt_dlp_gui.settings import (
    DEFAULT_PRESET,
    AppConfig,
    load_config,
    save_config,
)


def test_defaults(ini_settings, qapp):
    config = load_config(ini_settings)
    assert config.format_preset == DEFAULT_PRESET
    assert config.max_concurrent == 1
    assert config.always_on_top is True
    assert config.clipboard_watch is False
    assert config.allow_playlist is False
    assert config.split_chapters is False
    assert config.media_player == "vlc"
    assert config.download_dir


def test_roundtrip(ini_settings, qapp):
    original = AppConfig(
        download_dir="/tmp/downloads",
        format_preset="audio_mp3",
        filename_template="%(title)s.%(ext)s",
        always_on_top=False,
        start_with_session=True,
        clipboard_watch=True,
        allow_playlist=True,
        split_chapters=True,
        max_concurrent=3,
        media_player="mpv",
        yt_dlp_path="/usr/local/bin/yt-dlp",
    )
    save_config(original, ini_settings)
    loaded = load_config(ini_settings)
    assert loaded.download_dir == original.download_dir
    assert loaded.format_preset == original.format_preset
    assert loaded.filename_template == original.filename_template
    assert loaded.always_on_top is False
    assert loaded.start_with_session is True
    assert loaded.clipboard_watch is True
    assert loaded.allow_playlist is True
    assert loaded.split_chapters is True
    assert loaded.max_concurrent == 3
    assert loaded.media_player == "mpv"
    assert loaded.yt_dlp_path == original.yt_dlp_path


def test_invalid_values_are_tolerated(ini_settings, qapp):
    ini_settings.setValue("downloads/format_preset", "not-a-preset")
    ini_settings.setValue("downloads/max_concurrent", 42)
    ini_settings.setValue("downloads/folder", "   ")
    ini_settings.setValue("media/player", "totem")
    config = load_config(ini_settings)
    assert config.format_preset == DEFAULT_PRESET
    assert config.max_concurrent == 5
    assert config.media_player == "vlc"
    assert config.download_dir


def test_non_numeric_concurrency_falls_back(ini_settings, qapp):
    ini_settings.setValue("downloads/max_concurrent", "many")
    config = load_config(ini_settings)
    assert config.max_concurrent == 1
