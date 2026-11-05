"""Quay màn hình thành MP4 hoặc GIF bằng mss + imageio (ffmpeg đóng gói sẵn)."""
from __future__ import annotations

import threading
import time
from pathlib import Path


class ScreenRecorder:
    def __init__(self, bbox: tuple[int, int, int, int] | None, fps: int = 15):
        self.bbox = bbox  # None = toàn màn hình
        self.fps = fps
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.frames: list = []
        self.error: str = ""

    def start(self):
        self._stop.clear()
        self.frames = []
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            import mss
            import numpy as np

            with mss.mss() as sct:
                monitor = sct.monitors[0]
                if self.bbox:
                    x1, y1, x2, y2 = self.bbox
                    monitor = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}
                interval = 1.0 / max(1, self.fps)
                while not self._stop.is_set():
                    t0 = time.time()
                    shot = sct.grab(monitor)
                    frame = np.asarray(shot)[:, :, :3][:, :, ::-1]  # BGRA -> RGB
                    # Kích thước phải chẵn cho codec mp4
                    h, w = frame.shape[:2]
                    self.frames.append(frame[: h - h % 2, : w - w % 2].copy())
                    wait = interval - (time.time() - t0)
                    if wait > 0:
                        self._stop.wait(wait)
        except Exception as e:  # pragma: no cover - phụ thuộc môi trường máy
            self.error = str(e)

    def stop_and_save(self, path: Path) -> Path:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self.error:
            raise RuntimeError(self.error)
        if not self.frames:
            raise RuntimeError("Chưa ghi được khung hình nào.")
        import imageio.v2 as imageio

        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".gif":
            imageio.mimsave(str(path), self.frames, fps=self.fps, loop=0)
        else:
            writer = imageio.get_writer(str(path), fps=self.fps, codec="libx264", quality=8)
            try:
                for f in self.frames:
                    writer.append_data(f)
            finally:
                writer.close()
        self.frames = []
        return path
