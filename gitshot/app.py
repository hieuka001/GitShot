"""GitShot v1.1 — cửa sổ chính dạng sidebar + trang Công cụ kiểu ShareX.

Trang: Trang chủ (nhóm chụp/quay) • Công cụ (màu, thước, OCR, ghép/tách ảnh,
thumbnail, hash, thư mục) • Lịch sử (lưới thumbnail) • Cài đặt (GitHub + chụp).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Qt, QTimer, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget,
)

from . import __version__
from .capture import (
    apply_rounded_corners, grab_active_window, grab_fullscreen, grab_region,
    scrolling_capture,
)
from .color_picker import ColorPickerOverlay
from .config import AppConfig
from .editor import EditorWindow, pil_to_pixmap
from .github_uploader import GitHubUploader
from .history import History, HistoryItem
from .region_selector import MeasureOverlay, RegionSelector
from .tools_extra import (
    combine_images, file_hashes, make_thumbnail, ocr_image, split_image,
)
from .utils import format_link, make_filename

STYLE = """
QMainWindow, QDialog { background: #0b0e1a; color: #e2e8f0; font-family: 'Segoe UI'; font-size: 13px; }
QFrame#sidebar { background: #0d1120; border-right: 1px solid #1e293b; }
QLabel#logo { font-size: 22px; font-weight: 800; color: #f8fafc; }
QLabel#subtitle { color: #94a3b8; font-size: 12.5px; }
QLabel#chip { background: #12233a; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 9px; padding: 4px 8px; font-size: 11.5px; }
QPushButton { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 10px; padding: 8px 14px; }
QPushButton:hover { background: #273549; border-color: #22d3ee; }
QPushButton#primaryBtn { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0891b2, stop:1 #7c3aed);
    color: white; font-weight: 800; border: none; padding: 11px 22px; font-size: 14px; }
QPushButton#primaryBtn:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #8b5cf6); }
QPushButton#nav { background: transparent; border: none; border-radius: 10px; padding: 10px 12px; text-align: left; font-size: 14px; font-weight: 600; }
QPushButton#nav:hover { background: #16203a; }
QPushButton#nav:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #164e63, stop:1 #4c1d95); color: white; }
QPushButton#card { background: #111827; border: 1px solid #1f2b45; border-radius: 14px; padding: 14px 10px; font-size: 13.5px; font-weight: 600; }
QPushButton#card:hover { border-color: #22d3ee; background: #0f2033; }
QFrame#banner { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0e7490, stop:0.55 #1d4ed8, stop:1 #7c3aed); border-radius: 16px; }
QLabel#bannerTitle { color: white; font-size: 20px; font-weight: 800; }
QLabel#bannerSub { color: #dbeafe; font-size: 12.5px; }
QGroupBox { border: 1px solid #1e293b; border-radius: 12px; margin-top: 10px; padding-top: 12px; font-weight: 700; color: #cbd5e1; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #111827; border: 1px solid #334155; border-radius: 8px; padding: 7px 10px; color: #e2e8f0; }
QListWidget { background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; }
QToolButton { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 6px 10px; color: #e2e8f0; }
QToolButton:checked { background: #155e75; border-color: #22d3ee; }
QScrollArea { border: none; background: #0b0e1a; }
QLabel#status { color: #7dd3fc; font-size: 12px; }
"""


def icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "assets" / "icon.png"
    if p.exists():
        return p
    return Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def _png_bytes(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class SettingsPanel(QWidget):
    saved = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        gh = config.github
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        g1 = QGroupBox("🔑 GitHub — nơi ảnh được đẩy lên")
        f = QGridLayout(g1)
        f.addWidget(QLabel("Token (Personal Access Token):"), 0, 0)
        self.e_token = QLineEdit(gh.token)
        self.e_token.setEchoMode(QLineEdit.Password)
        f.addWidget(self.e_token, 0, 1)
        b_show = QPushButton("Hiện")
        b_show.setCheckable(True)
        b_show.toggled.connect(lambda on: self.e_token.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        f.addWidget(b_show, 0, 2)
        f.addWidget(QLabel("Chủ repo (trống = tự lấy từ token):"), 1, 0)
        self.e_owner = QLineEdit(gh.owner); f.addWidget(self.e_owner, 1, 1)
        f.addWidget(QLabel("Repo chứa ảnh:"), 2, 0)
        self.e_repo = QLineEdit(gh.repo); f.addWidget(self.e_repo, 2, 1)
        f.addWidget(QLabel("Nhánh:"), 3, 0)
        self.e_branch = QLineEdit(gh.branch); f.addWidget(self.e_branch, 3, 1)
        f.addWidget(QLabel("Mẫu thư mục:"), 4, 0)
        self.e_folder = QLineEdit(gh.folder_pattern); f.addWidget(self.e_folder, 4, 1)
        f.addWidget(QLabel("Kiểu link trả về:"), 5, 0)
        self.c_link = QComboBox(); self.c_link.addItems(["raw", "cdn"]); self.c_link.setCurrentText(gh.link_type)
        f.addWidget(self.c_link, 5, 1)
        f.addWidget(QLabel("Định dạng khi copy:"), 6, 0)
        self.c_fmt = QComboBox(); self.c_fmt.addItems(["link", "markdown", "html"]); self.c_fmt.setCurrentText(gh.copy_format)
        f.addWidget(self.c_fmt, 6, 1)
        row = QHBoxLayout()
        b_test = QPushButton("🔌 Kiểm tra kết nối"); b_test.clicked.connect(self._test)
        b_repo = QPushButton("📦 Tạo repo chứa ảnh"); b_repo.clicked.connect(self._create_repo)
        row.addWidget(b_test); row.addWidget(b_repo); row.addStretch()
        f.addLayout(row, 7, 0, 1, 3)
        lay.addWidget(g1)

        g2 = QGroupBox("📸 Hành vi khi chụp")
        v = QVBoxLayout(g2)
        self.chk_smart = QCheckBox("Nhận ô thông minh: di chuột tự bắt ô/cửa sổ có sẵn, click là chụp đúng ô")
        self.chk_smart.setChecked(config.smart_snap)
        self.chk_round = QCheckBox("Bo góc tròn cho ảnh chụp theo ô/cửa sổ (khớp Windows 11)")
        self.chk_round.setChecked(config.rounded_corners)
        rowr = QHBoxLayout()
        rowr.addWidget(QLabel("Bán kính bo góc:"))
        self.s_radius = QSpinBox(); self.s_radius.setRange(0, 30); self.s_radius.setValue(config.corner_radius)
        rowr.addWidget(self.s_radius); rowr.addStretch()
        self.chk_copy = QCheckBox("Tự copy link sau khi upload"); self.chk_copy.setChecked(gh.auto_copy)
        self.chk_create = QCheckBox("Tự tạo repo chứa ảnh nếu chưa có"); self.chk_create.setChecked(gh.auto_create_repo)
        self.chk_local = QCheckBox("Luôn lưu 1 bản trong máy (Pictures/GitShot)"); self.chk_local.setChecked(config.save_local_copy)
        v.addWidget(self.chk_smart); v.addWidget(self.chk_round); v.addLayout(rowr)
        v.addWidget(self.chk_copy); v.addWidget(self.chk_create); v.addWidget(self.chk_local)
        lay.addWidget(g2)

        g3 = QGroupBox("⌨ Phím tắt toàn cục")
        v3 = QVBoxLayout(g3)
        hk = config.hotkeys
        v3.addWidget(QLabel(
            f"Chụp vùng: <b>{hk.region}</b> • Toàn màn hình: <b>{hk.fullscreen}</b> • Cửa sổ: <b>{hk.window}</b><br>"
            f"Chụp cuộn: <b>{hk.scrolling}</b> • Quay MP4: <b>{hk.record}</b> • Quay GIF: <b>{hk.gif}</b>"))
        lay.addWidget(g3)

        b_save = QPushButton("💾 Lưu cài đặt")
        b_save.setObjectName("primaryBtn")
        b_save.clicked.connect(self._save)
        lay.addWidget(b_save)
        lay.addStretch()

    def _apply(self, cfg: AppConfig):
        cfg.github.token = self.e_token.text().strip()
        cfg.github.owner = self.e_owner.text().strip()
        cfg.github.repo = self.e_repo.text().strip() or "gitshot-uploads"
        cfg.github.branch = self.e_branch.text().strip() or "main"
        cfg.github.folder_pattern = self.e_folder.text().strip()
        cfg.github.link_type = self.c_link.currentText()
        cfg.github.copy_format = self.c_fmt.currentText()
        cfg.github.auto_copy = self.chk_copy.isChecked()
        cfg.github.auto_create_repo = self.chk_create.isChecked()
        cfg.smart_snap = self.chk_smart.isChecked()
        cfg.rounded_corners = self.chk_round.isChecked()
        cfg.corner_radius = self.s_radius.value()
        cfg.save_local_copy = self.chk_local.isChecked()

    def _uploader(self) -> GitHubUploader:
        tmp = AppConfig()
        self._apply(tmp)
        return GitHubUploader(tmp.github.token)

    def _test(self):
        try:
            login = self._uploader().whoami()
            QMessageBox.information(self, "Kết nối OK", f"Token hợp lệ — tài khoản: {login}")
            if not self.e_owner.text().strip():
                self.e_owner.setText(login)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi kết nối", str(e))

    def _create_repo(self):
        try:
            up = self._uploader()
            owner = self.e_owner.text().strip() or up.whoami()
            up.ensure_repo(owner, self.e_repo.text().strip() or "gitshot-uploads")
            QMessageBox.information(self, "Xong", f"Repo {owner}/{self.e_repo.text().strip()} đã sẵn sàng.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def _save(self):
        self._apply(self.config)
        self.config.save()
        self.saved.emit()
        QMessageBox.information(self, "Đã lưu", "Cài đặt đã được lưu.")


class RecordControl(QWidget):
    stop_clicked = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        lay = QHBoxLayout(self)
        self.label = QLabel("🔴 Đang quay… 00:00")
        lay.addWidget(self.label)
        b = QPushButton("⏹ Dừng & lưu")
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
        self.label.setText(f"🔴 Đang quay… {self._sec // 60:02d}:{self._sec % 60:02d}")


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
        self._auto = {"timer": None, "left": 0, "bbox": None}
        self.hotkey_fired.connect(self._on_hotkey)

        self.window = MainWindow(self)
        self._build_tray()
        self._register_hotkeys()

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
        return up.upload_bytes(
            data, filename, owner=owner, repo=gh.repo, branch=gh.branch,
            folder_pattern=gh.folder_pattern, auto_create_repo=gh.auto_create_repo,
        )

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
        filename = make_filename(ext="png")
        if self.config.save_local_copy:
            buf = _png_bytes(img)
            path = self.save_local(buf, filename)
            self.history.add(HistoryItem(filename, str(path), History.now_iso(), kind=kind, size=len(buf)))
            self.window.refresh_history()
        editor = EditorWindow(img, filename, self.config, self.upload_bytes, self.save_local)
        editor.uploaded.connect(lambda r, fn=filename: self._on_uploaded(r, fn))
        editor.show()
        self._editors.append(editor)
        self.status(f"Đã chụp {filename} — ấn Enter trong cửa sổ sửa để lên GitHub")

    def _on_uploaded(self, result, filename: str):
        url = result.link(self.config.github.link_type)
        for it in self.history.items:
            if it.filename == filename:
                self.history.mark_uploaded(it.local_path, url)
                break
        self.window.refresh_history()
        self._tray_msg("GitShot", "Đã upload xong — link đã copy vào clipboard.")
        self.status(f"☁ Đã lên GitHub: {url}")

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
            QMessageBox.information(self.window, "Chưa có vùng cũ",
                                    "Anh chưa chụp vùng nào. Hãy chụp vùng 1 lần trước.")

    def capture_scrolling(self):
        def go(bbox, snapped):
            self.config.last_region = list(bbox)
            self.config.save()
            self._after_shot(scrolling_capture(bbox))
        self._select_region(go)

    def capture_delayed(self, seconds: int = 3):
        self.status(f"⏳ Sẽ mở chụp vùng sau {seconds} giây…")
        QTimer.singleShot(seconds * 1000, self.capture_region)

    def capture_auto(self):
        interval, ok = QInputDialog.getInt(self.window, "Chụp tự động",
                                           "Mỗi bao nhiêu giây chụp 1 tấm?", 10, 2, 3600)
        if not ok:
            return
        count, ok = QInputDialog.getInt(self.window, "Chụp tự động",
                                        "Chụp bao nhiêu tấm? (toàn màn hình, tự upload)", 5, 1, 200)
        if not ok:
            return
        self._auto["left"] = count
        if self._auto["timer"]:
            self._auto["timer"].stop()
        timer = QTimer(self)
        timer.timeout.connect(self._auto_tick)
        self._auto["timer"] = timer
        timer.start(interval * 1000)
        self.status(f"⏱ Chụp tự động: {count} tấm, mỗi {interval} giây, tự upload…")

    def _auto_tick(self):
        if self._auto["left"] <= 0:
            self._auto["timer"].stop()
            self.status("⏱ Chụp tự động: xong.")
            return
        self._auto["left"] -= 1
        img = grab_fullscreen()
        filename = make_filename()
        data = _png_bytes(img)
        path = self.save_local(data, filename)
        self.history.add(HistoryItem(filename, str(path), History.now_iso(), size=len(data)))
        try:
            result = self.upload_bytes(data, filename)
            url = result.link(self.config.github.link_type)
            self.history.mark_uploaded(str(path), url)
            if self.config.github.auto_copy:
                QApplication.clipboard().setText(format_link(self.config.github.copy_format, url))
            self.status(f"⏱ Đã tự chụp + upload: {url}")
        except Exception as e:
            self.status(f"⏱ Tự chụp xong nhưng upload lỗi: {e}")
        self.window.refresh_history()

    def capture_from_clipboard(self):
        cb = QApplication.clipboard()
        img = cb.image()
        if img.isNull():
            QMessageBox.information(self.window, "Clipboard trống",
                                    "Clipboard chưa có ảnh. Hãy copy 1 ảnh rồi thử lại.")
            return
        buf = _qt_image_to_pil(img)
        self._after_shot(buf)

    def open_image_file(self):
        path, _ = QFileDialog.getOpenFileName(self.window, "Mở ảnh để sửa / upload",
                                              "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._after_shot(Image.open(path))

    def _select_region(self, callback):
        sel = RegionSelector(smart=self.config.smart_snap)
        self._selector = sel

        def on_selected(bbox, snapped):
            self._selector = None
            callback(bbox, snapped)

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
            self._recorder = ScreenRecorder(bbox, fps=self.config.record_fps if kind == "mp4" else 10)
            self._recorder.start()
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
        ext = "gif" if self._record_kind == "gif" else "mp4"
        filename = make_filename(prefix="record", ext=ext)
        path = self.config.pictures_folder() / filename
        try:
            self._recorder.stop_and_save(path)
        except Exception as e:
            QMessageBox.critical(self.window, "Quay thất bại", str(e))
            return
        self._recorder = None
        data = path.read_bytes()
        self.history.add(HistoryItem(filename, str(path), History.now_iso(), kind=ext, size=len(data)))
        self.window.refresh_history()
        box = QMessageBox(self.window)
        box.setWindowTitle("Đã quay xong")
        box.setText(f"Đã lưu: {path}\n\nĐẩy lên GitHub luôn không? (file {len(data)//1024} KB)")
        b_up = box.addButton("⬆ Upload GitHub", QMessageBox.AcceptRole)
        box.addButton("Để sau", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == b_up:
            try:
                result = self.upload_bytes(data, filename)
                url = result.link(self.config.github.link_type)
                QApplication.clipboard().setText(format_link(self.config.github.copy_format, url))
                self.history.mark_uploaded(str(path), url)
                self.window.refresh_history()
                QMessageBox.information(self.window, "Xong 🎉", f"Link video (đã copy):\n{url}")
            except Exception as e:
                QMessageBox.critical(self.window, "Upload lỗi", str(e))

    # ---------- Công cụ ----------
    def tool_color_picker(self):
        self.window.hide()
        def go():
            img = grab_fullscreen()
            overlay = ColorPickerOverlay(pil_to_pixmap(img), img)
            self._overlay = overlay
            overlay.picked.connect(lambda hexcode, rgb: (
                QApplication.clipboard().setText(hexcode),
                self.status(f"🎨 Đã copy mã màu {hexcode} (RGB {rgb[0]}, {rgb[1]}, {rgb[2]})"),
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
        for text, fn in [
            ("📸 Chụp vùng thông minh (Ctrl+Shift+1)", self.capture_region),
            ("🖥 Toàn màn hình", self.capture_fullscreen),
            ("🪟 Cửa sổ hiện tại", self.capture_window),
            ("🔁 Chụp lại vùng cũ", self.capture_last_region),
            ("📜 Chụp cuộn", self.capture_scrolling),
            ("🎬 Quay MP4", lambda: self.record_screen("mp4")),
            ("🖼 Quay GIF", lambda: self.record_screen("gif")),
            ("🎨 Lấy mã màu", self.tool_color_picker),
            ("📏 Thước đo", self.tool_ruler),
        ]:
            a = QAction(text, menu); a.triggered.connect(fn); menu.addAction(a)
        menu.addSeparator()
        a_show = QAction("Mở GitShot", menu); a_show.triggered.connect(self.window.show); menu.addAction(a_show)
        a_quit = QAction("Thoát", menu); a_quit.triggered.connect(QApplication.quit); menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.window.show() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _register_hotkeys(self):
        try:
            import keyboard
        except Exception:
            return
        hk = self.config.hotkeys
        mapping = {
            hk.region: "region", hk.fullscreen: "fullscreen", hk.window: "window",
            hk.scrolling: "scrolling", hk.record: "record", hk.gif: "gif",
        }
        for combo, name in mapping.items():
            try:
                keyboard.add_hotkey(combo, lambda n=name: self.hotkey_fired.emit(n), suppress=False)
            except Exception:
                pass

    def _on_hotkey(self, name: str):
        {
            "region": self.capture_region,
            "fullscreen": self.capture_fullscreen,
            "window": self.capture_window,
            "scrolling": self.capture_scrolling,
            "record": lambda: self.record_screen("mp4"),
            "gif": lambda: self.record_screen("gif"),
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
        b = QPushButton("📋 Copy tất cả")
        self.addButton(b, QMessageBox.ActionRole)
        b.clicked.connect(lambda: QApplication.clipboard().setText(text))
        self.addButton(QPushButton("Đóng"), QMessageBox.AcceptRole)


class MainWindow(QMainWindow):
    def __init__(self, app: GitShotApp):
        super().__init__()
        self.app_ref = app
        self.setWindowTitle(f"GitShot {__version__} — Chụp • Enter • Lên GitHub")
        self.resize(1020, 680)
        ic = icon_path()
        if ic.exists():
            self.setWindowIcon(QIcon(str(ic)))

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- Sidebar -----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 16, 14, 14)
        logo = QLabel("📸 GitShot")
        logo.setObjectName("logo")
        sb.addWidget(logo)
        tag = QLabel("ShareX-style + GitHub")
        tag.setObjectName("subtitle")
        sb.addWidget(tag)
        sb.addSpacing(16)
        self._nav_buttons = {}
        for key, label in [("home", "🏠  Trang chủ"), ("tools", "🧰  Công cụ"),
                           ("history", "🕘  Lịch sử"), ("settings", "⚙  Cài đặt")]:
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self._nav_buttons[key] = b
            sb.addWidget(b)
        sb.addStretch()
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.chip.setWordWrap(True)
        sb.addWidget(self.chip)
        ver = QLabel(f"Phiên bản {__version__}")
        ver.setObjectName("subtitle")
        sb.addWidget(ver)
        root.addWidget(sidebar)

        # ----- Nội dung -----
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 14, 16, 10)
        self.stack = QStackedWidget()
        rv.addWidget(self.stack, 1)
        self.status_label = QLabel("Sẵn sàng — Ctrl+Shift+1 để chụp vùng thông minh.")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        rv.addWidget(self.status_label)
        root.addWidget(right, 1)
        self.setCentralWidget(central)

        self._build_home_page(app)
        self._build_tools_page(app)
        self._build_history_page()
        self._build_settings_page(app)
        self.show_page("home")
        self.refresh_history()
        self._refresh_chip()

    # ----- Trang chủ -----
    def _card_grid(self, items, cols=4):
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (label, fn) in enumerate(items):
            b = QPushButton(label)
            b.setObjectName("card")
            b.setMinimumHeight(84)
            b.clicked.connect(fn)
            grid.addWidget(b, i // cols, i % cols)
        return grid

    def _build_home_page(self, app):
        page = QWidget()
        lay = QVBoxLayout(page)
        banner = QFrame()
        banner.setObjectName("banner")
        bv = QVBoxLayout(banner)
        t = QLabel("Chụp → Enter → Có link GitHub")
        t.setObjectName("bannerTitle")
        s = QLabel("Di chuột, app tự bắt đúng ô/cửa sổ trên màn hình — click là chụp, ảnh bo góc như Windows 11.")
        s.setObjectName("bannerSub")
        s.setWordWrap(True)
        bv.addWidget(t); bv.addWidget(s)
        lay.addWidget(banner)

        g1 = QGroupBox("📸  Chụp ảnh")
        g1.setLayout(self._card_grid([
            ("✂️\nChụp vùng\nthông minh", app.capture_region),
            ("🖥\nToàn màn hình\nCtrl+Shift+2", app.capture_fullscreen),
            ("🪟\nCửa sổ hiện tại\nCtrl+Shift+3", app.capture_window),
            ("🔁\nChụp lại\nvùng cũ", app.capture_last_region),
            ("📜\nChụp cuộn\ntrang dài", app.capture_scrolling),
            ("⏳\nChụp trễ\n3 giây", lambda: app.capture_delayed(3)),
            ("⏱\nChụp tự động\ntheo giờ", app.capture_auto),
            ("📋\nẢnh từ\nclipboard", app.capture_from_clipboard),
            ("🖼\nMở ảnh\ntừ máy", app.open_image_file),
        ], cols=3))
        lay.addWidget(g1)

        g2 = QGroupBox("🎬  Quay màn hình")
        g2.setLayout(self._card_grid([
            ("🎬\nQuay MP4\nCtrl+Shift+5", lambda: app.record_screen("mp4")),
            ("🖼\nQuay GIF\nCtrl+Shift+6", lambda: app.record_screen("gif")),
        ], cols=3))
        lay.addWidget(g2)
        lay.addStretch()
        self.stack.addWidget(page)

    # ----- Trang công cụ -----
    def _build_tools_page(self, app):
        page = QWidget()
        lay = QVBoxLayout(page)
        title = QLabel("🧰 Công cụ — kiểu ShareX")
        title.setObjectName("logo")
        lay.addWidget(title)
        sub = QLabel("Các tiện ích đi kèm, không cần mở phần mềm khác.")
        sub.setObjectName("subtitle")
        lay.addWidget(sub)
        grid = QGridLayout()
        grid.setSpacing(10)
        tools = [
            ("🎨\nLấy mã màu\ntrên màn hình", app.tool_color_picker),
            ("📏\nThước đo\nmàn hình (px)", app.tool_ruler),
            ("🔤\nOCR\ntrích chữ từ ảnh", app.tool_ocr),
            ("🧩\nGhép nhiều ảnh\nthành 1", app.tool_combine),
            ("✂️\nTách ảnh\ntheo lưới", app.tool_split),
            ("🔍\nTạo ảnh\nthu nhỏ", app.tool_thumbnail),
            ("🔐\nKiểm tra\nhash file", app.tool_hash),
            ("📁\nMở thư mục\nảnh đã lưu", app.tool_open_folder),
            ("⚙\nCài đặt\nGitHub + chụp", lambda: self.show_page("settings")),
        ]
        for i, (label, fn) in enumerate(tools):
            b = QPushButton(label)
            b.setObjectName("card")
            b.setMinimumHeight(92)
            b.clicked.connect(fn)
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)
        lay.addStretch()
        self.stack.addWidget(page)

    # ----- Trang lịch sử -----
    def _build_history_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        row = QHBoxLayout()
        t = QLabel("🕘 Lịch sử chụp / upload")
        t.setObjectName("logo")
        row.addWidget(t)
        row.addStretch()
        hint = QLabel("Nhấp đúp: copy lại link (đã upload) hoặc mở file")
        hint.setObjectName("subtitle")
        row.addWidget(hint)
        lay.addLayout(row)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(168, 106))
        self.list.setGridSize(QSize(196, 168))
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(self._history_double)
        lay.addWidget(self.list, 1)
        self.stack.addWidget(page)

    # ----- Trang cài đặt -----
    def _build_settings_page(self, app):
        page = QWidget()
        lay = QVBoxLayout(page)
        from PySide6.QtWidgets import QScrollArea
        panel = SettingsPanel(app.config)
        panel.saved.connect(self._refresh_chip)
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
            owner = gh.owner or "(tự lấy từ token)"
            self.chip.setText(f"☁ GitHub: {owner}/{gh.repo}")
        else:
            self.chip.setText("⚠ Chưa nhập token GitHub — vào Cài đặt")

    def refresh_history(self):
        self.list.clear()
        for it in self.app_ref.history.items[:60]:
            icon = QIcon()
            p = Path(it.local_path)
            if p.exists() and it.kind == "image":
                pm = QPixmap(str(p))
                if not pm.isNull():
                    icon = QIcon(pm.scaled(168, 106, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            mark = "☁" if it.uploaded_url else "💾"
            item = QListWidgetItem(icon, f"{mark} {it.filename}\n{it.created_at.replace('T', ' ')}")
            item.setData(Qt.UserRole, it)
            item.setToolTip(it.uploaded_url or it.local_path)
            self.list.addItem(item)

    def _history_double(self, item: QListWidgetItem):
        it: HistoryItem = item.data(Qt.UserRole)
        if it.uploaded_url:
            QApplication.clipboard().setText(
                format_link(self.app_ref.config.github.copy_format, it.uploaded_url))
            self.set_status("📋 Đã copy lại link ảnh từ lịch sử.")
        elif Path(it.local_path).exists():
            if sys.platform == "win32":
                os.startfile(it.local_path)  # type: ignore[attr-defined]

    def closeEvent(self, e):
        if hasattr(self.app_ref, "tray") and self.app_ref.tray:
            e.ignore()
            self.hide()
            self.app_ref._tray_msg("GitShot", "Vẫn chạy nền — Ctrl+Shift+1 để chụp vùng bất cứ lúc nào.")
        else:
            super().closeEvent(e)
