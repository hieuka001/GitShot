"""Lớp phủ chọn vùng chụp toàn màn hình: kéo chuột chọn, Enter xác nhận, Esc hủy."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
    selected = Signal(tuple)   # (x1, y1, x2, y2) tọa độ màn hình
    cancelled = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        # Phủ toàn bộ màn hình ảo (nhiều monitor)
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self._origin_geo = geo.topLeft()
        self._start = None
        self._rect = QRect()

    def _to_global(self, rect: QRect) -> tuple[int, int, int, int]:
        r = rect.normalized()
        ox, oy = self._origin_geo.x(), self._origin_geo.y()
        return (r.left() + ox, r.top() + oy, r.right() + ox, r.bottom() + oy)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.position().toPoint()
            self._rect = QRect(self._start, self._start)
            self.update()

    def mouseMoveEvent(self, e):
        if self._start is not None:
            self._rect = QRect(self._start, e.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, e):
        if self._start is not None and self._rect.normalized().width() > 4 and self._rect.normalized().height() > 4:
            bbox = self._to_global(self._rect)
            self.close()
            self.selected.emit(bbox)
        elif self._start is not None:
            self._start = None
            self._rect = QRect()
            self.update()

    def mouseDoubleClickEvent(self, e):
        if not self._rect.isEmpty():
            bbox = self._to_global(self._rect)
            self.close()
            self.selected.emit(bbox)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self.cancelled.emit()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and not self._rect.isEmpty():
            bbox = self._to_global(self._rect)
            self.close()
            self.selected.emit(bbox)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 12, 24, 130))
        if not self._rect.isEmpty():
            r = self._rect.normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor("#22d3ee"), 2)
            p.setPen(pen)
            p.drawRect(r)
            label = f"{r.width()} × {r.height()}  —  thả chuột / Enter để chụp"
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tw = p.fontMetrics().horizontalAdvance(label) + 16
            ty = max(0, r.top() - 30)
            p.fillRect(r.left(), ty, tw, 24, QColor(8, 10, 20, 220))
            p.setPen(QColor("#e2e8f0"))
            p.drawText(r.left() + 8, ty + 17, label)
        else:
            p.setPen(QColor("#e2e8f0"))
            p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            p.drawText(24, 40, "Kéo chuột để chọn vùng chụp  •  Esc để hủy")
        p.end()
