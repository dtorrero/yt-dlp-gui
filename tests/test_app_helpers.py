import yt_dlp_gui.app as app_module


def test_set_autostart_writes_and_removes(monkeypatch, tmp_path):
    target = tmp_path / "autostart" / "yt-dlp-gui.desktop"
    monkeypatch.setattr(app_module, "AUTOSTART_FILE", target)

    app_module.set_autostart(True)
    content = target.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in content
    assert "Exec=" in content
    assert "--hidden" in content
    assert "Type=Application" in content

    app_module.set_autostart(False)
    assert not target.exists()


def test_set_autostart_disable_is_idempotent(monkeypatch, tmp_path):
    target = tmp_path / "autostart" / "yt-dlp-gui.desktop"
    monkeypatch.setattr(app_module, "AUTOSTART_FILE", target)
    app_module.set_autostart(False)  # nothing to remove
    assert not target.exists()
