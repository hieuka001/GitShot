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

from .windows_detect import (
    StableRectTracker, build_screen_map, enumerate_rectangles,
    logical_to_physical, physical_to_logical, snap_edges,
)


class RegionSelector(QWidget):
    selected = Signal(tuple, bool)   # (bbox vật lý toàn cục, có_hít_theo_ô_sẵn_không)
    cancelled = Signal()
    _rects_loaded = Signal(list)

    def __init__(self, smart: bool = True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self._ox, self._oy = geo.topLeft().x(), geo.topLeft().y()
        # Bản đồ màn hình để quy đổi logic (Qt) <-> vật lý (Win32/ImageGrab)
        screens = []
        for s in QGuiApplication.screens():
            g = s.geometry()
            screens.append((g.x(), g.y(), g.width(), g.height(), s.devicePixelRatio()))
        self._smap = build_screen_map(screens)
        self.smart = smart
        self._rects: list = []
        self._load_started = False
        self._tracker = StableRectTracker()
        self._hover = None        # rect VẬT LÝ toàn cục (x1,y1,x2,y2,title)
        self._start: QPoint | None = None
        self._rect = QRect()      # rect kéo tay (tọa độ widget)
        self._painted = QRect()   # vùng đã vẽ lần trước (để repaint theo vùng)
        self._rects_loaded.connect(self._on_rects_loaded)

    def showEvent(self, e):
        super().showEvent(e)
        # Nạp danh sách ô ở THREAD NỀN sau khi lớp phủ đã hiện: nhấn phím tắt
        # là thấy lớp phủ ngay, không khựng vì liệt kê cửa sổ (app lớn có
        # hàng nghìn ô con) chạy trên luồng giao diện như trước.
        if self.smart and not self._load_started:
            self._load_started = True
            import threading
            threading.Thread(target=self._load_rects_bg, daemon=True).start()

    def _load_rects_bg(self):
        self._rects_loaded.emit(enumerate_rectangles())

    def _on_rects_loaded(self, rects):
        self._rects = rects or []
        self._tracker.reset()
        self._hover = None
        self.update()

    # ---------- tọa độ ----------
    def _global_point(self, p: QPoint) -> tuple[int, int]:
        """Điểm widget (logic) -> điểm VẬT LÝ toàn cục (cho Win32/ImageGrab)."""
        return logical_to_physical(p.x() + self._ox, p.y() + self._oy, self._smap)

    def _local_point_from_physical(self, x: int, y: int) -> tuple[int, int]:
        lx, ly = physical_to_logical(x, y, self._smap)
        return (lx - self._ox, ly - self._oy)

    def _local_rect(self, g) -> QRect:
        x1, y1 = self._local_point_from_physical(g[0], g[1])
        x2, y2 = self._local_point_from_physical(g[2], g[3])
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _emit_global(self, bbox, snapped: bool):
        self.close()
        self.selected.emit(tuple(int(v) for v in bbox), snapped)

    # ---------- chuột / phím ----------
    def _drawn_rect(self) -> QRect:
        if self._start is not None and not self._rect.isEmpty():
            return self._rect.normalized()
        if self.smart and self._hover:
            return self._local_rect(self._hover)
        return QRect()

    def _repaint_around(self, old: QRect, new: QRect):
        """Chỉ vẽ lại vùng quanh khung cũ + mới (nới cho nhãn), thay vì
        repaint toàn bộ màn hình ảo ở mỗi pixel di chuột như trước."""
        area = old.united(new).adjusted(-70, -70, 70, 70)
        self.update(area)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            pos = e.position().toPoint()
            # Chưa từng di chuột (lớp phủ hiện ngay dưới con trỏ đứng yên):
            # tính ô đang khoanh ngay tại thời điểm nhấn, tránh click bị trượt.
            if self.smart and self._hover is None and self._rects:
                gx, gy = self._global_point(pos)
                self._hover = self._tracker.update(self._rects, gx, gy)
            self._start = pos
            self._rect = QRect(self._start, self._start)
            self.update()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        old = self._drawn_rect()
        if self._start is not None:
            self._rect = QRect(self._start, pos)
        elif self.smart:
            gx, gy = self._global_point(pos)
            self._hover = self._tracker.update(self._rects, gx, gy)
        self._repaint_around(old, self._drawn_rect())

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._start is None:
            return
        drag = self._rect.normalized()
        self._start = None
        # Thả chuột khi đang có ô được khoanh -> MẶC ĐỊNH chụp đúng ô đó:
        # - nhấp chuột (tay lệch vài px vẫn tính là click), hoặc
        # - kéo nhẹ ngay trong ô (vùng kéo nhỏ hơn 1/3 ô) cũng là ý chọn ô.
        if self.smart and self._hover:
            hov_area = max(1, (self._hover[2] - self._hover[0]) * (self._hover[3] - self._hover[1]))
            drag_area = drag.width() * drag.height()
            cx, cy = self._global_point(drag.center())
            inside = (self._hover[0] <= cx <= self._hover[2]
                      and self._hover[1] <= cy <= self._hover[3])
            if (drag.width() <= 10 and drag.height() <= 10) or (inside and drag_area <= hov_area / 3):
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
            if self.smart and not self._rects and not self._load_started:
                self._load_started = True
                import threading
                threading.Thread(target=self._load_rects_bg, daemon=True).start()
            self._tracker.reset()
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
            title = (self._hover[4] or "")[:42]
            label = f"{title} — {r.width()} × {r.height()}" if title else f"{r.width()} × {r.height()}"
            self._label(p, r, label)
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
