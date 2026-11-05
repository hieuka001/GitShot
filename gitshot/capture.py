"""Chụp màn hình: toàn màn hình / vùng / cửa sổ đang dùng / chụp cuộn."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
import time

from PIL import Image


def grab_fullscreen() -> Image.Image:
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True)


def grab_region(bbox: tuple[int, int, int, int]) -> Image.Image:
    """bbox = (x1, y1, x2, y2) theo tọa độ màn hình thật."""
    from PIL import ImageGrab
    return ImageGrab.grab(bbox=bbox, all_screens=True)


def foreground_window_rect() -> tuple[int, int, int, int] | None:
    """Khung của cửa sổ đang active (Windows). Hệ khác -> None.

    Nếu cửa sổ active là chính GitShot (bấm nút chụp cửa sổ từ trong app),
    đi xuống cửa sổ ngay bên dưới thay vì chụp chính app. Khung lấy theo
    DWM extended bounds cho khít, không thừa viền vô hình.
    """
    if sys.platform != "win32":
        return None
    try:
        import os
        import ctypes.wintypes as wt

        from .windows_detect import _setup_user32, _window_frame

        user32 = ctypes.windll.user32
        dwm = _setup_user32(user32, wt)
        user32.GetWindow.argtypes = [wt.HWND, ctypes.c_uint]
        user32.GetWindow.restype = wt.HWND
        hwnd = user32.GetForegroundWindow()
        own = os.getpid()
        for _ in range(12):
            if not hwnd:
                return None
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != own:
                break
            hwnd = user32.GetWindow(hwnd, 2)  # GW_HWNDNEXT: cửa sổ ngay bên dưới
        if not hwnd:
            return None
        return _window_frame(user32, dwm, hwnd, extended=True)
    except Exception:
        return None


def grab_active_window() -> Image.Image:
    rect = foreground_window_rect()
    if rect and rect[2] > rect[0] and rect[3] > rect[1]:
        return grab_region(rect)
    return grab_fullscreen()


def _wheel_scroll(cx: int, cy: int, notches: int = -3):
    """Cuộn bánh xe chuột tại điểm (cx, cy) bằng Win32 mouse_event trực tiếp.

    Bản cũ dùng pyautogui kèm 1 cú CLICK THẬT vào giữa vùng chụp — click có
    thể bấm trúng link/nút làm trang đổi nội dung, và pyautogui cũng là thêm
    1 tầng dễ lỗi. Nay: chỉ dời con trỏ tới tâm vùng rồi phát sự kiện cuộn.
    """
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(cx), int(cy))
    time.sleep(0.05)
    MOUSEEVENTF_WHEEL = 0x0800
    WHEEL_DELTA = 120
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(notches * WHEEL_DELTA), None)


def scrolling_capture(bbox, steps: int = 12, delay: float = 0.55) -> Image.Image:
    """Chụp cuộn: chụp vùng đã chọn, cuộn chuột xuống, chụp tiếp, rồi ghép.

    Dừng sớm khi khung hình không thay đổi nữa (đã tới cuối trang).
    """
    import logging

    from .stitch import stitch_images

    log = logging.getLogger("gitshot.scroll")
    cx = (bbox[0] + bbox[2]) // 2
    cy = (bbox[1] + bbox[3]) // 2
    log.info("Chụp cuộn bắt đầu: bbox=%s tâm=(%d,%d)", bbox, cx, cy)
    _wheel_scroll(cx, cy, 0)  # chỉ dời con trỏ vào vùng, chưa cuộn
    time.sleep(0.3)
    frames = [grab_region(bbox)]
    for i in range(steps):
        _wheel_scroll(cx, cy, -3)
        time.sleep(delay)
        frame = grab_region(bbox)
        if frame.tobytes() == frames[-1].tobytes():
            log.info("Dừng ở bước %d: khung hình không đổi (cuối trang)", i + 1)
            break  # hết nội dung để cuộn
        frames.append(frame)
    log.info("Chụp cuộn: %d khung hình", len(frames))
    if len(frames) == 1:
        return frames[0]
    return stitch_images(frames)


def apply_rounded_corners(img: Image.Image, radius: int = 10) -> Image.Image:
    """Bo tròn 4 góc ảnh (góc thành trong suốt) — khớp bo góc cửa sổ Windows 11."""
    from PIL import ImageDraw

    img = img.convert("RGBA")
    w, h = img.size
    radius = max(0, min(radius, w // 2, h // 2))
    if radius == 0:
        return img
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def pixelate(img: Image.Image, bbox: tuple[int, int, int, int], block: int = 12) -> Image.Image:
    """Làm mờ ô vuông (che thông tin nhạy cảm) vùng bbox TRONG ảnh."""
    out = img.copy()
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(out.size[0], x2), min(out.size[1], y2)
    if x2 <= x1 or y2 <= y1:
        return out
    region = out.crop((x1, y1, x2, y2))
    small = region.resize((max(1, (x2 - x1) // block), max(1, (y2 - y1) // block)), Image.NEAREST)
    region = small.resize(region.size, Image.NEAREST)
    out.paste(region, (x1, y1))
    return out
