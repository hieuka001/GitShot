"""Lớp phủ chọn vùng chụp — ĐƠN GIẢN: nhấn chuột, kéo, thả là chọn xong.

Từ v1.5.1 bỏ hẳn "nhận ô thông minh" theo yêu cầu người dùng: không liệt kê
cửa sổ, không hít cạnh, không quy đổi tọa độ — một hệ tọa độ Qt duy nhất từ
lúc kéo tới lúc chụp nên không còn điểm nào để lệch. Esc: hủy.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
    selected = Signal(tuple, bool)   # (bbox toàn cục, False) — giữ chữ ký cho app
    cancelled = Signal()

    def __init__(self, smart: bool = False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self._ox, self._oy = geo.topLeft().x(), geo.topLeft().y()
        self._start: QPoint | None = None
        self._cur: QPoint | None = None

    def _drag_rect(self) -> QRect:
        # Tự lấy min/max 2 đầu: QRect 2 điểm + normalized() của Qt bị hụt
        # 1px mỗi cạnh khi kéo ngược (lên/trái) do quy ước tọa độ inclusive.
        if self._start is None or self._cur is None:
            return QRect()
        x1, x2 = sorted((self._start.x(), self._cur.x()))
        y1, y2 = sorted((self._start.y(), self._cur.y()))
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _global(self, p: QPoint) -> tuple[int, int]:
        return (p.x() + self._ox, p.y() + self._oy)

    def _emit(self, r: QRect):
        # bbox theo quy ước (x1, y1, x2, y2) với x2/y2 là điểm cuối con trỏ:
        # dùng left+width thay cho bottomRight() (vốn hụt 1px vì QRect
        # tính right = left + width - 1).
        gx1, gy1 = self._global(r.topLeft())
        gx2, gy2 = gx1 + r.width(), gy1 + r.height()
        self.close()
        self.selected.emit((gx1, gy1, gx2, gy2), False)

    # ---------- chuột / phím ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.position().toPoint()
            self._cur = self._start
            self.update()

    def mouseMoveEvent(self, e):
        if self._start is not None:
            self._cur = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._start is None:
            return
        self._cur = e.position().toPoint()
        r = self._drag_rect()
        self._start = None
        self._cur = None
        if r.width() >= 8 and r.height() >= 8:
            self._emit(r)
            return
        # Kéo quá nhỏ (hoặc chỉ nhấp chuột): bỏ qua, chờ kéo lại
        self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self.cancelled.emit()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            r = self._drag_rect()
            if r.width() >= 8 and r.height() >= 8:
                self._emit(r)

    # ---------- vẽ ----------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(10, 12, 24, 130))
        r = self._drag_rect()
        if self._start is not None and not r.isEmpty():
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor("#22d3ee"), 2))
            p.drawRect(r)
            text = f"{r.width()} × {r.height()}"
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tw = p.fontMetrics().horizontalAdvance(text) + 18
            ty = max(0, r.top() - 30)
            p.fillRect(r.left(), ty, tw, 24, QColor(8, 10, 20, 225))
            p.setPen(QColor("#e2e8f0"))
            p.drawText(r.left() + 9, ty + 17, text)
        else:
            p.setPen(QColor("#e2e8f0"))
            p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            p.drawText(24, 40, "Kéo chuột để chọn vùng • Esc: hủy")
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
            a, b = self._rect.topLeft(), self._rect.bottomRight()
            r = QRect(min(a.x(), b.x()), min(a.y(), b.y()),
                      abs(a.x() - b.x()), abs(a.y() - b.y()))
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
