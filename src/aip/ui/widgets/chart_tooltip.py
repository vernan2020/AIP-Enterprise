from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QToolTip, QWidget


_MISSING_TOKENS = {"", "-", "N/A", "N/D", "NONE", "NULL"}


def build_chart_tooltip(
    title: str,
    rows: Iterable[tuple[str, object]],
    *,
    note: str | None = None,
) -> str:
    """Build a compact institutional rich-text tooltip.

    Missing presentation values are omitted rather than coerced to zero.
    """

    body: list[str] = []
    for label, raw_value in rows:
        if raw_value is None:
            continue
        value = str(raw_value).strip()
        if value.upper() in _MISSING_TOKENS:
            continue
        body.append(
            "<tr>"
            f"<td style='padding-right:12px;color:#5E7183;'>{escape(str(label))}</td>"
            f"<td style='font-weight:600;color:#17324D;'>{escape(value)}</td>"
            "</tr>"
        )

    table = ""
    if body:
        table = (
            "<table cellspacing='0' cellpadding='1' style='margin-top:3px;'>"
            + "".join(body)
            + "</table>"
        )

    note_html = ""
    if note and note.strip():
        note_html = (
            "<div style='margin-top:5px;color:#6F8090;font-size:9px;'>"
            f"{escape(note.strip())}"
            "</div>"
        )

    return (
        "<div style='min-width:190px;'>"
        f"<div style='font-weight:700;color:#00345F;'>{escape(title)}</div>"
        f"{table}{note_html}"
        "</div>"
    )


def point_hit_rect(point: QPointF, radius: float = 9.0) -> QRectF:
    """Return a forgiving hover target around a plotted point."""

    return QRectF(point.x() - radius, point.y() - radius, radius * 2.0, radius * 2.0)


def show_chart_tooltip(
    widget: QWidget,
    event: QMouseEvent,
    regions: Iterable[tuple[QRectF, str]],
) -> bool:
    """Show the tooltip for the first hit region and hide it otherwise."""

    position = event.position()
    for region, text in reversed(tuple(regions)):
        if region.contains(position):
            QToolTip.showText(event.globalPosition().toPoint(), text, widget)
            return True
    QToolTip.hideText()
    return False

def show_series_tooltip(
    point: QPointF,
    state: bool,
    tooltips_by_x: Mapping[int, str],
) -> None:
    """Show rich hover text for a QtCharts XY-series point."""

    if not state or not tooltips_by_x:
        QToolTip.hideText()
        return
    key = min(tooltips_by_x, key=lambda candidate: abs(candidate - point.x()))
    QToolTip.showText(QCursor.pos(), tooltips_by_x[key])

