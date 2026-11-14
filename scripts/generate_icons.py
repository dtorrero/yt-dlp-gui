#!/usr/bin/env python3
"""Render the yt-dlp-gui app icon (modern, bold "yt-dlp" wordmark).

The glyphs are baked into PNGs, so neither the app nor the installed icon
depends on a specific font being present at runtime.

Usage:
    python3 scripts/generate_icons.py
    python3 scripts/generate_icons.py --output /tmp/icons --sizes 64,128
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# QPixmap/QFontDatabase need a QGuiApplication; stay headless when there is no display.
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontInfo,
    QFontMetricsF,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPixmap,
)

DEFAULT_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)
FONT_CANDIDATES = (
    "Adwaita Sans",  # modern GNOME UI sans (Bold installed on this system)
    "Roboto",
    "Source Sans 3",
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
)

TEXT = "yt-dlp"


def _choose_font_family() -> str:
    available = set(QFontDatabase.families())
    for family in FONT_CANDIDATES:
        if family in available:
            return family
    return QFontInfo(QFont("sans-serif")).family()


def _render(size: int, family: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#6d8dff"))
    gradient.setColorAt(1.0, QColor("#3f4fd6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.23, size * 0.23)

    # Measure at a fixed size, then scale to fill ~86% of the tile width.
    probe = QFont(family)
    probe.setPixelSize(100)
    probe.setWeight(QFont.Weight.Bold)
    probe_metrics = QFontMetricsF(probe)
    text_width = probe_metrics.horizontalAdvance(TEXT) or 1
    width_ratio = 0.92 if size <= 48 else 0.86
    pixel_size = max(6, int(width_ratio * size * 100 / text_width))

    font = QFont(family)
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Bold)
    # Slightly tight tracking gives the wordmark a modern, composed feel.
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 99.0)
    metrics = QFontMetricsF(font)

    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    baseline = (size + metrics.ascent() - metrics.descent()) / 2
    x = (size - metrics.horizontalAdvance(TEXT)) / 2
    painter.drawText(QPointF(x, baseline), TEXT)
    painter.end()
    return pixmap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "yt_dlp_gui" / "assets" / "icons",
        help="directory for the generated PNGs",
    )
    parser.add_argument(
        "--sizes",
        default=",".join(str(size) for size in DEFAULT_SIZES),
        help="comma separated pixel sizes (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])  # noqa: F841 - required for QPixmap/QFontDatabase
    family = _choose_font_family()
    if not family:
        print("error: no usable sans-serif font found", file=sys.stderr)
        return 1

    sizes = []
    for chunk in args.sizes.split(","):
        chunk = chunk.strip()
        if chunk:
            sizes.append(int(chunk))
    if not sizes:
        print("error: no sizes requested", file=sys.stderr)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    for size in sizes:
        pixmap = _render(size, family)
        path = args.output / f"yt-dlp-gui-{size}.png"
        if not pixmap.save(str(path), "PNG"):
            print(f"error: could not write {path}", file=sys.stderr)
            return 1
        print(f"wrote {path} ({size}x{size}, font: {family})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
