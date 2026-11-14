"""Application icon: the bundled yt-dlp wordmark, with a painted fallback."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

ICON_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def _asset_path(size: int) -> Path | None:
    try:
        base = resources.files(__package__ or "yt_dlp_gui")
        candidate = Path(str(base / "assets" / "icons" / f"yt-dlp-gui-{size}.png"))
    except (ModuleNotFoundError, AttributeError, TypeError):
        return None
    return candidate if candidate.is_file() else None


def _available_sizes() -> list[int]:
    return [size for size in ICON_SIZES if _asset_path(size) is not None]


def _painted_pixmap(size: int) -> QPixmap:
    """Fallback used only if the bundled PNG assets are missing."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#5b7cfa"))
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.26, size * 0.26)

    pen = QPen(
        QColor("#ffffff"),
        size * 0.085,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    center = size * 0.5
    painter.drawLine(QPointF(center, size * 0.24), QPointF(center, size * 0.62))
    painter.drawLine(QPointF(size * 0.32, size * 0.46), QPointF(center, size * 0.64))
    painter.drawLine(QPointF(size * 0.68, size * 0.46), QPointF(center, size * 0.64))
    painter.drawLine(QPointF(size * 0.28, size * 0.80), QPointF(size * 0.72, size * 0.80))
    painter.end()
    return pixmap


def app_pixmap(size: int = 64) -> QPixmap:
    """Return the wordmark at *size* pixels (downscaled from the nearest asset)."""
    available = _available_sizes()
    if available:
        larger = [candidate for candidate in available if candidate >= size]
        source_size = min(larger) if larger else max(available)
        source_path = _asset_path(source_size)
        if source_path is not None:
            source = QPixmap(str(source_path))
            if not source.isNull():
                if source.width() != size:
                    source = source.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                return source
    return _painted_pixmap(size)


def app_icon() -> QIcon:
    """Multi-resolution icon for the window, tray and KDE launcher."""
    icon = QIcon()
    for size in _available_sizes():
        path = _asset_path(size)
        if path is not None:
            icon.addFile(str(path), QSize(size, size))
    if icon.isNull():
        icon = QIcon(_painted_pixmap(64))
    return icon


def tinted_icon(icon: QIcon, color: str, size: int = 32) -> QIcon:
    """Recolour an icon (usually a QStyle standard icon) to *color*.

    The source pixmap keeps its alpha channel; ``SourceIn`` paints the new
    colour only where the icon is opaque, so anti-aliased edges stay smooth.
    """
    source = icon.pixmap(QSize(size, size))
    if source.isNull():
        return icon
    tinted = QPixmap(source.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return QIcon(tinted)

