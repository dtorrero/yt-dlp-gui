# yt-dlp widget

A tiny always-on-top desktop widget for Linux (KDE/GNOME/any X11 or Wayland
desktop) that downloads videos with [yt-dlp](https://github.com/yt-dlp/yt-dlp)
from a URL you paste or **drag from your browser**.

```
┌──────────────────────────────────────────┐
│ ⬇ yt-dlp widget          ⚙  📌  –  ×    │
│ ┌──────────────────────────┐ ┌─────┐ ┌──────┐
│ │ Paste a URL or drop link │ │Paste│ │Download│
│ └──────────────────────────┘ └─────┘ └──────┘
│ Downloads                     Clear finished
│ ┌──────────────────────────────────────┐
│ │ Video title                  [Cancel]│
│ │ ███████████░░░░  62.4% · 4.1MiB/s …  │
│ └──────────────────────────────────────┘
└──────────────────────────────────────────┘
```

## Features

- **Drag & drop from the browser** — drag a link or the address-bar URL onto the
  widget (`text/uri-list`, `text/plain` and Firefox's `text/x-moz-url` are all
  understood). This works with Firefox and Chromium; on Wayland the widget runs
  through XWayland by default, so the compositor bridges the drag (see
  [Wayland](#wayland)). The Paste button is always there as a fallback.
- **Paste / Ctrl+V** — paste one or multiple links; each is queued.
- **Queue with live progress** — title, progress bar, speed, ETA, per-job
  cancel, "Open folder" when done, "Clear finished".
- **Play / open folder** — finished items get a play button that opens the
  file in VLC or MPV (configurable, VLC by default) and a folder icon.
- **Runs in the system tray** — the × and – buttons hide the widget while
  downloads keep running. Tray menu: show/hide, settings, open download folder,
  quit. Always-on-top and tray-hiding are independent.
- **Settings** — download folder (defaults to your localised XDG `Downloads`
  folder, e.g. `~/Descargas`), quality preset, filename template, simultaneous
  downloads, playlist handling, optional chapter splitting, clipboard watcher,
  autostart.
- **Single instance** — launching again (menu or terminal) raises and focuses
  the existing widget, including an open Settings dialog. A stale lock is
  recovered automatically. Note that `yt-dlp` itself is a Python program, so
  each active download adds a `python3 /usr/bin/yt-dlp` child process; count
  app instances with `pgrep -af 'python -m yt_dlp_gui'`.
- **Machine-readable yt-dlp integration** — progress comes from
  `--progress-template "download:%(progress)j"`, and the final path from
  `after_move:__FILE__%(filepath)s`. No terminal scraping, no shell.
- **Logs** — every download's raw yt-dlp output is written to
  `~/.local/share/yt-dlp-gui/logs/`.

## Requirements

- Python ≥ 3.11 and PySide6 ≥ 6.11 (`PySide6-Essentials` is enough)
- `yt-dlp` on `PATH` (or configured in Settings)
- `ffmpeg` for merging best video+audio and for MP3 extraction

Arch/Manjaro:

```bash
sudo pacman -S yt-dlp ffmpeg
```

Keep yt-dlp up to date with your package manager; the Settings dialog shows the
detected version.

## Install & run

```bash
poetry install
poetry run yt-dlp-gui
```

Without Poetry:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
yt-dlp-gui
```

Start hidden in the tray:

```bash
yt-dlp-gui --hidden
```

### Wayland

On Wayland the widget runs through **XWayland** by default. The Wayland
`xdg-shell` protocol lets the compositor decide where a window goes and has no
"keep above" request, so a native Wayland window cannot be positioned by the
app (it opens centred and the title bar cannot drag it) and the always-on-top
pin does nothing. XWayland restores all three behaviours on KDE, GNOME and
wlroots desktops alike.

- The Qt platform is picked at startup and falls back to native Wayland
  automatically when XWayland is unavailable (Qt's `xcb;wayland` plugin list).
- An explicitly set `QT_QPA_PLATFORM` is always respected.
- Set `YTDLP_GUI_NATIVE_WAYLAND=1` to force native Wayland. The title bar can
  then still move the window (`startSystemMove()`), but the compositor chooses
  its position, only the size is remembered, and the always-on-top pin has no
  effect. Background clipboard watching and single-instance raising are also
  restricted by the compositor; use the Paste button and the tray icon.

### KDE / desktop menu entry

The bundled installer adds a menu launcher and the modern **yt-dlp** icon for
the current user (no root needed):

```bash
./install.sh              # install
./install.sh --uninstall  # remove menu entry, icons, launcher, autostart
```

It writes:

- `~/.local/share/applications/yt-dlp-gui.desktop` (shows up in the KDE menu)
- `~/.local/share/icons/hicolor/<size>x<size>/apps/yt-dlp-gui.png`
  (16/22/24/32/48/64/128/256/512 px)
- `~/.local/bin/yt-dlp-gui` — a small launcher that runs the project with the
  right interpreter (project `.venv`, then Poetry's environment, then `python3`;
  override with `YTDLP_GUI_PYTHON=/path/to/python`)

It refreshes the KDE menu cache with `kbuildsycoca6` when available. Because the
launcher points at this checkout, re-run the script if you move the repository.
After an icon redesign, also re-run `./install.sh`: it replaces the installed
PNGs and clears KDE's `icon-cache.kcache`, so the new pixmaps are picked up.
The autostart checkbox in Settings writes the same integration independently.

The icon is generated by `scripts/generate_icons.py` (modern bold sans-serif
"yt-dlp", Adwaita Sans with Roboto / Source Sans 3 / Noto Sans fallbacks, baked
into PNGs so no font is needed at runtime). Regenerate it after changing the
design:

```bash
python3 scripts/generate_icons.py
```

The static `packaging/yt-dlp-gui.desktop` is an alternative for people who
already installed the `yt-dlp-gui` console script.

### Autostart

The "Start with the desktop session" checkbox writes/removes
`~/.config/autostart/yt-dlp-gui.desktop`, which KDE and GNOME both honour.

## Usage

1. Paste a video URL, press **Download**, or drag a link from the browser.
2. Watch progress in the queue; cancel with the row button if needed.
3. Done jobs offer **Open folder**.

Multiple links can be pasted at once (one per line); queued jobs run one after
another unless "Simultaneous downloads" is increased.

## Settings

| Setting | Meaning |
|---|---|
| Download folder | Where files are saved (created on save if missing) |
| Quality | Best MP4, best any container, ≤1080p, ≤720p, audio-only MP3 |
| Filename template | yt-dlp output template (default `%(title)s [%(id)s].%(ext)s`) |
| yt-dlp binary | Optional path override; auto-detected otherwise |
| Media player | VLC (default) or MPV, used by the play button on finished items |
| Simultaneous downloads | 1–5 parallel yt-dlp processes |
| Always on top | Window stays above other windows while visible (needs the default XWayland path on Wayland; see [Wayland](#wayland)) |
| Start with session | XDG autostart entry, starts hidden in the tray |
| Clipboard watcher | Pre-fills the field when a link is copied (off by default) |
| Split chapters | Off = one file per video, on = `--split-chapters` (one file per chapter, when available) |
| Playlists | Off = `--no-playlist` (single video), on = download the playlist |

Settings live in `~/.config/yt-dlp-gui/yt-dlp-gui.conf` (QSettings INI).

## Development

```bash
poetry install
poetry run pytest -m "not network"   # unit + GUI tests, offscreen Qt
poetry run pytest -m network         # real download (3 s sample MP3)
```

The GUI tests use `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py`), so
they run headless as well as on a desktop.

Layout:

```
├── install.sh         # KDE/GNOME menu + icon installer/uninstaller
├── scripts/
│   └── generate_icons.py  # renders the modern wordmark PNGs
├── yt_dlp_gui/
│   ├── __main__.py        # `python -m` entry; picks XWayland vs native Wayland
│   ├── app.py             # QApplication, tray, single instance, autostart
│   ├── widget.py          # frameless window, title bar, job rows, drag & drop
│   ├── downloader.py      # DownloadManager (QProcess), arg builder, progress parser
│   ├── settings.py        # AppConfig, QSettings persistence, quality presets
│   ├── settings_dialog.py # settings UI
│   ├── media_player.py    # launch VLC/MPV for finished downloads
│   ├── url_utils.py       # extract http(s) URLs from paste/drop payloads
│   ├── resources.py       # multi-size icon loader (painted fallback)
│   └── assets/icons/      # yt-dlp-gui-*.png wordmark icons
└── packaging/yt-dlp-gui.desktop
```

## Known limitations

- One queue row per URL; a playlist is one row that reports the current item.
- Canceling leaves yt-dlp's `.part` file behind (yt-dlp resumes it next time).
- With chapter splitting enabled, chapter files use yt-dlp's built-in chapter
  filename template rather than the configured Filename template.
- Cookies / age-restricted videos, SponsorBlock and subtitle options are not
  exposed yet.
- The UI is English-only for now; it is not a KDE Plasma plasmoid, just a
  frameless `Qt.Tool` window (so it does not appear in Alt-Tab on X11/XWayland,
  by design; on native Wayland taskbar/Alt-Tab handling is up to the
  compositor).
- Native Wayland (`YTDLP_GUI_NATIVE_WAYLAND=1`): the compositor positions the
  window, ignores always-on-top and may refuse focus requests, so the default
  XWayland path is what most users want.
- Background clipboard watching only sees new links while the widget is focused
  on native Wayland; it works in the background on X11/XWayland (the default).

## License

MIT — see [LICENSE](LICENSE). You may use, modify, distribute, sublicense and
sell this software, provided the copyright notice is retained.
