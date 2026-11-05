"""Lấy mã màu trên màn hình: di chuột xem trước màu tại điểm, click để lấy."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QFont, QPen
from PySide6.QtWidgets import QWidget


class ColorPickerOverlay(QWidget):
    picked = Signal(str, tuple)   # (hex, (r, g, b))
    cancelled = Signal()

    def __init__(self, screenshot: QPixmap, pil_image):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self._ox, self._oy = geo.topLeft().x(), geo.topLeft().y()
        self._shot = screenshot
        self._pil = pil_image  # PIL RGB theo tọa độ vật lý của ảnh chụp
        self._pos = None

    def _color_at(self, pos):
        if self._pil is None or pos is None:
            return None
        x, y = pos.x(), pos.y()
        # Ảnh chụp có thể khác tỉ lệ với geometry Qt khi DPI scale != 100%:
        # quy đổi tuyến tính theo kích thước.
        if self.width() > 0 and self.height() > 0:
            px = int(x * self._pil.size[0] / self.width())
            py = int(y * self._pil.size[1] / self.height())
        else:
            px, py = x, y
        px = max(0, min(self._pil.size[0] - 1, px))
        py = max(0, min(self._pil.size[1] - 1, py))
        r, g, b = self._pil.convert("RGB").getpixel((px, py))[:3]
        return (r, g, b)

    def mouseMoveEvent(self, e):
        self._pos = e.position().toPoint()
        self.update()

    def mousePressEvent(self, e):
        rgb = self._color_at(e.position().toPoint())
        if rgb:
            hexcode = "#{:02X}{:02X}{:02X}".format(*rgb)
            self.close()
            self.picked.emit(hexcode, rgb)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self.cancelled.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._shot)
        rgb = self._color_at(self._pos)
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        if self._pos is not None and rgb:
            hexcode = "#{:02X}{:02X}{:02X}".format(*rgb)
            x, y = self._pos.x(), self._pos.y()
            # Vòng tròn đánh dấu điểm
            p.setPen(QPen(QColor("white"), 2))
            p.drawEllipse(x - 9, y - 9, 18, 18)
            p.setPen(QPen(QColor(rgb[0], rgb[1], rgb[2]), 2))
            p.drawEllipse(x - 6, y - 6, 12, 12)
            # Bảng thông tin đi theo chuột
            bx = min(x + 18, self.width() - 190)
            by = min(y + 18, self.height() - 86)
            p.fillRect(bx, by, 182, 78, QColor(8, 10, 20, 230))
            p.fillRect(bx + 10, by + 10, 26, 26, QColor(*rgb))
            p.setPen(QColor("#f8fafc"))
            p.drawText(bx + 46, by + 28, hexcode)
            p.setPen(QColor("#94a3b8"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(bx + 10, by + 56, f"RGB {rgb[0]}, {rgb[1]}, {rgb[2]} • click để copy")
        else:
            p.setPen(QColor("#f8fafc"))
            p.drawText(24, 40, "🎨 Di chuột tới điểm cần lấy màu, click để copy mã HEX • Esc hủy")
        p.end()
