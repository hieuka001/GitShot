"""Điểm vào: python -m gitshot.main  /  GitShot.exe

- DPI awareness để tọa độ khớp pixel thật khi Windows scaling > 100%.
- Ghi log vào thư mục cấu hình + excepthook toàn cục: lỗi không bắt được
  không còn làm app "biến mất không dấu vết".
- Khóa đơn tiến trình: mở app lần 2 chỉ hiện lại cửa sổ của bản đang chạy.
"""
from __future__ import annotations

import ctypes
import logging
import sys

_INSTANCE_NAME = "GitShot-single-instance"


def _dpi_aware():
    """Windows: để tọa độ Qt trùng tọa độ pixel thật khi màn hình scale 125–150%."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def _setup_logging_and_errors():
    try:
        from .config import config_dir
        log_path = config_dir() / "gitshot.log"
        config_dir().mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_path), level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except Exception:
        log_path = None

    def hook(exc_type, exc, tb):
        logging.error("Lỗi không bắt được", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                where = f"\n\nChi tiết đã ghi vào log:\n{log_path}" if log_path else ""
                QMessageBox.critical(
                    None, "GitShot gặp lỗi",
                    f"Đã xảy ra lỗi ngoài dự kiến: {exc}{where}")
        except Exception:
            pass

    sys.excepthook = hook
    return log_path


def main() -> int:
    _dpi_aware()
    log_path = _setup_logging_and_errors()
    logging.info("GitShot khởi động (log: %s)", log_path)

    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication

    from .app import STYLE, GitShotApp

    app = QApplication(sys.argv)
    app.setApplicationName("GitShot")
    app.setQuitOnLastWindowClosed(False)  # sống ở khay hệ thống
    app.setStyleSheet(STYLE)

    # --- Đơn tiến trình: đã có bản đang chạy thì nhắn nó hiện cửa sổ rồi thoát
    probe = QLocalSocket()
    probe.connectToServer(_INSTANCE_NAME)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        logging.info("Đã có GitShot đang chạy — yêu cầu hiện cửa sổ, thoát bản mới.")
        return 0

    core = GitShotApp()

    server = QLocalServer()
    QLocalServer.removeServer(_INSTANCE_NAME)  # dọn socket mồ côi của lần crash trước
    if server.listen(_INSTANCE_NAME):
        def on_new_connection():
            conn = server.nextPendingConnection()
            if conn is not None:
                conn.readyRead.connect(lambda: _wake(core))
                conn.disconnected.connect(conn.deleteLater)

        def _wake(app_core):
            app_core.window.show()
            app_core.window.raise_()
            app_core.window.activateWindow()

        server.newConnection.connect(on_new_connection)
        app._single_instance_server = server  # giữ tham chiếu sống theo app

    # Chế độ tự kiểm tra cho CI: mở app rồi tự thoát sau 1,2 giây
    if "--selftest" in sys.argv:
        from PySide6.QtCore import QTimer
        core.window.show()
        QTimer.singleShot(1200, app.quit)
        code = app.exec()
        logging.info("Selftest kết thúc, mã %s", code)
        return code

    core.window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
