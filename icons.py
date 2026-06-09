"""Material Symbols SVG helpers for the PyQt frontend."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


BASE_DIR = Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / "assets" / "material_symbols" / "outlined"
FALLBACK_ICON = "label"


def icon_path(icon_name: str | None) -> Path:
    name = _safe_icon_name(icon_name)
    path = ICON_DIR / f"{name}.svg"
    if path.exists():
        return path
    return ICON_DIR / f"{FALLBACK_ICON}.svg"


def material_icon(icon_name: str | None, color: str = "#4e453c", size: int = 24) -> QIcon:
    return QIcon(material_pixmap(icon_name, color, size))


def icon_size(size: int) -> QSize:
    return QSize(size, size)


@lru_cache(maxsize=512)
def material_pixmap(icon_name: str | None, color: str = "#4e453c", size: int = 24) -> QPixmap:
    normalized_size = max(1, int(size))
    pixmap = QPixmap(normalized_size, normalized_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    renderer = QSvgRenderer(str(icon_path(icon_name)))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(_safe_color(color)))
    painter.end()

    return pixmap


def _safe_icon_name(icon_name: str | None) -> str:
    if not icon_name:
        return FALLBACK_ICON
    return "".join(char for char in icon_name if char.isalnum() or char == "_") or FALLBACK_ICON


def _safe_color(color: str) -> str:
    if QColor(color).isValid():
        return color
    return "#4e453c"
