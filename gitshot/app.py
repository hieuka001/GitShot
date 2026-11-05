"""GitShot — cửa sổ chính dạng sidebar, giao diện Liquid Glass.

Trang: Trang chủ (nhóm chụp/quay) • Công cụ (màu, thước, OCR, ghép/tách ảnh,
thumbnail, hash, thư mục) • Lịch sử (lưới thumbnail) • Cài đặt (GitHub + chụp
+ tổ hợp phím tự thiết lập).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, QSize
from PySide6.QtGui import QAction, QColor, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import __version__
from .capture import (
    apply_rounded_corners, compute_capture_scale, grab_active_window,
    grab_fullscreen, grab_region, scrolling_capture,
)
from .color_picker import ColorPickerOverlay
from .config import AppConfig
from .editor import EditorWindow, pil_to_pixmap
from .github_uploader import GitHubUploader
from .history import History, HistoryItem
from .hotkeys_util import build_combo, find_conflicts, prettify, validate_combo
from .region_selector import MeasureOverlay, RegionSelector
from .tools_extra import (
    combine_images, file_hashes, make_thumbnail, ocr_image, split_image,
)
from .utils import format_link, make_filename

STYLE = """
/* ===== Liquid Glass — chiều sâu nhiều lớp: nền ambient, kính mờ, viền sáng, bóng đổ tầng ===== */
QMainWindow, QDialog { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0A0E1A, stop:0.45 #0C1522, stop:1 #141024);
    color: #E8EDF5; font-family: 'Segoe UI'; font-size: 13px; }
QFrame#sidebar { background: rgba(255,255,255,0.038); border-right: 1px solid rgba(255,255,255,0.09); }
QLabel#pageTitle { font-size: 18px; font-weight: 600; color: #FFFFFF; }
QLabel#subtitle { color: #93A1B5; font-size: 12px; }
QLabel#version { color: #66738A; font-size: 10px; }
QFrame#divider { background: rgba(255,255,255,0.09); max-height: 1px; }
QPushButton { background: rgba(255,255,255,0.06); color: #E8EDF5; border: 1px solid rgba(255,255,255,0.13); border-radius: 9px; padding: 7px 14px; }
QPushButton:hover { background: rgba(255,255,255,0.10); border-color: rgba(125,211,252,0.45); }
QPushButton#primaryBtn { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0284C7, stop:1 #6D28D9);
    color: #FFFFFF; font-weight: 600; border: 1px solid rgba(255,255,255,0.28); padding: 8px 18px; }
QPushButton#primaryBtn:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0EA5E9, stop:1 #7C3AED); }
QPushButton#navIcon { background: transparent; border: 1px solid transparent; border-radius: 12px; padding: 0; }
QPushButton#navIcon:hover { background: rgba(255,255,255,0.08); }
QPushButton#navIcon:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(2,132,199,0.42), stop:1 rgba(109,40,217,0.38));
    border-color: rgba(125,211,252,0.50); }
QPushButton#card { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(255,255,255,0.095), stop:1 rgba(255,255,255,0.045));
    border: 1px solid rgba(255,255,255,0.13); border-radius: 14px; padding: 13px 10px; font-size: 13px; font-weight: 500; color: #E2E9F4; }
QPushButton#card:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(255,255,255,0.14), stop:1 rgba(255,255,255,0.07));
    border-color: rgba(125,211,252,0.60); color: #FFFFFF; }
QGroupBox { background: rgba(255,255,255,0.028); border: 1px solid rgba(255,255,255,0.09); border-radius: 14px; margin-top: 14px; padding-top: 12px; font-weight: 600; color: #C9D4E4; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.14); border-radius: 9px; padding: 7px 10px; color: #EDF2FA; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: rgba(125,211,252,0.75); background: rgba(255,255,255,0.08); }
QLineEdit#hotkeyCapturing { border-color: #38BDF8; background: rgba(2,132,199,0.14); color: #CFEAFB; }
QListWidget { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.09); border-radius: 12px; }
QToolButton { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.13); border-radius: 9px; padding: 6px 11px; color: #E2E9F4; }
QToolButton:hover { border-color: rgba(125,211,252,0.45); }
QToolButton:checked { background: rgba(2,132,199,0.30); border-color: #38BDF8; color: #FFFFFF; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.16); border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.28); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#status { color: #93A9C4; font-size: 12px; }
QCheckBox { spacing: 8px; }
QToolTip { background: #1B2331; color: #E8EDF5; border: 1px solid rgba(255,255,255,0.16); padding: 5px 8px; }
"""


def asset_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "assets" / rel
    if p.exists():
        return p
    return Path(__file__).resolve().parent.parent / "assets" / rel


def icon_path() -> Path:
    return asset_path("icon.png")


def depth_shadow(widget, blur: int = 22, dy: int = 6, alpha: int = 95):
    """Bóng đổ mềm tạo chiều sâu giữa các lớp kính."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return widget


def _png_bytes(img: Image.Image) -> bytes:
    return _image_bytes(img, "png")


def _image_bytes(img: Image.Image, fmt: str = "png") -> bytes:
    """Mã hóa ảnh PIL theo định dạng cấu hình (png/jpg/webp)."""
    import io
    buf = io.BytesIO()
    fmt = (fmt or "png").lower()
    if fmt in ("jpg", "jpeg"):
        # quality 95 + subsampling 4:4:4: chữ trong ảnh chụp màn hình giữ nét
        # (mặc định 4:2:0 làm viền chữ bị lem màu)
        img.convert("RGB").save(buf, "JPEG", quality=95, subsampling=0)
    elif fmt == "webp":
        img.save(buf, "WEBP", quality=95)  # WebP giữ được kênh alpha (góc bo tròn)
    else:
        img.save(buf, "PNG")
    return buf.getvalue()


class _AsyncCall(QObject):
    """Chạy 1 hàm ở thread nền, báo kết quả về luồng giao diện qua signal."""
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


_LIVE_THREADS: list = []


class _Dispatcher(QObject):
    """Nhận kết quả ở LUỒNG GIAO DIỆN (nơi nó được tạo ra) rồi mới gọi callback
    của người dùng — callback chạm vào widget nên tuyệt đối không chạy ở
    thread nền."""

    def __init__(self, on_done, on_fail, cleanup):
        super().__init__()
        self._on_done, self._on_fail, self._cleanup = on_done, on_fail, cleanup

    def handle_done(self, result):
        try:
            if self._on_done:
                self._on_done(result)
        finally:
            self._cleanup()

    def handle_failed(self, msg):
        try:
            if self._on_fail:
                self._on_fail(msg)
        finally:
            self._cleanup()


def build_updater_script(new_file: str, target: str) -> str:
    """Script .bat thay exe: đợi app thoát (exe hết bị khóa) -> ghi đè ->
    mở lại bản mới -> tự xóa. App đang chạy không tự ghi đè được chính nó."""
    return (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        ":retry\r\n"
        f'copy /y "{new_file}" "{target}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto retry\r\n"
        ")\r\n"
        f'del "{new_file}" >nul 2>&1\r\n'
        f'start "" "{target}"\r\n'
        'del "%~f0"\r\n'
    )


def run_async(fn, on_done=None, on_fail=None):
    """Việc nặng (mạng, chụp cuộn, mã hóa) chạy ở thread riêng để giao diện
    không bao giờ bị đơ. Trả về QThread đang chạy."""
    worker = _AsyncCall(fn)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def _cleanup():
        thread.quit()
        thread.wait(2000)
        if pair in _LIVE_THREADS:
            _LIVE_THREADS.remove(pair)

    dispatcher = _Dispatcher(on_done, on_fail, _cleanup)
    # Giữ tham chiếu tới mọi thành phần tới khi xong việc — để worker rơi
    # khỏi scope là bị thu hồi bộ nhớ, thread chạy mà không có ai làm.
    pair = (thread, worker, dispatcher)
    _LIVE_THREADS.append(pair)
    worker.done.connect(dispatcher.handle_done)
    worker.failed.connect(dispatcher.handle_failed)
    thread.start()
    return thread


_QT_KEY_NAMES = {
    Qt.Key_Space: "space", Qt.Key_Tab: "tab", Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
    Qt.Key_Print: "print screen", Qt.Key_Insert: "insert", Qt.Key_Delete: "delete",
    Qt.Key_Home: "home", Qt.Key_End: "end", Qt.Key_PageUp: "page up", Qt.Key_PageDown: "page down",
    Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
    Qt.Key_Backspace: "backspace", Qt.Key_CapsLock: "caps lock",
    Qt.Key_Comma: ",", Qt.Key_Period: ".", Qt.Key_Slash: "/", Qt.Key_Semicolon: ";",
    Qt.Key_Apostrophe: "'", Qt.Key_BracketLeft: "[", Qt.Key_BracketRight: "]",
    Qt.Key_Minus: "-", Qt.Key_Equal: "=", Qt.Key_Backslash: "\\", Qt.Key_QuoteLeft: "`",
}
_MODIFIER_KEYS = {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta}


def _qt_key_name(key: int) -> str | None:
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key).lower()
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    if Qt.Key_F1 <= key <= Qt.Key_F35:
        return f"f{key - Qt.Key_F1 + 1}"
    return _QT_KEY_NAMES.get(key)


class HotkeyEdit(QLineEdit):
    """Ô tự thiết lập tổ hợp phím: bấm vào ô rồi nhấn tổ hợp phím mong muốn."""

    def __init__(self, combo: str = "", parent=None):
        super().__init__(parent)
        self.combo = (combo or "").strip().lower()
        self._capturing = False
        self._old = self.combo
        self.setReadOnly(True)
        self.setCursor(Qt.IBeamCursor)
        self._show_combo()
        self.setToolTip("Bấm vào ô rồi nhấn tổ hợp phím mới. Esc = hủy, để trống = không dùng phím tắt.")

    def _show_combo(self):
        self.setText(prettify(self.combo) if self.combo else "— chưa đặt (bấm để đặt) —")

    def clear_combo(self):
        self.combo = ""
        self._show_combo()

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._begin()

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self._begin()

    def _begin(self):
        if self._capturing:
            return
        self._capturing = True
        self._old = self.combo
        self.setObjectName("hotkeyCapturing")
        self.setStyleSheet("")  # ép Qt vẽ lại theo objectName mới
        self.setText("Đang chờ phím…")

    def _end(self):
        self._capturing = False
        self.setObjectName("")
        self.setStyleSheet("")
        self._show_combo()

    def keyPressEvent(self, e):
        if not self._capturing:
            return
        key = e.key()
        if key == Qt.Key_Escape:
            self.combo = self._old
            self._end()
            self.clearFocus()
            return
        mods = []
        m = e.modifiers()
        if m & Qt.ControlModifier:
            mods.append("ctrl")
        if m & Qt.AltModifier:
            mods.append("alt")
        if m & Qt.ShiftModifier:
            mods.append("shift")
        if m & Qt.MetaModifier:
            mods.append("windows")
        if key in _MODIFIER_KEYS:
            pretty = " + ".join(x.title() for x in mods) or "⌨"
            self.setText(f"{pretty} + …")
            return
        name = _qt_key_name(key)
        if name is None:
            self.setText("Phím không được hỗ trợ")
            return
        combo = build_combo(mods, name)
        err = validate_combo(combo)
        if err:
            self.setText(err)
            return
        self.combo = combo
        self._end()
        self.clearFocus()


class SettingsPanel(QWidget):
    saved = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        gh = config.github
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        g1 = QGroupBox("GitHub")
        f = QGridLayout(g1)
        f.addWidget(QLabel("Token (Personal Access Token):"), 0, 0)
        self.e_token = QLineEdit(gh.token)
        self.e_token.setEchoMode(QLineEdit.Password)
        f.addWidget(self.e_token, 0, 1)
        b_show = QPushButton("Hiện")
        b_show.setCheckable(True)
        b_show.toggled.connect(lambda on: self.e_token.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        f.addWidget(b_show, 0, 2)
        f.addWidget(QLabel("Tài khoản (để trống = theo token):"), 1, 0)
        self.e_owner = QLineEdit(gh.owner); f.addWidget(self.e_owner, 1, 1)
        f.addWidget(QLabel("Kho chứa ảnh:"), 2, 0)
        self.e_repo = QLineEdit(gh.repo); f.addWidget(self.e_repo, 2, 1)
        f.addWidget(QLabel("Nhánh:"), 3, 0)
        self.e_branch = QLineEdit(gh.branch); f.addWidget(self.e_branch, 3, 1)
        f.addWidget(QLabel("Mẫu thư mục:"), 4, 0)
        self.e_folder = QLineEdit(gh.folder_pattern); f.addWidget(self.e_folder, 4, 1)
        f.addWidget(QLabel("Kiểu liên kết:"), 5, 0)
        self.c_link = QComboBox(); self.c_link.addItems(["raw", "cdn"]); self.c_link.setCurrentText(gh.link_type)
        f.addWidget(self.c_link, 5, 1)
        f.addWidget(QLabel("Định dạng sao chép:"), 6, 0)
        self.c_fmt = QComboBox(); self.c_fmt.addItems(["link", "markdown", "html"]); self.c_fmt.setCurrentText(gh.copy_format)
        f.addWidget(self.c_fmt, 6, 1)
        row = QHBoxLayout()
        b_test = QPushButton("Kiểm tra kết nối"); b_test.clicked.connect(self._test)
        b_repo = QPushButton("Tạo kho chứa ảnh"); b_repo.clicked.connect(self._create_repo)
        row.addWidget(b_test); row.addWidget(b_repo); row.addStretch()
        f.addLayout(row, 7, 0, 1, 3)
        lay.addWidget(g1)

        g2 = QGroupBox("Chụp")
        v = QVBoxLayout(g2)
        self.chk_round = QCheckBox("Bo góc tròn cho ảnh chụp cửa sổ")
        self.chk_round.setChecked(config.rounded_corners)
        rowr = QHBoxLayout()
        rowr.addWidget(QLabel("Bán kính bo góc:"))
        self.s_radius = QSpinBox(); self.s_radius.setRange(0, 30); self.s_radius.setValue(config.corner_radius)
        rowr.addWidget(self.s_radius); rowr.addStretch()
        self.chk_copy = QCheckBox("Tự động sao chép liên kết sau khi tải lên"); self.chk_copy.setChecked(gh.auto_copy)
        self.chk_create = QCheckBox("Tự tạo kho chứa ảnh nếu chưa có"); self.chk_create.setChecked(gh.auto_create_repo)
        self.chk_local = QCheckBox("Lưu bản sao trong thư mục Pictures/GitShot"); self.chk_local.setChecked(config.save_local_copy)
        self.chk_quick = QCheckBox("Chụp xong tải lên ngay (không mở trình sửa ảnh)")
        self.chk_quick.setChecked(config.quick_upload)
        rowf = QHBoxLayout()
        rowf.addWidget(QLabel("Định dạng ảnh:"))
        self.c_imgfmt = QComboBox(); self.c_imgfmt.addItems(["png", "jpg", "webp"])
        self.c_imgfmt.setCurrentText(config.image_format if config.image_format in ("png", "jpg", "webp") else "png")
        rowf.addWidget(self.c_imgfmt); rowf.addStretch()
        v.addWidget(self.chk_round); v.addLayout(rowr)
        v.addWidget(self.chk_copy); v.addWidget(self.chk_create); v.addWidget(self.chk_local)
        v.addWidget(self.chk_quick); v.addLayout(rowf)
        lay.addWidget(g2)

        g3 = QGroupBox("Phím tắt")
        f3 = QGridLayout(g3)
        self.hk_edits: dict[str, HotkeyEdit] = {}
        hk_actions = [
            ("region", "Chụp vùng"),
            ("fullscreen", "Toàn màn hình"),
            ("window", "Cửa sổ hiện tại"),
            ("scrolling", "Chụp cuộn"),
            ("record", "Quay MP4"),
            ("gif", "Quay GIF"),
            ("last_region", "Chụp lại vùng cũ"),
            ("color_picker", "Lấy mã màu"),
        ]
        for i, (action, label) in enumerate(hk_actions, start=0):
            f3.addWidget(QLabel(label), i, 0)
            edit = HotkeyEdit(getattr(config.hotkeys, action, ""))
            self.hk_edits[action] = edit
            f3.addWidget(edit, i, 1)
            b_clear = QPushButton("✕")
            b_clear.setFixedWidth(34)
            b_clear.clicked.connect(lambda _=False, ed=edit: ed.clear_combo())
            f3.addWidget(b_clear, i, 2)
        lay.addWidget(g3)

        b_save = QPushButton("Lưu cài đặt")
        b_save.setObjectName("primaryBtn")
        b_save.clicked.connect(self._save)
        lay.addWidget(b_save)
        lay.addStretch()

    HOTKEY_LABELS = {
        "region": "Chụp vùng", "fullscreen": "Toàn màn hình", "window": "Cửa sổ",
        "scrolling": "Chụp cuộn", "record": "Quay MP4", "gif": "Quay GIF",
        "last_region": "Chụp lại vùng cũ", "color_picker": "Lấy mã màu",
    }

    def _hotkey_mapping(self) -> dict[str, str]:
        return {a: ed.combo for a, ed in self.hk_edits.items()}

    def _apply(self, cfg: AppConfig):
        for action, combo in self._hotkey_mapping().items():
            if hasattr(cfg.hotkeys, action):
                setattr(cfg.hotkeys, action, combo)
        cfg.github.token = self.e_token.text().strip()
        cfg.github.owner = self.e_owner.text().strip()
        cfg.github.repo = self.e_repo.text().strip() or "gitshot-uploads"
        cfg.github.branch = self.e_branch.text().strip() or "main"
        cfg.github.folder_pattern = self.e_folder.text().strip()
        cfg.github.link_type = self.c_link.currentText()
        cfg.github.copy_format = self.c_fmt.currentText()
        cfg.github.auto_copy = self.chk_copy.isChecked()
        cfg.github.auto_create_repo = self.chk_create.isChecked()
        cfg.rounded_corners = self.chk_round.isChecked()
        cfg.corner_radius = self.s_radius.value()
        cfg.save_local_copy = self.chk_local.isChecked()
        cfg.quick_upload = self.chk_quick.isChecked()
        cfg.image_format = self.c_imgfmt.currentText()

    def _uploader(self) -> GitHubUploader:
        tmp = AppConfig()
        self._apply(tmp)
        return GitHubUploader(tmp.github.token)

    def _test(self):
        up = self._uploader()

        def ok(login):
            QMessageBox.information(self, "Kết nối OK", f"Token hợp lệ — tài khoản: {login}")
            if not self.e_owner.text().strip():
                self.e_owner.setText(login)

        run_async(up.whoami, on_done=ok,
                  on_fail=lambda m: QMessageBox.critical(self, "Lỗi kết nối", m))

    def _create_repo(self):
        up = self._uploader()
        repo_name = self.e_repo.text().strip() or "gitshot-uploads"

        def work():
            owner = self.e_owner.text().strip() or up.whoami()
            up.ensure_repo(owner, repo_name)
            return owner

        run_async(work,
                  on_done=lambda owner: QMessageBox.information(
                      self, "Hoàn tất", f"Kho {owner}/{repo_name} đã sẵn sàng."),
                  on_fail=lambda m: QMessageBox.critical(self, "Lỗi", m))

    def _save(self):
        conflicts = find_conflicts(self._hotkey_mapping())
        if conflicts:
            detail = "\n".join(
                f"• {prettify(c)}: đang dùng cho " + ", ".join(self.HOTKEY_LABELS.get(a, a) for a in acts)
                for c, acts in conflicts.items())
            QMessageBox.warning(self, "Trùng tổ hợp phím",
                                f"Các tổ hợp sau bị trùng nhau, hãy đổi trước khi lưu:\n{detail}")
            return
        self._apply(self.config)
        self.config.save()
        self.saved.emit()
        QMessageBox.information(self, "Cài đặt", "Đã lưu. Phím tắt mới có hiệu lực ngay.")


class RecordControl(QWidget):
    stop_clicked = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        lay = QHBoxLayout(self)
        self.label = QLabel("Đang quay — 00:00")
        lay.addWidget(self.label)
        b = QPushButton("Dừng và lưu")
        b.setObjectName("primaryBtn")
        b.clicked.connect(self.stop_clicked.emit)
        lay.addWidget(b)
        self._sec = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self.move(30, 30)

    def _tick(self):
        self._sec += 1
        self.label.setText(f"Đang quay — {self._sec // 60:02d}:{self._sec % 60:02d}")


class GitShotApp(QObject):
    hotkey_fired = Signal(str)

    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.history = History()
        self._editors: list[EditorWindow] = []
        self._selector = None
        self._overlay = None
        self._recorder = None
        self._record_ctrl: RecordControl | None = None
        self._record_kind = "mp4"
        self._owner_cache = self.config.github.owner
        self._ensured_repos: set = set()
        self._auto = {"timer": None, "left": 0, "bbox": None}
        self.hotkey_fired.connect(self._on_hotkey)

        self.window = MainWindow(self)
        self._hk_registered = False
        # Lưu cài đặt xong là áp dụng phím tắt mới ngay (không cần khởi động lại)
        self.window.settings_panel.saved.connect(lambda: self._register_hotkeys())
        self.window.settings_panel.saved.connect(self._rebuild_tray)
        self._build_tray()
        self._register_hotkeys()
        self._cap_scale = (1.0, 1.0)
        self._virt_origin = (0, 0)
        QTimer.singleShot(900, self._probe_capture_scale)  # hiệu chuẩn tỉ lệ pixel thật
        QTimer.singleShot(6000, self._check_update)  # kiểm tra bản mới sau khi mở 6s

    def _check_update(self, manual: bool = False):
        """Hỏi GitHub Releases xem có bản GitShot mới hơn bản đang chạy.

        Có bản mới + đang chạy bản .exe: hỏi ngay trong app, người dùng bấm
        "Cập nhật ngay" là app tự tải, tự thay exe và mở lại (xem
        _start_self_update). Chạy từ mã nguồn: chỉ mở trang release.
        """
        from . import __version__

        def fetch():
            import json as _json
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/repos/hieuka001/GitShot/releases/latest",
                headers={"User-Agent": "GitShot", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return _json.loads(r.read().decode("utf-8"))

        def done(data):
            from .utils import is_newer_version
            tag = (data or {}).get("tag_name", "")
            if not (tag and is_newer_version(tag, __version__)):
                if manual:
                    QMessageBox.information(self.window, "Cập nhật",
                                            f"Đang dùng bản mới nhất ({__version__}).")
                return
            url = ""
            for asset in (data or {}).get("assets", []):
                if asset.get("name") == "GitShot.exe":
                    url = asset.get("browser_download_url", "")
                    break
            if not url:
                url = f"https://github.com/hieuka001/GitShot/releases/download/{tag}/GitShot.exe"
            self.status(f"Có bản GitShot mới {tag}.")
            if not getattr(sys, "frozen", False):
                self._tray_msg("GitShot", f"Đã có bản mới {tag} — mở menu khay để tới trang tải.")
                menu = getattr(self, "_tray_menu", None)
                if menu is not None:
                    page = (data or {}).get("html_url", "")
                    act = menu.addAction(f"Tải bản mới {tag}")
                    act.triggered.connect(lambda: __import__("webbrowser").open(page))
                return
            box = QMessageBox(self.window)
            box.setWindowTitle("Cập nhật GitShot")
            box.setText(f"Đã có bản mới {tag} (đang dùng {__version__}).\n"
                        "Cập nhật ngay? App sẽ tự tải, thay bản mới và mở lại.")
            b_now = box.addButton("Cập nhật ngay", QMessageBox.AcceptRole)
            box.addButton("Để sau", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == b_now:
                self._start_self_update(url, tag)

        run_async(fetch, on_done=done,
                  on_fail=(lambda m: QMessageBox.critical(self.window, "Cập nhật", m)
                           if manual else None))

    def _start_self_update(self, url: str, tag: str):
        """Tải exe mới về thư mục cấu hình, chạy script thay thế rồi thoát app
        để script ghi đè exe đang chạy và mở lại bản mới."""
        from .config import config_dir
        target = Path(sys.executable)
        new_file = config_dir() / f"GitShot-{tag}.exe"
        self.status(f"Đang tải bản {tag}…")

        def download():
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "GitShot"})
            with urllib.request.urlopen(req, timeout=300) as r, open(new_file, "wb") as f:
                import shutil
                shutil.copyfileobj(r, f, 1 << 20)
            if new_file.stat().st_size < 1_000_000:
                raise RuntimeError("Tệp tải về quá nhỏ — tải chưa hoàn tất.")
            return str(new_file)

        def ready(_):
            bat = config_dir() / "gitshot-update.bat"
            bat.write_text(build_updater_script(str(new_file), str(target)),
                           encoding="utf-8")
            import subprocess
            subprocess.Popen(["cmd", "/c", str(bat)],
                             creationflags=0x00000008 | 0x00000200,  # DETACHED + NEW GROUP
                             close_fds=True)
            self.status("Đã tải xong — đang khởi động lại vào bản mới…")
            QTimer.singleShot(600, QApplication.quit)

        run_async(download, on_done=ready,
                  on_fail=lambda m: QMessageBox.critical(self.window, "Cập nhật thất bại", m))

    # ---------- GitHub ----------
    def uploader(self) -> GitHubUploader:
        return GitHubUploader(self.config.github.token)

    def resolve_owner(self, up: GitHubUploader) -> str:
        if not self._owner_cache:
            self._owner_cache = up.whoami()
            self.config.github.owner = self._owner_cache
            self.config.save()
        return self._owner_cache

    def upload_bytes(self, data: bytes, filename: str):
        gh = self.config.github
        up = self.uploader()
        owner = self.resolve_owner(up)
        # Kiểm tra/tạo repo chỉ cần làm 1 lần cho mỗi (owner, repo) trong phiên
        key = (owner, gh.repo)
        auto_create = gh.auto_create_repo and key not in self._ensured_repos
        result = up.upload_bytes(
            data, filename, owner=owner, repo=gh.repo, branch=gh.branch,
            folder_pattern=gh.folder_pattern, auto_create_repo=auto_create,
        )
        self._ensured_repos.add(key)
        return result

    def save_local(self, data: bytes, filename: str) -> Path:
        p = self.config.pictures_folder() / filename
        p.write_bytes(data)
        return p

    def status(self, msg: str):
        self.window.set_status(msg)

    # ---------- Luồng chụp ----------
    def _after_shot(self, img: Image.Image, kind: str = "image", rounded: bool = False):
        if rounded and self.config.rounded_corners:
            img = apply_rounded_corners(img, self.config.corner_radius)
        fmt = (self.config.image_format or "png").lower()
        filename = make_filename(ext=fmt)
        buf = _image_bytes(img, fmt)
        # Lịch sử LUÔN có mục cho ảnh này (kể cả khi tắt lưu bản sao local) —
        # bản cũ tắt lưu local là upload xong không gắn được link vào lịch sử.
        local_path = ""
        if self.config.save_local_copy:
            local_path = str(self.save_local(buf, filename))
        self.history.add(HistoryItem(filename, local_path, History.now_iso(), kind=kind, size=len(buf)))
        self.window.refresh_history()
        if self.config.quick_upload:
            # Chế độ tải lên ngay: không mở trình sửa, Enter ngầm
            self.status("Đang tải ảnh lên GitHub…")
            run_async(lambda: self.upload_bytes(buf, filename),
                      on_done=lambda r, fn=filename: self._on_uploaded(r, fn),
                      on_fail=lambda m: self.status(f"Tải lên thất bại: {m}"))
            return
        if not self.config.open_editor_after_capture:
            self.status(f"Đã chụp: {filename}")
            return
        editor = EditorWindow(img, filename, self.config, self.upload_bytes, self.save_local)
        editor.uploaded.connect(lambda r, fn=filename: self._on_uploaded(r, fn))
        editor.destroyed.connect(
            lambda *_: self._editors.remove(editor) if editor in self._editors else None)
        editor.show()
        self._editors.append(editor)
        self.status(f"Đã chụp: {filename}")

    def _on_uploaded(self, result, filename: str):
        url = result.link(self.config.github.link_type)
        self.history.mark_uploaded_by_filename(filename, url)
        self.window.refresh_history()
        self._tray_msg("GitShot", "Đã tải lên. Liên kết đã được sao chép.")
        self.status(f"Đã tải lên GitHub: {url}")

    def capture_fullscreen(self):
        was_visible = self.window.isVisible()
        self.window.hide()
        def go():
            self._after_shot(grab_fullscreen())
            if was_visible:
                self.window.show()
        QTimer.singleShot(350, go)

    def capture_window(self):
        self._after_shot(grab_active_window(), rounded=True)

    def capture_region(self):
        self._select_region(lambda bbox, snapped: QTimer.singleShot(
            120, lambda: self._shot_region(bbox, snapped)))

    def _shot_region(self, bbox, snapped: bool):
        self.config.last_region = list(bbox)
        self.config.save()
        self._after_shot(grab_region(bbox), rounded=snapped)

    def capture_last_region(self):
        lr = self.config.last_region
        if lr and len(lr) == 4:
            self._after_shot(grab_region(tuple(lr)))
        else:
            QMessageBox.information(self.window, "Chụp lại vùng cũ",
                                    "Chưa có vùng chụp trước đó.")

    def capture_scrolling(self):
        def go(bbox, snapped):
            self.config.last_region = list(bbox)
            self.config.save()
            self.status("Đang chụp cuộn…")
            # Chụp cuộn mất vài giây (cuộn + ghép) — chạy thread nền, app không đơ
            run_async(lambda: scrolling_capture(bbox),
                      on_done=lambda img: self._after_shot(img),
                      on_fail=lambda m: QMessageBox.critical(self.window, "Chụp cuộn", m))
        self._select_region(go)

    def capture_delayed(self, seconds: int = 3):
        self.status(f"Chụp vùng sau {seconds} giây")
        QTimer.singleShot(seconds * 1000, self.capture_region)

    def capture_auto(self):
        interval, ok = QInputDialog.getInt(self.window, "Chụp tự động",
                                           "Chu kỳ chụp (giây):", 10, 2, 3600)
        if not ok:
            return
        count, ok = QInputDialog.getInt(self.window, "Chụp tự động",
                                        "Số ảnh (toàn màn hình, tự động tải lên):", 5, 1, 200)
        if not ok:
            return
        self._auto["left"] = count
        if self._auto["timer"]:
            self._auto["timer"].stop()
        timer = QTimer(self)
        timer.timeout.connect(self._auto_tick)
        self._auto["timer"] = timer
        timer.start(interval * 1000)
        self.status(f"Chụp tự động: {count} ảnh, chu kỳ {interval} giây")

    def _auto_tick(self):
        if self._auto["left"] <= 0:
            self._auto["timer"].stop()
            self.status("Chụp tự động: hoàn tất.")
            return
        self._auto["left"] -= 1
        img = grab_fullscreen()
        filename = make_filename(ext=(self.config.image_format or "png").lower())
        data = _image_bytes(img, self.config.image_format)
        path = self.save_local(data, filename)
        self.history.add(HistoryItem(filename, str(path), History.now_iso(), size=len(data)))
        self.window.refresh_history()

        def ok(result):
            url = result.link(self.config.github.link_type)
            self.history.mark_uploaded(str(path), url)
            if self.config.github.auto_copy:
                QApplication.clipboard().setText(format_link(self.config.github.copy_format, url))
            self.status(f"Đã chụp và tải lên: {url}")
            self.window.refresh_history()

        run_async(lambda: self.upload_bytes(data, filename), on_done=ok,
                  on_fail=lambda m: self.status(f"Chụp tự động: lỗi tải lên: {m}"))

    def capture_from_clipboard(self):
        cb = QApplication.clipboard()
        img = cb.image()
        if img.isNull():
            QMessageBox.information(self.window, "Clipboard trống",
                                    "Clipboard hiện không chứa ảnh.")
            return
        buf = _qt_image_to_pil(img)
        self._after_shot(buf)

    def open_image_file(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Mở ảnh để sửa / upload",
                                              "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._after_shot(Image.open(path))

    def _probe_capture_scale(self):
        """Đo tỉ lệ pixel thật / tọa độ Qt bằng cách chụp thử toàn màn hình
        1 lần lúc mở app và so với virtualGeometry. Máy scaling 100% -> 1.0
        (không đổi hành vi); máy 125–150% mà Qt trả tọa độ logic -> tỉ lệ
        > 1, vùng chụp được phóng đúng về pixel thật nên nét như chụp gốc."""
        def probe():
            return grab_fullscreen().size

        def done(size):
            from PySide6.QtGui import QGuiApplication
            vg = QGuiApplication.primaryScreen().virtualGeometry()
            self._cap_scale = compute_capture_scale(size[0], size[1], vg.width(), vg.height())
            self._virt_origin = (vg.left(), vg.top())
            import logging
            logging.info("Hiệu chuẩn chụp: ảnh thật %s, khung Qt %sx%s, tỉ lệ %s",
                         size, vg.width(), vg.height(), self._cap_scale)

        run_async(probe, on_done=done, on_fail=lambda m: None)

    def _to_physical_bbox(self, bbox):
        sx, sy = getattr(self, "_cap_scale", (1.0, 1.0))
        if (sx, sy) == (1.0, 1.0):
            return bbox
        ox, oy = getattr(self, "_virt_origin", (0, 0))
        x1, y1, x2, y2 = bbox
        return (round(ox + (x1 - ox) * sx), round(oy + (y1 - oy) * sy),
                round(ox + (x2 - ox) * sx), round(oy + (y2 - oy) * sy))

    def _select_region(self, callback):
        sel = RegionSelector()
        self._selector = sel

        def on_selected(bbox, snapped):
            self._selector = None
            callback(self._to_physical_bbox(bbox), snapped)

        def on_cancel():
            self._selector = None

        sel.selected.connect(on_selected)
        sel.cancelled.connect(on_cancel)
        sel.show()
        sel.activateWindow()

    # ---------- Quay màn hình ----------
    def record_screen(self, kind: str = "mp4"):
        self._record_kind = kind

        def go(bbox, snapped=False):
            from .recorder import ScreenRecorder
            ext = "gif" if kind == "gif" else "mp4"
            filename = make_filename(prefix="record", ext=ext)
            path = self.config.pictures_folder() / filename
            self._record_path = path
            self._record_filename = filename
            self._recorder = ScreenRecorder(bbox, fps=self.config.record_fps if kind == "mp4" else 10)
            self._recorder.start(path)
            self._record_ctrl = RecordControl()
            self._record_ctrl.stop_clicked.connect(self._stop_record)
            self._record_ctrl.show()

        box = QMessageBox(self.window)
        box.setWindowTitle("Quay màn hình")
        box.setText("Chọn phạm vi quay:")
        b_region = box.addButton("Chọn vùng", QMessageBox.AcceptRole)
        b_full = box.addButton("Toàn màn hình", QMessageBox.AcceptRole)
        box.addButton("Hủy", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == b_region:
            self._select_region(go)
        elif box.clickedButton() == b_full:
            go(None)

    def _stop_record(self):
        if self._record_ctrl:
            self._record_ctrl.close()
            self._record_ctrl = None
        if not self._recorder:
            return
        filename = getattr(self, "_record_filename", make_filename(prefix="record", ext="mp4"))
        try:
            path = self._recorder.stop_and_save()
        except Exception as e:
            QMessageBox.critical(self.window, "Quay thất bại", str(e))
            self._recorder = None
            return
        self._recorder = None
        data = path.read_bytes()
        kind = "gif" if path.suffix.lower() == ".gif" else "mp4"
        self.history.add(HistoryItem(filename, str(path), History.now_iso(), kind=kind, size=len(data)))
        self.window.refresh_history()
        box = QMessageBox(self.window)
        box.setWindowTitle("Đã quay xong")
        box.setText(f"Đã lưu: {path}\n\nTải lên GitHub? ({len(data)//1024} KB)")
        b_up = box.addButton("Tải lên GitHub", QMessageBox.AcceptRole)
        box.addButton("Để sau", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == b_up:
            self.status("Đang tải video lên GitHub…")

            def ok(result):
                url = result.link(self.config.github.link_type)
                QApplication.clipboard().setText(format_link(self.config.github.copy_format, url))
                self.history.mark_uploaded(str(path), url)
                self.window.refresh_history()
                QMessageBox.information(self.window, "Hoàn tất", f"Liên kết video (đã sao chép):\n{url}")

            run_async(lambda: self.upload_bytes(data, filename), on_done=ok,
                      on_fail=lambda m: QMessageBox.critical(self.window, "Upload lỗi", m))

    # ---------- Công cụ ----------
    def tool_color_picker(self):
        self.window.hide()
        def go():
            img = grab_fullscreen()
            overlay = ColorPickerOverlay(pil_to_pixmap(img), img)
            self._overlay = overlay
            overlay.picked.connect(lambda hexcode, rgb: (
                QApplication.clipboard().setText(hexcode),
                self.status(f"Đã sao chép mã màu {hexcode} (RGB {rgb[0]}, {rgb[1]}, {rgb[2]})"),
                self.window.show(),
            ))
            overlay.cancelled.connect(lambda: self.window.show())
            overlay.show()
            overlay.activateWindow()
        QTimer.singleShot(300, go)

    def tool_ruler(self):
        overlay = MeasureOverlay()
        self._overlay = overlay
        overlay.show()
        overlay.activateWindow()

    def tool_ocr(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Chọn ảnh để trích chữ (OCR)",
                                              "", "Ảnh (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        try:
            text = ocr_image(Image.open(path))
        except Exception as e:
            QMessageBox.critical(self.window, "OCR", str(e))
            return
        dlg = _TextResultDialog("Chữ trích từ ảnh", text or "(Không đọc được chữ nào)", self.window)
        dlg.exec()

    def tool_combine(self):
        paths, _ = QFileDialog.getOpenFileNames(self.window, "Chọn nhiều ảnh để ghép",
                                                "", "Ảnh (*.png *.jpg *.jpeg *.bmp)")
        if len(paths) < 2:
            return
        direction, ok = QInputDialog.getItem(self.window, "Ghép ảnh", "Hướng ghép:",
                                             ["vertical", "horizontal"], 0, False)
        if not ok:
            return
        merged = combine_images([Image.open(p) for p in paths], direction)
        self._after_shot(merged)

    def tool_split(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Chọn ảnh để tách",
                                              "", "Ảnh (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        rows, ok = QInputDialog.getInt(self.window, "Tách ảnh", "Số hàng:", 2, 1, 20)
        if not ok:
            return
        cols, ok = QInputDialog.getInt(self.window, "Tách ảnh", "Số cột:", 2, 1, 20)
        if not ok:
            return
        parts = split_image(Image.open(path), rows, cols)
        stem = Path(path).stem
        saved = []
        for i, part in enumerate(parts, 1):
            fn = f"{stem}_part{i:02d}.png"
            data = _png_bytes(part)
            p = self.save_local(data, fn)
            self.history.add(HistoryItem(fn, str(p), History.now_iso(), size=len(data)))
            saved.append(fn)
        self.window.refresh_history()
        QMessageBox.information(self.window, "Đã tách ảnh",
                                f"Đã tạo {len(parts)} ảnh con trong Pictures/GitShot:\n" + "\n".join(saved[:10]))

    def tool_thumbnail(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Tạo ảnh thu nhỏ",
                                              "", "Ảnh (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        side, ok = QInputDialog.getInt(self.window, "Ảnh thu nhỏ", "Cạnh dài nhất (px):", 800, 50, 4000)
        if not ok:
            return
        out = make_thumbnail(Image.open(path), side)
        self._after_shot(out)

    def tool_hash(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Chọn file để kiểm tra hash", "", "Mọi file (*.*)")
        if not path:
            return
        h = file_hashes(Path(path))
        text = f"File: {path}\n\nMD5:    {h['md5']}\nSHA256: {h['sha256']}"
        QApplication.clipboard().setText(h["sha256"])
        _TextResultDialog("Hash của file (SHA256 đã copy)", text, self.window).exec()

    def tool_open_folder(self):
        folder = self.config.pictures_folder()
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(folder)])

    # ---------- Tray + hotkey ----------
    def _tray_msg(self, title, msg):
        if hasattr(self, "tray") and self.tray:
            self.tray.showMessage(title, msg)

    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        ic = QIcon(str(icon_path()))
        self.tray = QSystemTrayIcon(ic, self.window)
        menu = QMenu()
        self._tray_menu = menu
        for text, fn in [
            (f"Chụp vùng ({prettify(self.config.hotkeys.region)})", self.capture_region),
            ("Toàn màn hình", self.capture_fullscreen),
            ("Cửa sổ hiện tại", self.capture_window),
            ("Chụp lại vùng cũ", self.capture_last_region),
            ("Chụp cuộn", self.capture_scrolling),
            ("Quay MP4", lambda: self.record_screen("mp4")),
            ("Quay GIF", lambda: self.record_screen("gif")),
            ("Lấy mã màu", self.tool_color_picker),
            ("Thước đo", self.tool_ruler),
        ]:
            a = QAction(text, menu); a.triggered.connect(fn); menu.addAction(a)
        menu.addSeparator()
        a_show = QAction("Mở GitShot", menu); a_show.triggered.connect(self.window.show); menu.addAction(a_show)
        a_upd = QAction("Kiểm tra bản mới", menu)
        a_upd.triggered.connect(lambda: self._check_update(manual=True)); menu.addAction(a_upd)
        a_quit = QAction("Thoát", menu); a_quit.triggered.connect(QApplication.quit); menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.window.show() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _register_hotkeys(self):
        try:
            import keyboard
        except Exception:
            return
        if self._hk_registered:
            try:
                keyboard.remove_all_hotkeys()
            except Exception:
                pass
            self._hk_registered = False
        hk = self.config.hotkeys
        pairs = [
            (hk.region, "region"), (hk.fullscreen, "fullscreen"), (hk.window, "window"),
            (hk.scrolling, "scrolling"), (hk.record, "record"), (hk.gif, "gif"),
            (hk.last_region, "last_region"), (hk.color_picker, "color_picker"),
        ]
        failed = []
        for combo, name in pairs:
            if not combo:
                continue
            if validate_combo(combo):
                failed.append(combo)
                continue
            try:
                keyboard.add_hotkey(combo, lambda n=name: self.hotkey_fired.emit(n), suppress=False)
                self._hk_registered = True
            except Exception:
                failed.append(combo)
        if failed:
            # Không nuốt im lặng nữa: báo rõ tổ hợp nào không đăng ký được
            self.status("Không đăng ký được phím tắt: "
                        + ", ".join(prettify(c) for c in failed)
                        + " — đổi sang tổ hợp khác trong Cài đặt.")

    def _rebuild_tray(self):
        if getattr(self, "tray", None):
            self.tray.hide()
            self.tray = None
        self._build_tray()

    def _on_hotkey(self, name: str):
        {
            "region": self.capture_region,
            "fullscreen": self.capture_fullscreen,
            "window": self.capture_window,
            "scrolling": self.capture_scrolling,
            "record": lambda: self.record_screen("mp4"),
            "gif": lambda: self.record_screen("gif"),
            "last_region": self.capture_last_region,
            "color_picker": self.tool_color_picker,
        }.get(name, lambda: None)()


def _qt_image_to_pil(qimg) -> Image.Image:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    qimg.save(buf, "PNG")
    import io
    return Image.open(io.BytesIO(bytes(ba))).convert("RGB")


class _TextResultDialog(QMessageBox):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(text[:4000])
        b = QPushButton("Sao chép tất cả")
        self.addButton(b, QMessageBox.ActionRole)
        b.clicked.connect(lambda: QApplication.clipboard().setText(text))
        self.addButton(QPushButton("Đóng"), QMessageBox.AcceptRole)


class MainWindow(QMainWindow):
    def __init__(self, app: GitShotApp):
        super().__init__()
        self.app_ref = app
        self.setWindowTitle("GitShot")
        self.setAcceptDrops(True)  # kéo-thả file ảnh vào cửa sổ để mở sửa/tải lên
        self.resize(1020, 680)
        ic = icon_path()
        if ic.exists():
            self.setWindowIcon(QIcon(str(ic)))

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- Sidebar dạng icon -----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(68)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(11, 14, 11, 12)
        sb.setSpacing(8)
        ic = icon_path()
        if ic.exists():
            mark = QLabel()
            mark.setPixmap(QPixmap(str(ic)).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            mark.setAlignment(Qt.AlignCenter)
            mark.setToolTip("GitShot")
            sb.addWidget(mark)
        sb.addSpacing(10)
        self._nav_buttons = {}
        for key, icon_name, tip in [("home", "home", "Trang chủ"), ("tools", "tools", "Công cụ"),
                                    ("history", "history", "Lịch sử"), ("settings", "settings", "Cài đặt")]:
            b = QPushButton()
            b.setObjectName("navIcon")
            b.setCheckable(True)
            b.setFixedSize(46, 46)
            ip = asset_path(f"icons/{icon_name}.png")
            if ip.exists():
                b.setIcon(QIcon(str(ip)))
                b.setIconSize(QSize(22, 22))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self._nav_buttons[key] = b
            sb.addWidget(b, 0, Qt.AlignHCenter)
        sb.addStretch()
        self.chip = QLabel("●")
        self.chip.setAlignment(Qt.AlignCenter)
        sb.addWidget(self.chip)
        ver = QLabel(__version__)
        ver.setObjectName("version")
        ver.setAlignment(Qt.AlignCenter)
        sb.addWidget(ver)
        root.addWidget(sidebar)

        # ----- Nội dung -----
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 14, 16, 10)
        self.stack = QStackedWidget()
        rv.addWidget(self.stack, 1)
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        rv.addWidget(self.status_label)
        root.addWidget(right, 1)
        self.setCentralWidget(central)

        self._hk_cards: dict[str, tuple] = {}
        self._build_home_page(app)
        self._build_tools_page(app)
        self._build_history_page()
        self._build_settings_page(app)
        self.show_page("home")
        self.refresh_history()
        self.refresh_hotkey_labels()
        self._refresh_chip()

    # ----- Trang chủ -----
    def _card_grid(self, items, cols=4):
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, item in enumerate(items):
            label, fn = item[0], item[1]
            action = item[2] if len(item) > 2 else None
            fallback = item[3] if len(item) > 3 else ""
            b = QPushButton(label)
            b.setObjectName("card")
            b.setMinimumHeight(86)
            b.clicked.connect(fn)
            depth_shadow(b)
            if action:
                self._hk_cards[action] = (b, label, fallback)
            grid.addWidget(b, i // cols, i % cols)
        return grid

    def refresh_hotkey_labels(self):
        """Cập nhật tổ hợp phím hiển thị trên các thẻ theo cài đặt hiện tại."""
        hk = self.app_ref.config.hotkeys
        for action, (b, base, fallback) in self._hk_cards.items():
            combo = getattr(hk, action, "")
            detail = prettify(combo) if combo else fallback
            b.setText(f"{base}\n{detail}" if detail else base)

    def _page_header(self, title: str, app=None) -> QHBoxLayout:
        row = QHBoxLayout()
        t = QLabel(title)
        t.setObjectName("pageTitle")
        row.addWidget(t)
        row.addStretch()
        if app is not None:
            b = QPushButton("Chụp vùng")
            b.setObjectName("primaryBtn")
            b.clicked.connect(app.capture_region)
            row.addWidget(b)
        return row

    def _build_home_page(self, app):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addLayout(self._page_header("Trang chủ", app))
        div = QFrame(); div.setObjectName("divider")
        lay.addWidget(div)

        g1 = QGroupBox("Chụp ảnh")
        g1.setLayout(self._card_grid([
            ("Chụp vùng", app.capture_region, "region", ""),
            ("Toàn màn hình", app.capture_fullscreen, "fullscreen", ""),
            ("Cửa sổ hiện tại", app.capture_window, "window", ""),
            ("Chụp lại vùng cũ", app.capture_last_region, "last_region", ""),
            ("Chụp cuộn", app.capture_scrolling, "scrolling", ""),
            ("Chụp trễ 3 giây", lambda: app.capture_delayed(3)),
            ("Chụp tự động", app.capture_auto),
            ("Ảnh từ clipboard", app.capture_from_clipboard),
            ("Mở ảnh", app.open_image_file),
        ], cols=3))
        lay.addWidget(g1)

        g2 = QGroupBox("Quay màn hình")
        g2.setLayout(self._card_grid([
            ("Quay MP4", lambda: app.record_screen("mp4"), "record", ""),
            ("Quay GIF", lambda: app.record_screen("gif"), "gif", ""),
        ], cols=3))
        lay.addWidget(g2)
        lay.addStretch()
        self.stack.addWidget(page)

    # ----- Trang công cụ -----
    def _build_tools_page(self, app):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addLayout(self._page_header("Công cụ"))
        div = QFrame(); div.setObjectName("divider")
        lay.addWidget(div)
        grid = QGridLayout()
        grid.setSpacing(10)
        tools = [
            ("Lấy mã màu", app.tool_color_picker),
            ("Thước đo (px)", app.tool_ruler),
            ("OCR — trích chữ từ ảnh", app.tool_ocr),
            ("Ghép nhiều ảnh", app.tool_combine),
            ("Tách ảnh theo lưới", app.tool_split),
            ("Tạo ảnh thu nhỏ", app.tool_thumbnail),
            ("Kiểm tra hash file", app.tool_hash),
            ("Mở thư mục ảnh", app.tool_open_folder),
            ("Cài đặt", lambda: self.show_page("settings")),
        ]
        for i, (label, fn) in enumerate(tools):
            b = QPushButton(label)
            b.setObjectName("card")
            b.setMinimumHeight(92)
            b.clicked.connect(fn)
            depth_shadow(b)
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)
        lay.addStretch()
        self.stack.addWidget(page)

    # ----- Trang lịch sử -----
    def _build_history_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addLayout(self._page_header("Lịch sử"))
        div = QFrame(); div.setObjectName("divider")
        lay.addWidget(div)
        self.list = QListWidget()
        self.list.setToolTip("Nhấp đúp để sao chép lại liên kết hoặc mở tệp. Chuột phải để có thêm thao tác.")
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(168, 106))
        self.list.setGridSize(QSize(196, 168))
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(self._history_double)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._history_menu)
        lay.addWidget(self.list, 1)
        self.stack.addWidget(page)

    # ----- Trang cài đặt -----
    def _build_settings_page(self, app):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addLayout(self._page_header("Cài đặt"))
        div = QFrame(); div.setObjectName("divider")
        lay.addWidget(div)
        from PySide6.QtWidgets import QScrollArea
        panel = SettingsPanel(app.config)
        panel.saved.connect(self._refresh_chip)
        panel.saved.connect(self.refresh_hotkey_labels)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        lay.addWidget(scroll)
        self.settings_panel = panel
        self.stack.addWidget(page)

    # ----- Điều hướng / trạng thái -----
    def show_page(self, key: str):
        idx = {"home": 0, "tools": 1, "history": 2, "settings": 3}[key]
        self.stack.setCurrentIndex(idx)
        for k, b in self._nav_buttons.items():
            b.setChecked(k == key)
        if key == "history":
            self.refresh_history()

    def open_settings(self):
        self.show_page("settings")

    def set_status(self, msg: str):
        self.status_label.setText(msg)

    def _refresh_chip(self):
        gh = self.app_ref.config.github
        if gh.token:
            owner = gh.owner or "(theo token)"
            self.chip.setStyleSheet("color: #34D399; font-size: 13px;")
            self.chip.setToolTip(f"GitHub: {owner}/{gh.repo}")
        else:
            self.chip.setStyleSheet("color: #F59E0B; font-size: 13px;")
            self.chip.setToolTip("GitHub: chưa cấu hình")

    def refresh_history(self):
        self.list.clear()
        for it in self.app_ref.history.items[:60]:
            icon = QIcon()
            p = Path(it.local_path)
            if p.exists() and it.kind == "image":
                # Đọc ảnh thu nhỏ ngay từ đầu (không nạp full-size rồi mới thu)
                reader = QImageReader(str(p))
                sz = reader.size()
                if sz.isValid():
                    reader.setScaledSize(sz.scaled(168, 106, Qt.KeepAspectRatio))
                    thumb = reader.read()
                    if not thumb.isNull():
                        icon = QIcon(QPixmap.fromImage(thumb))
            mark = "Đã tải lên" if it.uploaded_url else "Đã lưu"
            item = QListWidgetItem(icon, f"{mark} {it.filename}\n{it.created_at.replace('T', ' ')}")
            item.setData(Qt.UserRole, it)
            item.setToolTip(it.uploaded_url or it.local_path)
            self.list.addItem(item)

    # ----- Kéo-thả file ảnh vào cửa sổ -----
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        opened = 0
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif") and p.exists():
                self.app_ref.open_image_file(p)
                opened += 1
                if opened >= 5:
                    break
        if opened:
            self.set_status(f"Đã mở {opened} ảnh từ kéo-thả.")

    # ----- Menu chuột phải trong Lịch sử -----
    def _history_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        it: HistoryItem = item.data(Qt.UserRole)
        menu = QMenu(self)
        if it.uploaded_url:
            menu.addAction("Sao chép liên kết", lambda: (
                QApplication.clipboard().setText(
                    format_link(self.app_ref.config.github.copy_format, it.uploaded_url)),
                self.set_status("Đã sao chép liên kết.")))
        p = Path(it.local_path) if it.local_path else None
        if p is not None and p.exists():
            menu.addAction("Mở tệp", lambda: os.startfile(str(p)) if sys.platform == "win32" else None)
            menu.addAction("Mở thư mục chứa tệp", lambda: (
                __import__("subprocess").Popen(["explorer", "/select,", str(p)])
                if sys.platform == "win32" else None))
        menu.addSeparator()
        menu.addAction("Xóa khỏi lịch sử", lambda: self._history_remove(it, delete_file=False))
        if p is not None and p.exists():
            menu.addAction("Xóa tệp và mục lịch sử", lambda: self._history_remove(it, delete_file=True))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def _history_remove(self, it: HistoryItem, delete_file: bool):
        if delete_file and it.local_path:
            try:
                Path(it.local_path).unlink(missing_ok=True)
            except Exception:
                pass
        self.app_ref.history.remove(it)
        self.refresh_history()
        self.set_status("Đã xóa mục lịch sử.")

    def _history_double(self, item: QListWidgetItem):
        it: HistoryItem = item.data(Qt.UserRole)
        if it.uploaded_url:
            QApplication.clipboard().setText(
                format_link(self.app_ref.config.github.copy_format, it.uploaded_url))
            self.set_status("Đã sao chép liên kết.")
        elif Path(it.local_path).exists():
            if sys.platform == "win32":
                os.startfile(it.local_path)  # type: ignore[attr-defined]

    def closeEvent(self, e):
        if hasattr(self.app_ref, "tray") and self.app_ref.tray:
            e.ignore()
            self.hide()
            self.app_ref._tray_msg(
                "GitShot",
                f"Vẫn chạy nền — {prettify(self.app_ref.config.hotkeys.region)} để chụp vùng bất cứ lúc nào.")
        else:
            super().closeEvent(e)
