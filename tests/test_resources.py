from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

from yt_dlp_gui.resources import ICON_SIZES, app_icon, app_pixmap, tinted_icon

ASSET_DIR = Path(__file__).resolve().parent.parent / "yt_dlp_gui" / "assets" / "icons"


def test_all_bundled_icon_sizes_exist():
    for size in ICON_SIZES:
        assert (ASSET_DIR / f"yt-dlp-gui-{size}.png").is_file()


def test_app_icon_exposes_multiple_sizes(qapp):
    sizes = {size.width() for size in app_icon().availableSizes()}
    assert {16, 64, 512} <= sizes


def test_app_pixmap_returns_requested_size(qapp):
    pixmap = app_pixmap(48)
    assert not pixmap.isNull()
    assert pixmap.size() == QSize(48, 48)


def test_app_pixmap_downscales_from_larger_asset(qapp):
    pixmap = app_pixmap(40)
    assert pixmap.size() == QSize(40, 40)


def test_tinted_icon_recolors_opaque_pixels(qapp):
    source = QPixmap(16, 16)
    source.fill(Qt.GlobalColor.white)
    tinted = tinted_icon(QIcon(source), "#5b7cfa", 16)
    image = tinted.pixmap(16, 16).toImage()
    color = image.pixelColor(8, 8)
    assert (color.red(), color.green(), color.blue()) == (0x5B, 0x7C, 0xFA)


def test_tinted_icon_keeps_transparency(qapp):
    source = QPixmap(16, 16)
    source.fill(Qt.GlobalColor.transparent)
    painter = QPainter(source)
    painter.fillRect(4, 4, 8, 8, Qt.GlobalColor.white)
    painter.end()
    tinted = tinted_icon(QIcon(source), "#5b7cfa", 16)
    image = tinted.pixmap(16, 16).toImage()
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(8, 8).alpha() == 255
