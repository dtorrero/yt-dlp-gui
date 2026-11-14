from pathlib import Path

from yt_dlp_gui import media_player


def _video(tmp_path: Path) -> Path:
    path = tmp_path / "video.mp4"
    path.write_bytes(b"data")
    return path


def test_default_player_is_vlc():
    assert media_player.DEFAULT_MEDIA_PLAYER == "vlc"
    assert media_player.MEDIA_PLAYERS["vlc"]["label"] == "VLC"
    assert media_player.MEDIA_PLAYERS["mpv"]["executable"] == "mpv"


def test_open_in_player_launches_detached(tmp_path, monkeypatch):
    video = _video(tmp_path)
    calls = []

    monkeypatch.setattr(media_player.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_popen(args, **kwargs):
        calls.append((list(args), kwargs))
        return object()

    monkeypatch.setattr(media_player.subprocess, "Popen", fake_popen)

    ok, error = media_player.open_in_player("mpv", str(video))
    assert (ok, error) == (True, "")
    assert calls[0][0] == ["/usr/bin/mpv", str(video)]
    assert calls[0][1]["start_new_session"] is True


def test_open_in_player_reports_missing_binary(tmp_path, monkeypatch):
    video = _video(tmp_path)
    monkeypatch.setattr(media_player.shutil, "which", lambda name: None)
    ok, error = media_player.open_in_player("vlc", str(video))
    assert ok is False
    assert "VLC" in error
    assert "Settings" in error


def test_open_in_player_reports_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(media_player.shutil, "which", lambda name: "/usr/bin/vlc")
    ok, error = media_player.open_in_player("vlc", str(tmp_path / "missing.mp4"))
    assert ok is False
    assert "no longer exists" in error


def test_open_in_player_rejects_unknown_player(tmp_path):
    video = _video(tmp_path)
    ok, error = media_player.open_in_player("totem", str(video))
    assert ok is False
    assert "Unknown media player" in error


def test_open_in_player_reports_launch_failure(tmp_path, monkeypatch):
    video = _video(tmp_path)
    monkeypatch.setattr(media_player.shutil, "which", lambda name: "/usr/bin/vlc")

    def failing_popen(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(media_player.subprocess, "Popen", failing_popen)
    ok, error = media_player.open_in_player("vlc", str(video))
    assert ok is False
    assert "Could not start VLC" in error
