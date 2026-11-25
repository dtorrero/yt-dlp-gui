"""Allow ``python -m yt_dlp_gui`` and prepare the Qt platform plugin."""

import os
import sys
from collections.abc import MutableMapping

#: Set to 1/true/yes/on to keep the native Wayland Qt plugin.  Native Wayland
#: cannot place windows or keep them above others, so the widget is then
#: centred by the compositor and the pin button has no effect.
NATIVE_WAYLAND_ENV = "YTDLP_GUI_NATIVE_WAYLAND"

_TRUTHY = {"1", "true", "yes", "on"}


def configure_qt_platform(environ: MutableMapping[str, str] | None = None) -> str | None:
    """Run the widget through XWayland on Wayland desktops.

    xdg-shell clients cannot position their own top-level windows nor request
    "always on top", which is exactly what this frameless widget needs:
    ``move()`` is ignored (so the compositor centres it and the title bar
    cannot drag it) and ``Qt.WindowStaysOnTopHint`` is never sent to the
    compositor.  XWayland restores both behaviours on KDE, GNOME and wlroots
    desktops alike.

    The ``xcb;wayland`` value is Qt's ordered plugin list: if XWayland is not
    reachable, Qt falls back to the native Wayland plugin instead of aborting.

    An explicitly configured ``QT_QPA_PLATFORM`` always wins, and setting
    ``YTDLP_GUI_NATIVE_WAYLAND`` to a true value opts out.  Returns the
    platform string that was selected (``None`` when nothing was changed).
    """
    env = os.environ if environ is None else environ

    current = env.get("QT_QPA_PLATFORM")
    if current:
        return current
    if env.get(NATIVE_WAYLAND_ENV, "").strip().lower() in _TRUTHY:
        return None

    wayland = env.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland" or bool(
        env.get("WAYLAND_DISPLAY")
    )
    # Without DISPLAY there is no XWayland to fall back to.
    if wayland and env.get("DISPLAY"):
        env["QT_QPA_PLATFORM"] = "xcb;wayland"
        return env["QT_QPA_PLATFORM"]
    return None


def main(argv: list[str] | None = None) -> int:
    # Must run before PySide6 (and therefore QApplication) is imported.
    configure_qt_platform()
    from .app import main as app_main

    return app_main(argv)


if __name__ == "__main__":
    sys.exit(main())
