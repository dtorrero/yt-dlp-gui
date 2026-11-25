import yt_dlp_gui.__main__ as main_module
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


def test_configure_qt_platform_prefers_xwayland():
    env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0"}
    assert main_module.configure_qt_platform(env) == "xcb;wayland"
    assert env["QT_QPA_PLATFORM"] == "xcb;wayland"


def test_configure_qt_platform_detects_wayland_without_session_type():
    env = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"}
    assert main_module.configure_qt_platform(env) == "xcb;wayland"


def test_configure_qt_platform_keeps_explicit_platform():
    env = {
        "XDG_SESSION_TYPE": "wayland",
        "WAYLAND_DISPLAY": "wayland-1",
        "DISPLAY": ":0",
        "QT_QPA_PLATFORM": "offscreen",
    }
    assert main_module.configure_qt_platform(env) == "offscreen"
    assert env["QT_QPA_PLATFORM"] == "offscreen"


def test_configure_qt_platform_honours_native_wayland_opt_out():
    env = {
        "XDG_SESSION_TYPE": "wayland",
        "WAYLAND_DISPLAY": "wayland-1",
        "DISPLAY": ":0",
        main_module.NATIVE_WAYLAND_ENV: "1",
    }
    assert main_module.configure_qt_platform(env) is None
    assert "QT_QPA_PLATFORM" not in env


def test_configure_qt_platform_without_xwayland():
    env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-1"}
    assert main_module.configure_qt_platform(env) is None
    assert "QT_QPA_PLATFORM" not in env


def test_configure_qt_platform_leaves_x11_sessions_alone():
    env = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
    assert main_module.configure_qt_platform(env) is None
    assert "QT_QPA_PLATFORM" not in env
