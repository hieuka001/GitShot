"""Trình sửa ảnh sau khi chụp + nút Gửi lên GitHub (Enter).

Công cụ: bút vẽ, đường thẳng, mũi tên, hình chữ nhật, elip, chữ, đánh số bước,
che mờ vùng nhạy cảm. Hoàn tác bằng chồng ảnh chụp (snapshot) cho chắc chắn.
Upload chạy ở luồng riêng; xong hiện hộp thoại link + tự copy.
"""
from __future__ import annotations

import io
import math

from PIL import Image
from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice, QObject, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from .capture import pixelate
from .utils import format_link

TOOLS = [
    ("pen", "Bút"),
    ("line", "Đường thẳng"),
    ("arrow", "Mũi tên"),
    ("rect", "Khung"),
    ("ellipse", "Elip"),
    ("text", "T Chữ"),
    ("step", "Số bước"),
    ("blur", "Che mờ"),
]


def pixmap_to_pil(pm: QPixmap) -> Image.Image:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(ba))).convert("RGBA")


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    pm = QPixmap()
    pm.loadFromData(buf.getvalue(), "PNG")
    return pm


def pixmap_to_png_bytes(pm: QPixmap) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    return bytes(ba)


class Canvas(QWidget):
    """Vùng vẽ: thao tác chuột vẽ trực tiếp lên QPixmap nền."""

    def __init__(self, pixmap: QPixmap, get_tool, get_color, get_width, on_change):
        super().__init__()
        self.pm = pixmap
        self._get_tool, self._get_color, self._get_width = get_tool, get_color, get_width
        self._on_change = on_change
        self._start = None
        self._preview: QPixmap | None = None
        self._last = None
        self.step_counter = 0
        self.setFixedSize(pixmap.size())
        self.setCursor(Qt.CrossCursor)

    def set_pixmap(self, pm: QPixmap):
        self.pm = pm
        self._preview = None
        self.setFixedSize(pm.size())
        self.update()

    def _pen(self):
        return QPen(QColor(self._get_color()), self._get_width(), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def _draw_shape(self, target: QPixmap, tool: str, a, b, final: bool):
        p = QPainter(target)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(self._pen())
        if tool == "line":
            p.drawLine(a, b)
        elif tool == "arrow":
            p.drawLine(a, b)
            angle = math.atan2(b.y() - a.y(), b.x() - a.x())
            size = 12 + self._get_width() * 2
            for delta in (2.65, -2.65):
                x = b.x() + size * math.cos(angle + delta)
                y = b.y() + size * math.sin(angle + delta)
                p.drawLine(b.x(), b.y(), int(x), int(y))
        elif tool == "rect":
            p.drawRect(min(a.x(), b.x()), min(a.y(), b.y()), abs(b.x() - a.x()), abs(b.y() - a.y()))
        elif tool == "ellipse":
            p.drawEllipse(min(a.x(), b.x()), min(a.y(), b.y()), abs(b.x() - a.x()), abs(b.y() - a.y()))
        p.end()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pos = e.position().toPoint()
        tool = self._get_tool()
        if tool == "step":
            self._on_change()
            self.step_counter += 1
            p = QPainter(self.pm)
            p.setRenderHint(QPainter.Antialiasing)
            r = 14
            p.setBrush(QColor(self._get_color()))
            p.setPen(QPen(QColor("white"), 2))
            p.drawEllipse(pos.x() - r, pos.y() - r, r * 2, r * 2)
            p.setFont(QFont("Segoe UI", 13, QFont.Bold))
            p.drawText(pos.x() - r, pos.y() - r, r * 2, r * 2, Qt.AlignCenter, str(self.step_counter))
            p.end()
            self.update()
            return
        if tool == "text":
            text, ok = QInputDialog.getText(self, "Thêm chữ", "Nội dung:")
            if ok and text:
                self._on_change()
                p = QPainter(self.pm)
                p.setPen(self._pen())
                p.setFont(QFont("Segoe UI", 11 + self._get_width() * 3, QFont.Bold))
                p.drawText(pos, text)
                p.end()
                self.update()
            return
        self._on_change()  # chụp snapshot TRƯỚC khi bắt đầu nét vẽ này để Hoàn tác đúng 1 nét
        self._start = pos
        self._last = pos

    def mouseMoveEvent(self, e):
        if self._start is None:
            return
        pos = e.position().toPoint()
        tool = self._get_tool()
        if tool == "pen":
            if self._last is not None:
                p = QPainter(self.pm)
                p.setPen(self._pen())
                p.drawLine(self._last, pos)
                p.end()
            self._last = pos
            self.update()
        else:
            self._preview = self.pm.copy()
            if tool != "blur":
                self._draw_shape(self._preview, tool, self._start, pos, False)
            else:
                p = QPainter(self._preview)
                p.setPen(QPen(QColor("#f59e0b"), 2, Qt.DashLine))
                p.drawRect(min(self._start.x(), pos.x()), min(self._start.y(), pos.y()),
                           abs(pos.x() - self._start.x()), abs(pos.y() - self._start.y()))
                p.end()
            self.update()

    def mouseReleaseEvent(self, e):
        if self._start is None:
            return
        pos = e.position().toPoint()
        tool = self._get_tool()
        if tool == "pen":
            pass  # đã vẽ trong lúc di chuột; snapshot lấy ở lần nhấn sau / khi đổi công cụ
        elif tool == "blur":
            self._on_change()
            img = pixmap_to_pil(self.pm)
            bbox = (min(self._start.x(), pos.x()), min(self._start.y(), pos.y()),
                    max(self._start.x(), pos.x()), max(self._start.y(), pos.y()))
            self.pm = pil_to_pixmap(pixelate(img, bbox))
        else:
            self._on_change()
            self._draw_shape(self.pm, tool, self._start, pos, True)
        self._start = None
        self._last = None
        self._preview = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#111827"))  # nền tối để thấy phần góc trong suốt (ảnh bo góc)
        p.drawPixmap(0, 0, self._preview or self.pm)
        p.end()


class _UploadWorker(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:
            self.failed.emit(str(e))


class LinkDialog(QDialog):
    def __init__(self, url: str, copy_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Đã tải lên GitHub")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Liên kết ảnh:"))
        field = QLineEdit(url)
        field.setReadOnly(True)
        field.selectAll()
        lay.addWidget(field)
        row = QHBoxLayout()
        b_copy = QPushButton("Sao chép liên kết")
        b_copy.clicked.connect(lambda: _copy(copy_text))
        b_open = QPushButton("Mở liên kết")
        b_open.clicked.connect(lambda: __import__("webbrowser").open(url))
        b_ok = QPushButton("Xong")
        b_ok.clicked.connect(self.accept)
        row.addWidget(b_copy); row.addWidget(b_open); row.addStretch(); row.addWidget(b_ok)
        lay.addLayout(row)
        lay.addWidget(QLabel("Liên kết đã được sao chép vào clipboard."))


def _copy(text: str):
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.clipboard().setText(text)


class EditorWindow(QMainWindow):
    uploaded = Signal(object)   # UploadResult
    saved_local = Signal(str)   # path

    def __init__(self, image: Image.Image, filename: str, config, upload_fn, save_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"GitShot — {filename}")
        self.filename = filename
        self.config = config
        self._upload_fn = upload_fn
        self._save_fn = save_fn
        self._tool = "pen"
        self._color = "#ef4444"
        self._width = 3
        self._undo: list[QPixmap] = []
        self._thread = None
        self._worker = None

        pm = pil_to_pixmap(image)
        self.canvas = Canvas(pm, lambda: self._tool, lambda: self._color,
                             lambda: self._width, self._push_undo)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)

        bar = QHBoxLayout()
        self._tool_buttons = {}
        for key, label in TOOLS:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self._set_tool(k))
            self._tool_buttons[key] = b
            bar.addWidget(b)
        self._tool_buttons["pen"].setChecked(True)
        b_color = QPushButton("Màu")
        b_color.clicked.connect(self._pick_color)
        bar.addWidget(b_color)
        for w in (2, 3, 5, 8):
            b = QToolButton(); b.setText(f"{w}px"); b.setCheckable(True)
            b.clicked.connect(lambda _=False, ww=w: self._set_width(ww))
            if w == 3:
                b.setChecked(True)
                self._width_btn = b
            bar.addWidget(b)
        b_undo = QPushButton("Hoàn tác")
        b_undo.clicked.connect(self._do_undo)
        bar.addWidget(b_undo)
        bar.addStretch()
        root.addLayout(bar)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setAlignment(Qt.AlignCenter)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        b_copyimg = QPushButton("Sao chép ảnh (Ctrl+C)")
        b_copyimg.clicked.connect(lambda: _copy_image(self.canvas.pm))
        b_save = QPushButton("Lưu vào máy (Ctrl+S)")
        b_save.clicked.connect(self._save_local)
        self.b_upload = QPushButton("Tải lên GitHub (Enter)")
        self.b_upload.setObjectName("primaryBtn")
        self.b_upload.clicked.connect(self.upload)
        actions.addWidget(b_copyimg)
        actions.addWidget(b_save)
        actions.addStretch()
        actions.addWidget(self.b_upload)
        root.addLayout(actions)

        self.setCentralWidget(central)
        self.resize(min(1180, pm.width() + 60), min(820, pm.height() + 170))

    # ---------- công cụ ----------
    def _set_tool(self, key):
        self._tool = key
        for k, b in self._tool_buttons.items():
            b.setChecked(k == key)

    def _set_width(self, w):
        self._width = w

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Chọn màu vẽ")
        if c.isValid():
            self._color = c.name()

    def _push_undo(self):
        self._undo.append(self.canvas.pm.copy())
        if len(self._undo) > 30:
            self._undo.pop(0)

    def _do_undo(self):
        if self._undo:
            self.canvas.set_pixmap(self._undo.pop())

    # ---------- hành động ----------
    def _save_local(self):
        path = self._save_fn(pixmap_to_png_bytes(self.canvas.pm), self.filename)
        self.saved_local.emit(str(path))
        QMessageBox.information(self, "Đã lưu", f"Đã lưu ảnh vào:\n{path}")

    def upload(self):
        if self._thread:
            return
        self.b_upload.setEnabled(False)
        self.b_upload.setText("Đang tải lên GitHub…")
        data = pixmap_to_png_bytes(self.canvas.pm)
        fname = self.filename

        self._worker = _UploadWorker(lambda: self._upload_fn(data, fname))
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_uploaded)
        self._worker.failed.connect(self._on_upload_failed)
        self._thread.start()

    def _finish_upload_ui(self):
        self.b_upload.setEnabled(True)
        self.b_upload.setText("Tải lên GitHub (Enter)")
        if self._thread:
            self._thread.quit()
            self._thread.wait(500)
            self._thread = None
            self._worker = None

    def _on_uploaded(self, result):
        self._finish_upload_ui()
        url = result.link(self.config.github.link_type)
        copy_text = format_link(self.config.github.copy_format, url)
        if self.config.github.auto_copy:
            _copy(copy_text)
        self.uploaded.emit(result)
        LinkDialog(url, copy_text, self).exec()

    def _on_upload_failed(self, msg):
        self._finish_upload_ui()
        QMessageBox.critical(self, "Upload thất bại", msg)

    # ---------- phím tắt ----------
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.upload()
        elif e.key() == Qt.Key_S and e.modifiers() & Qt.ControlModifier:
            self._save_local()
        elif e.key() == Qt.Key_C and e.modifiers() & Qt.ControlModifier:
            _copy_image(self.canvas.pm)
        elif e.key() == Qt.Key_Z and e.modifiers() & Qt.ControlModifier:
            self._do_undo()
        elif e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


def _copy_image(pm: QPixmap):
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.clipboard().setPixmap(pm)
