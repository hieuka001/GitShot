"""Nhận diện các "ô vuông có sẵn" trên màn hình: cửa sổ và các khung con của chúng.

Phần logic (find_snap_rect / snap_edges) là hàm thuần, không phụ thuộc hệ điều
hành — có unit test. Phần liệt kê cửa sổ thật chỉ chạy trên Windows (ctypes),
hệ khác trả về danh sách rỗng và chụp vùng vẫn hoạt động như thường.

Rect = (x1, y1, x2, y2, title)
"""
from __future__ import annotations

import sys

Rect = tuple  # (x1, y1, x2, y2, title)


def rect_area(r) -> int:
    return max(0, r[2] - r[0]) * max(0, r[3] - r[1])


def rect_contains(r, x: int, y: int) -> bool:
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def find_snap_rect(rects, x: int, y: int, min_size: int = 24):
    """Ô NHỎ NHẤT chứa điểm (x, y) — chính là ô người dùng đang trỏ vào.

    Ưu tiên ô nhỏ nhất vì đó thường là nút/khung nội dung cụ thể, thay vì
    cả cửa sổ lớn bao ngoài.
    """
    candidates = [
        r for r in rects
        if rect_contains(r, x, y) and (r[2] - r[0]) >= min_size and (r[3] - r[1]) >= min_size
    ]
    if not candidates:
        return None
    return min(candidates, key=rect_area)


def snap_edges(bbox, rects, threshold: int = 12):
    """Hít 4 cạnh của bbox vào cạnh gần nhất của các ô có sẵn (trong ngưỡng)."""
    x1, y1, x2, y2 = bbox
    lefts = [r[0] for r in rects] + [r[2] for r in rects]
    tops = [r[1] for r in rects] + [r[3] for r in rects]

    def nearest(value, options):
        best, best_d = value, threshold + 1
        for o in options:
            d = abs(o - value)
            if d < best_d:
                best, best_d = o, d
        return best

    nx1, nx2 = nearest(x1, lefts), nearest(x2, lefts)
    ny1, ny2 = nearest(y1, tops), nearest(y2, tops)
    if nx2 - nx1 < 8 or ny2 - ny1 < 8:
        return bbox  # hít quá đà làm vùng méo -> giữ nguyên
    return (nx1, ny1, nx2, ny2)


def enumerate_rectangles(max_rects: int = 600) -> list:
    """Liệt kê cửa sổ hiển thị + khung con của cửa sổ đang active (Windows)."""
    if sys.platform != "win32":
        return []
    try:
        return _enumerate_win32(max_rects)
    except Exception:
        return []


def _enumerate_win32(max_rects: int) -> list:
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    rects: list = []
    seen = set()

    def add(hwnd):
        r = wt.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return
        w, h = r.right - r.left, r.bottom - r.top
        if w < 16 or h < 16:
            return
        key = (r.left, r.top, r.right, r.bottom)
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value or ""
        if key in seen and not title:
            return
        seen.add(key)
        rects.append((r.left, r.top, r.right, r.bottom, title))

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def enum_top(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            add(hwnd)
        return True

    user32.EnumWindows(CB(enum_top), 0)

    # Khung con của cửa sổ đang dùng — nơi có các "ô" cụ thể (nút, panel, ô nhập…)
    fg = user32.GetForegroundWindow()
    if fg:
        def enum_child(hwnd, _):
            add(hwnd)
            return len(rects) < max_rects

        user32.EnumChildWindows(fg, CB(enum_child), 0)

    # Bỏ các rect trùng hệt nhau, giữ bản có tiêu đề
    uniq: dict = {}
    for r in rects:
        k = r[:4]
        if k not in uniq or (r[4] and not uniq[k][4]):
            uniq[k] = r
    return list(uniq.values())[:max_rects]
