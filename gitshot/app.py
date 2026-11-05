"""Cửa sổ chính GitShot: thẻ chụp, lịch sử, cài đặt GitHub, khay hệ thống, phím tắt toàn cục."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import __version__
from .capture import grab_active_window, grab_fullscreen, grab_region, scrolling_capture
from .config import AppConfig
from .editor import EditorWindow
from .github_uploader import GitHubUploader
from .history import History, HistoryItem
from .region_selector import RegionSelector
from .utils import format_link, make_filename

STYLE = """
QMainWindow, QDialog { background: #0b0e1a; color: #e2e8f0; font-family: 'Segoe UI'; font-size: 13px; }
QLabel#title { font-size: 26px; font-weight: 800; color: #f8fafc; }
QLabel#subtitle { color: #94a3b8; font-size: 13px; }
QPushButton { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 10px; padding: 8px 14px; }
QPushButton:hover { background: #273549; border-color: #22d3ee; }
QPushButton#primaryBtn { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0891b2, stop:1 #7c3aed);
    color: white; font-weight: 800; border: none; padding: 10px 22px; font-size: 14px; }
QPushButton#primaryBtn:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #8b5cf6); }
QPushButton#card { background: #111827; border: 1px solid #1f2b45; border-radius: 14px; padding: 18px 12px; font-size: 14px; font-weight: 600; text-align: center; }
QPushButton#card:hover { border-color: #22d3ee; background: #0f2033; }
QLineEdit, QComboBox { background: #111827; border: 1px solid #334155; border-radius: 8px; padding: 7px 10px; color: #e2e8f0; }
QListWidget { background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; }
QToolButton { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 6px 10px; color: #e2e8f0; }
QToolButton:checked { background: #155e75; border-color: #22d3ee; }
QScrollArea { border: none; background: #0b0e1a; }
"""


def icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "assets" / "icon.png"
    if p.exists():
        return p
    return Path(__file__).resolve().parent.parent / "assets" / "icon.png"


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Cài đặt GitHub")
        self.setMinimumWidth(560)
        gh = config.github
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("🔑 <b>GitHub Personal Access Token</b> — tạo tại github.com/settings/tokens\n"
                             "(Fine-grained token: chọn repo chứa ảnh, quyền Contents = Read and write)"))
        self.e_token = QLineEdit(gh.token)
        self.e_token.setEchoMode(QLineEdit.Password)
        row = QHBoxLayout(); row.addWidget(self.e_token)
        b_show = QPushButton("Hiện"); b_show.setCheckable(True)
        b_show.toggled.connect(lambda on: self.e_token.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        row.addWidget(b_show); lay.addLayout(row)

        grid = QGridLayout()
        grid.addWidget(QLabel("Chủ repo (để trống = tự lấy từ token):"), 0, 0)
        self.e_owner = QLineEdit(gh.owner); grid.addWidget(self.e_owner, 0, 1)
        grid.addWidget(QLabel("Repo chứa ảnh:"), 1, 0)
        self.e_repo = QLineEdit(gh.repo); grid.addWidget(self.e_repo, 1, 1)
        grid.addWidget(QLabel("Nhánh:"), 2, 0)
        self.e_branch = QLineEdit(gh.branch); grid.addWidget(self.e_branch, 2, 1)
        grid.addWidget(QLabel("Mẫu thư mục:"), 3, 0)
        self.e_folder = QLineEdit(gh.folder_pattern); grid.addWidget(self.e_folder, 3, 1)
        grid.addWidget(QLabel("Kiểu link trả về:"), 4, 0)
        self.c_link = QComboBox(); self.c_link.addItems(["raw", "cdn"]); self.c_link.setCurrentText(gh.link_type)
        grid.addWidget(self.c_link, 4, 1)
        grid.addWidget(QLabel("Định dạng khi copy:"), 5, 0)
        self.c_fmt = QComboBox(); self.c_fmt.addItems(["link", "markdown", "html"]); self.c_fmt.setCurrentText(gh.copy_format)
        grid.addWidget(self.c_fmt, 5, 1)
        lay.addLayout(grid)

        self.chk_copy = QCheckBox("Tự copy link sau khi upload"); self.chk_copy.setChecked(gh.auto_copy)
        self.chk_create = QCheckBox("Tự tạo repo chứa ảnh nếu chưa có"); self.chk_create.setChecked(gh.auto_create_repo)
        lay.addWidget(self.chk_copy); lay.addWidget(self.chk_create)

        row2 = QHBoxLayout()
        b_test = QPushButton("🔌 Kiểm tra kết nối"); b_test.clicked.connect(self._test)
        b_repo = QPushButton("📦 Tạo repo chứa ảnh ngay"); b_repo.clicked.connect(self._create_repo)
        row2.addWidget(b_test); row2.addWidget(b_repo); row2.addStretch()
        lay.addLayout(row2)

        row3 = QHBoxLayout(); row3.addStretch()
        b_save = QPushButton("💾 Lưu cài đặt"); b_save.setObjectName("primaryBtn"); b_save.clicked.connect(self._save)
        row3.addWidget(b_save); lay.addLayout(row3)

    def _apply_to(self, cfg: AppConfig):
        cfg.github.token = self.e_token.text().strip()
        cfg.github.owner = self.e_owner.text().strip()
        cfg.github.repo = self.e_repo.text().strip() or "gitshot-uploads"
        cfg.github.branch = self.e_branch.text().strip() or "main"
        cfg.github.folder_pattern = self.e_folder.text().strip()
        cfg.github.link_type = self.c_link.currentText()
        cfg.github.copy_format = self.c_fmt.currentText()
        cfg.github.auto_copy = self.chk_copy.isChecked()
        cfg.github.auto_create_repo = self.chk_create.isChecked()

    def _uploader(self) -> GitHubUploader:
        tmp = AppConfig()
        self._apply_to(tmp)
        return GitHubUploader(tmp.github.token)

    def _test(self):
        try:
            login = self._uploader().whoami()
            QMessageBox.information(self, "Kết nối OK", f"Token hợp lệ — tài khoản GitHub: {login}")
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
        self._apply_to(self.config)
        self.config.save()
        self.accept()


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
        self._selector: RegionSelector | None = None
        self._recorder = None
        self._record_ctrl: RecordControl | None = None
        self._record_kind = "mp4"
        self._owner_cache = self.config.github.owner
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

    # ---------- Luồng chụp ----------
    def _after_shot(self, img: Image.Image, kind: str = "image"):
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

    def _on_uploaded(self, result, filename: str):
        url = result.link(self.config.github.link_type)
        for it in self.history.items:
            if it.filename == filename:
                self.history.mark_uploaded(it.local_path, url)
                break
        self.window.refresh_history()
        self._tray_msg("GitShot", "Đã upload xong — link đã copy vào clipboard.")

    def capture_fullscreen(self):
        self.window.hide()
        QTimer.singleShot(350, lambda: (self._after_shot(grab_fullscreen()), self.window.show()))

    def capture_window(self):
        self._after_shot(grab_active_window())

    def capture_region(self):
        self._select_region(lambda bbox: QTimer.singleShot(120, lambda: self._after_shot(grab_region(bbox))))

    def capture_scrolling(self):
        def go(bbox):
            img = scrolling_capture(bbox)
            self._after_shot(img)
        self._select_region(go)

    def _select_region(self, callback):
        sel = RegionSelector()
        self._selector = sel

        def on_selected(bbox):
            self._selector = None
            callback(bbox)

        def on_cancel():
            self._selector = None

        sel.selected.connect(on_selected)
        sel.cancelled.connect(on_cancel)
        sel.show()
        sel.activateWindow()

    # ---------- Quay màn hình ----------
    def record_screen(self, kind: str = "mp4"):
        self._record_kind = kind

        def go(bbox):
            from .recorder import ScreenRecorder
            self._recorder = ScreenRecorder(bbox, fps=self.config.record_fps if kind == "mp4" else 10)
            self._recorder.start()
            self._record_ctrl = RecordControl()
            self._record_ctrl.stop_clicked.connect(self._stop_record)
            self._record_ctrl.show()

        # Hỏi nhanh: quay vùng chọn hay toàn màn hình
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
            ("📸 Chụp vùng (Ctrl+Shift+1)", self.capture_region),
            ("🖥 Toàn màn hình", self.capture_fullscreen),
            ("🪟 Cửa sổ hiện tại", self.capture_window),
            ("📜 Chụp cuộn", self.capture_scrolling),
            ("🎬 Quay MP4", lambda: self.record_screen("mp4")),
            ("🖼 Quay GIF", lambda: self.record_screen("gif")),
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


def _png_bytes(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class MainWindow(QMainWindow):
    def __init__(self, app: GitShotApp):
        super().__init__()
        self.app_ref = app
        self.setWindowTitle(f"GitShot {__version__} — Chụp • Enter • Lên GitHub")
        self.resize(880, 620)
        ic = icon_path()
        if ic.exists():
            self.setWindowIcon(QIcon(str(ic)))

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)

        title = QLabel("📸 GitShot")
        title.setObjectName("title")
        lay.addWidget(title)
        sub = QLabel("Chụp màn hình kiểu ShareX — sửa ngay — ấn <b>Enter</b> là ảnh lên GitHub và nhận link.\n"
                     "Vào Cài đặt GitHub dán token 1 lần duy nhất, các lần sau chụp xong chỉ cần Enter.")
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        grid = QGridLayout()
        cards = [
            ("✂️\nChụp vùng\nCtrl+Shift+1", app.capture_region),
            ("🖥\nToàn màn hình\nCtrl+Shift+2", app.capture_fullscreen),
            ("🪟\nCửa sổ hiện tại\nCtrl+Shift+3", app.capture_window),
            ("📜\nChụp cuộn\nCtrl+Shift+4", app.capture_scrolling),
            ("🎬\nQuay MP4\nCtrl+Shift+5", lambda: app.record_screen("mp4")),
            ("🖼\nQuay GIF\nCtrl+Shift+6", lambda: app.record_screen("gif")),
        ]
        for i, (label, fn) in enumerate(cards):
            b = QPushButton(label)
            b.setObjectName("card")
            b.setMinimumHeight(96)
            b.clicked.connect(fn)
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)

        row = QHBoxLayout()
        row.addWidget(QLabel("🕘 <b>Lịch sử gần đây</b> — nhấp đúp để copy link / mở file"))
        row.addStretch()
        b_settings = QPushButton("⚙ Cài đặt GitHub")
        b_settings.setObjectName("primaryBtn")
        b_settings.clicked.connect(self.open_settings)
        row.addWidget(b_settings)
        lay.addLayout(row)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._history_double)
        lay.addWidget(self.list, 1)
        self.setCentralWidget(central)
        self.refresh_history()

    def open_settings(self):
        dlg = SettingsDialog(self.app_ref.config, self)
        dlg.exec()
        self.app_ref._owner_cache = self.app_ref.config.github.owner

    def refresh_history(self):
        self.list.clear()
        for it in self.app_ref.history.items[:50]:
            icon = "🎬" if it.kind in ("mp4", "gif") else "🖼"
            link = f"  →  {it.uploaded_url}" if it.uploaded_url else "  (chưa upload)"
            item = QListWidgetItem(f"{icon} {it.filename}   •   {it.created_at.replace('T', ' ')}{link}")
            item.setData(Qt.UserRole, it)
            self.list.addItem(item)

    def _history_double(self, item: QListWidgetItem):
        it: HistoryItem = item.data(Qt.UserRole)
        if it.uploaded_url:
            QApplication.clipboard().setText(
                format_link(self.app_ref.config.github.copy_format, it.uploaded_url))
            self.app_ref._tray_msg("GitShot", "Đã copy lại link ảnh.")
        else:
            import os
            if Path(it.local_path).exists():
                os.startfile(it.local_path)  # type: ignore[attr-defined]

    def closeEvent(self, e):
        # Đóng cửa sổ chính = thu xuống khay, app tiếp tục chạy nền để phím tắt hoạt động
        if hasattr(self.app_ref, "tray") and self.app_ref.tray:
            e.ignore()
            self.hide()
            self.app_ref._tray_msg("GitShot", "Vẫn chạy nền — dùng Ctrl+Shift+1 để chụp vùng bất cứ lúc nào.")
        else:
            super().closeEvent(e)
