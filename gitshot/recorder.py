"""Quay màn hình thành MP4 hoặc GIF bằng mss + imageio (ffmpeg đóng gói sẵn).

Từ v1.5: khung hình được GHI THẲNG xuống file theo luồng (streaming) ngay
khi bắt được — không còn giữ toàn bộ frame trong RAM như trước (bản cũ ngốn
~90 MB/giây ở 1080p15, quay vài phút là treo máy). Dừng quay chỉ là đóng file,
và nếu có lỗi giữa chừng thì phần đã quay vẫn còn trên đĩa.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path


class ScreenRecorder:
    def __init__(self, bbox: tuple[int, int, int, int] | None, fps: int = 15,
                 frame_source=None):
        self.bbox = bbox  # None = toàn màn hình
        self.fps = fps
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str = ""
        self.frames_written = 0
        self._path: Path | None = None
        self._frame_source = frame_source  # chỉ dùng cho unit test

    def start(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        self.error = ""
        self.frames_written = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _open_writer(self):
        import imageio.v2 as imageio
        if self._path.suffix.lower() == ".gif":
            return imageio.get_writer(str(self._path), mode="I", fps=self.fps, loop=0)
        return imageio.get_writer(str(self._path), fps=self.fps, codec="libx264", quality=8)

    def _run(self):
        writer = None
        try:
            writer = self._open_writer()
            if self._frame_source is not None:
                for frame in self._frame_source:
                    writer.append_data(frame)
                    self.frames_written += 1
                return
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
                    writer.append_data(frame[: h - h % 2, : w - w % 2].copy())
                    self.frames_written += 1
                    wait = interval - (time.time() - t0)
                    if wait > 0:
                        self._stop.wait(wait)
        except Exception as e:  # pragma: no cover - phụ thuộc môi trường máy
            self.error = str(e)
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

    def stop_and_save(self) -> Path:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self.error and self.frames_written == 0:
            raise RuntimeError(self.error)
        if self.frames_written == 0:
            raise RuntimeError("Chưa ghi được khung hình nào.")
        if self.error:
            # Có lỗi giữa chừng nhưng đã có khung hình: giữ phần đã quay được
            import logging
            logging.warning("Quay phim gặp lỗi giữa chừng, giữ phần đã ghi: %s", self.error)
        return self._path
