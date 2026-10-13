"""Atomic PNG export of existing Qt financial charts, without changing source data."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QIODevice, QSaveFile
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


def export_widget_png(widget: QWidget, destination: str | Path) -> tuple[int, int]:
    """Capture the rendered widget at Qt's device-pixel ratio and save atomically."""
    if widget.width() <= 0 or widget.height() <= 0:
        raise ValueError("El gráfico no tiene dimensiones válidas.")
    pixmap = widget.grab()
    if pixmap.isNull():
        raise ValueError("El gráfico todavía no se puede capturar.")

    output = QSaveFile(str(destination))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(output.errorString())
    if not pixmap.save(output, "PNG"):
        output.cancelWriting()
        raise OSError("No se pudo codificar la imagen PNG.")
    if not output.commit():
        raise OSError(output.errorString())
    return pixmap.width(), pixmap.height()


def save_widget_png_dialog(
    parent: QWidget, widget: QWidget, suggested_filename: str
) -> None:
    """Export only after the user chooses the file path; report any write failure."""
    path, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        "Guardar gráfico financiero",
        suggested_filename,
        "Imagen PNG (*.png)",
    )
    if not path:
        return
    if not path.lower().endswith(".png"):
        path += ".png"
    try:
        export_widget_png(widget, path)
    except (OSError, ValueError) as exc:
        QMessageBox.warning(
            parent, "Error de exportación", f"No se pudo guardar el gráfico: {exc}"
        )
        return
    QMessageBox.information(
        parent, "Exportación completada", "El gráfico se guardó como imagen PNG."
    )
