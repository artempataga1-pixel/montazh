"""Контуры текста для объёмных 3D-надписей (Three.js SVGLoader + ExtrudeGeometry).
Шрифт — Inter (кириллица и латиница лежат разными файлами-подмножествами), символ берётся из того файла, где он есть.

    from textpath import text_path
    d, w = text_path("ПРАВДУ", weight=900)   # d — SVG-путь (y вниз, кегль 100), w — ширина строки
"""
from functools import lru_cache
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parent / "assets" / "fonts"


@lru_cache(None)
def _fonts(weight: int) -> list[TTFont]:
    return [TTFont(FONTS / f"inter-{sub}-{weight}-normal.woff2") for sub in ("cyrillic", "latin")]


def text_path(text: str, weight: int = 900, size: float = 100, tracking: float = 0.0, y_up: bool = False) -> tuple[str, float]:
    """y_up=True — для 3D: координаты сразу в осях Three.js (без отрицательного масштаба, иначе нормали выворачиваются)."""
    x, parts = 0.0, []
    for ch in text:
        for f in _fonts(weight):
            g = f.getBestCmap().get(ord(ch))
            if g:
                break
        else:
            raise KeyError(f"нет глифа {ch!r} в Inter {weight}")
        k = size / f["head"].unitsPerEm
        gs = f.getGlyphSet()
        pen = SVGPathPen(gs)
        gs[g].draw(TransformPen(pen, (k, 0, 0, k if y_up else -k, x, 0)))  # базовая линия — 0
        parts.append(pen.getCommands())
        x += gs[g].width * k + tracking * size
    return " ".join(p for p in parts if p), x - tracking * size
