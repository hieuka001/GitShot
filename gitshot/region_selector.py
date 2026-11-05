"""Lớp phủ chọn vùng chụp.

Chế độ THÔNG MINH (mặc định): di chuột tới đâu, app tự nhận diện "ô vuông có
sẵn" tại đó (cửa sổ / khung con / nút / ô nhập) và tô sáng bo góc theo đúng ô
đó — click 1 cái là chụp đúng ô, ảnh được bo góc tròn theo cửa sổ Windows.
Kéo chuột để chọn tay: 4 cạnh tự "hít" vào cạnh các ô gần nhất.
Phím S: bật/tắt nhận ô thông minh. Esc: hủy.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont
from PySide6.QtWidgets import QWidget

from .windows_detect import enumerate_rectangles, find_snap_rect, snap_edges


class RegionSelector(QWidget):
    selected = Signal(tuple, bool)   # (bbox toàn cục, có_hít_theo_ô_sẵn_không)
    cancelled = Signal()

    def __init__(self, smart: bool = True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self._ox, self._oy = geo.topLeft().x(), geo.topLeft().y()
        self.smart = smart
        self._rects = enumerate_rectangles() if smart else []
        self._hover = None        # rect toàn cục (x1,y1,x2,y2,title)
        self._start: QPoint | None = None
        self._rect = QRect()      # rect kéo tay (tọa độ widget)

    # ---------- tọa độ ----------
    def _global_point(self, p: QPoint) -> tuple[int, int]:
        return (p.x() + self._ox, p.y() + self._oy)

    def _local_rect(self, g) -> QRect:
        return QRect(g[0] - self._ox, g[1] - self._oy, g[2] - g[0], g[3] - g[1])

    def _emit_global(self, bbox, snapped: bool):
        self.close()
        self.selected.emit(tuple(int(v) for v in bbox), snapped)

    # ---------- chuột / phím ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.position().toPoint()
            self._rect = QRect(self._start, self._start)
            self.update()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._start is not None:
            self._rect = QRect(self._start, pos)
        elif self.smart:
            gx, gy = self._global_point(pos)
            self._hover = find_snap_rect(self._rects, gx, gy)
        self.update()

    def mouseReleaseEvent(self, e):
        if self._start is None:
            return
        drag = self._rect.normalized()
        start, self._start = self._start, None
        # Click (không kéo) khi đang có ô được nhận diện -> chụp đúng ô đó
        if drag.width() <= 4 and drag.height() <= 4 and self.smart and self._hover:
            self._emit_global(self._hover[:4], True)
            return
        if drag.width() > 4 and drag.height() > 4:
            gx1, gy1 = self._global_point(drag.topLeft())
            gx2, gy2 = self._global_point(drag.bottomRight())
            bbox = (gx1, gy1, gx2, gy2)
            snapped = False
            if self.smart:
                new = snap_edges(bbox, self._rects)
                snapped = new != bbox
                bbox = new
            self._emit_global(bbox, snapped)
            return
        self._rect = QRect()
        self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self.cancelled.emit()
        elif e.key() == Qt.Key_S:
            self.smart = not self.smart
            if self.smart and not self._rects:
                self._rects = enumerate_rectangles()
            self._hover = None
            self.update()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not self._rect.isEmpty():
                r = self._rect.normalized()
                gx1, gy1 = self._global_point(r.topLeft())
                gx2, gy2 = self._global_point(r.bottomRight())
                self._emit_global((gx1, gy1, gx2, gy2), False)
            elif self.smart and self._hover:
                self._emit_global(self._hover[:4], True)

    # ---------- vẽ ----------
    def _label(self, p: QPainter, rect: QRect, text: str):
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        tw = p.fontMetrics().horizontalAdvance(text) + 18
        ty = max(0, rect.top() - 30)
        p.fillRect(rect.left(), ty, tw, 24, QColor(8, 10, 20, 225))
        p.setPen(QColor("#e2e8f0"))
        p.drawText(rect.left() + 9, ty + 17, text)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(10, 12, 24, 130))

        dragging = self._start is not None and not self._rect.isEmpty()
        if dragging:
            r = self._rect.normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor("#22d3ee"), 2))
            p.drawRect(r)
            self._label(p, r, f"{r.width()} × {r.height()}")
        elif self.smart and self._hover:
            r = self._local_rect(self._hover)
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            path = QPainterPath()
            path.addRoundedRect(r, 10, 10)
            p.fillPath(path, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor("#22d3ee"), 2))
            p.drawPath(path)
            p.setPen(QPen(QColor("#a78bfa"), 1, Qt.DashLine))
            p.drawRect(r.adjusted(-5, -5, 5, 5))
            title = (self._hover[4] or "Ô trên màn hình")[:42]
            self._label(p, r, f"▣ {title} — {r.width()} × {r.height()} • Click để chụp ô này")
        else:
            p.setPen(QColor("#e2e8f0"))
            p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            hint = ("Di chuột để nhận ô • Kéo để chọn vùng • S: nhận ô • Esc: hủy"
                    if self.smart else
                    "Kéo để chọn vùng • S: nhận ô • Esc: hủy")
            p.drawText(24, 40, hint)
        p.end()


class MeasureOverlay(QWidget):
    """Thước đo màn hình: kéo chuột, hiện kích thước vùng + đường chéo (px)."""
    closed = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        from PySide6.QtGui import QGuiApplication
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())
        self._start = None
        self._rect = QRect()

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
        pass  # giữ nguyên hình để đọc số; Esc hoặc click phải để thoát

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self.closed.emit()

    def paintEvent(self, e):
        import math
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 12, 24, 90))
        p.setPen(QColor("#e2e8f0"))
        p.setFont(QFont("Segoe UI", 13, QFont.Bold))
        p.drawText(24, 40, "Kéo để đo — Esc để thoát")
        if not self._rect.isEmpty():
            r = self._rect.normalized()
            p.setPen(QPen(QColor("#f59e0b"), 2))
            p.drawRect(r)
            p.drawLine(r.topLeft(), r.bottomRight())
            diag = int(math.hypot(r.width(), r.height()))
            label = f"{r.width()} × {r.height()} px • chéo {diag} px"
            p.setFont(QFont("Segoe UI", 11, QFont.Bold))
            tw = p.fontMetrics().horizontalAdvance(label) + 16
            ty = max(0, r.top() - 28)
            p.fillRect(r.left(), ty, tw, 24, QColor(8, 10, 20, 225))
            p.setPen(QColor("#fde68a"))
            p.drawText(r.left() + 8, ty + 17, label)
        p.end()
