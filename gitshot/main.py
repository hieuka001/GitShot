"""Điểm vào: python -m gitshot.main  /  GitShot.exe"""
from __future__ import annotations

import ctypes
import sys


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


def main() -> int:
    _dpi_aware()
    from PySide6.QtWidgets import QApplication

    from .app import STYLE, GitShotApp

    app = QApplication(sys.argv)
    app.setApplicationName("GitShot")
    app.setQuitOnLastWindowClosed(False)  # sống ở khay hệ thống
    app.setStyleSheet(STYLE)
    core = GitShotApp()
    core.window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
