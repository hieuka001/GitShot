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
    cả cửa sổ lớn bao ngoài. Tie-break xác định (diện tích rồi tọa độ) để
    cùng một danh sách ô luôn cho cùng một kết quả, bất kể thứ tự liệt kê.
    """
    candidates = [
        r for r in rects
        if rect_contains(r, x, y) and (r[2] - r[0]) >= min_size and (r[3] - r[1]) >= min_size
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda r: (rect_area(r), r[0], r[1], r[2], r[3]))


class StableRectTracker:
    """Giữ ô đang khoanh ỔN ĐỊNH, chống nhảy qua lại giữa các ô chồng nhau.

    Vấn đề của cách chọn thuần "ô nhỏ nhất": di chuột 1px gần biên chung của
    hai ô chồng nhau là ô thắng đổi ngay -> khung khoanh nhảy liên tục.
    Tracker này giữ ô hiện tại cho tới khi:
    - con trỏ ra khỏi ô hiện tại (nới biên stick_px), hoặc
    - xuất hiện ô nhỏ hơn hẳn (<= shrink_ratio diện tích) chứa con trỏ và
      ô đó thắng LIÊN TIẾP confirm lần (loại nhiễu 1 khung hình).
    """

    def __init__(self, stick_px: int = 6, shrink_ratio: float = 0.55, confirm: int = 2):
        self.stick_px = stick_px
        self.shrink_ratio = shrink_ratio
        self.confirm = confirm
        self.current = None
        self._pending = None
        self._pending_n = 0

    def reset(self):
        self.current = None
        self._pending = None
        self._pending_n = 0

    def _confirm(self, cand):
        if self._pending is not None and cand[:4] == self._pending[:4]:
            self._pending_n += 1
        else:
            self._pending, self._pending_n = cand, 1
        if self._pending_n >= self.confirm:
            self.current = cand
            self._pending, self._pending_n = None, 0
        return self.current

    def update(self, rects, x: int, y: int):
        cand = find_snap_rect(rects, x, y)
        cur = self.current
        if cur is not None:
            inflated = (cur[0] - self.stick_px, cur[1] - self.stick_px,
                        cur[2] + self.stick_px, cur[3] + self.stick_px)
            if rect_contains(inflated, x, y):
                if cand is None or cand[:4] == cur[:4]:
                    self._pending, self._pending_n = None, 0
                    return cur
                # Chỉ nhường cho ô nhỏ hơn hẳn, và phải thắng liên tiếp
                if rect_area(cand) <= self.shrink_ratio * rect_area(cur):
                    return self._confirm(cand)
                self._pending, self._pending_n = None, 0
                return cur
        # Ngoài ô hiện tại: nhận ô ứng viên ngay
        self.current = cand
        self._pending, self._pending_n = None, 0
        return self.current


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


# ---------- Ánh xạ tọa độ logic (Qt) <-> vật lý (Win32 / ImageGrab) ----------
# Khi Windows scaling != 100%, tọa độ Qt (logic) và pixel vật lý lệch nhau
# theo devicePixelRatio của TỪNG màn hình. Hàm thuần dưới đây quy đổi 2 chiều;
# mọi dpr == 1 thì ánh xạ là đồng nhất (không đổi hành vi ở scaling 100%).

def build_screen_map(screens):
    """screens: list (lx, ly, lw, lh, dpr) theo tọa độ logic.

    Trả về list (lx, ly, lw, lh, dpr, px, py) với (px, py) là gốc VẬT LÝ
    suy ra của màn hình đó."""
    out = []
    for (lx, ly, lw, lh, dpr) in screens:
        dpr = float(dpr) if dpr else 1.0
        out.append((lx, ly, lw, lh, dpr, int(round(lx * dpr)), int(round(ly * dpr))))
    return out


def _screen_for_logical(smap, x, y):
    for s in smap:
        if s[0] <= x < s[0] + s[2] and s[1] <= y < s[1] + s[3]:
            return s
    return smap[0] if smap else None


def _screen_for_physical(smap, x, y):
    for s in smap:
        pw, ph = int(round(s[2] * s[4])), int(round(s[3] * s[4]))
        if s[5] <= x < s[5] + pw and s[6] <= y < s[6] + ph:
            return s
    return smap[0] if smap else None


def logical_to_physical(x, y, smap):
    s = _screen_for_logical(smap, x, y)
    if s is None or s[4] == 1.0:
        return (int(x), int(y))
    return (int(round(s[5] + (x - s[0]) * s[4])), int(round(s[6] + (y - s[1]) * s[4])))


def physical_to_logical(x, y, smap):
    s = _screen_for_physical(smap, x, y)
    if s is None or s[4] == 1.0:
        return (int(x), int(y))
    return (int(round(s[0] + (x - s[5]) / s[4])), int(round(s[1] + (y - s[6]) / s[4])))


def enumerate_rectangles(max_rects: int = 600) -> list:
    """Liệt kê cửa sổ hiển thị + khung con của cửa sổ đang active (Windows)."""
    if sys.platform != "win32":
        return []
    try:
        return _enumerate_win32(max_rects)
    except Exception:
        return []


def _setup_user32(user32, wt):
    """Khai báo chữ ký đầy đủ cho các hàm Win32 dùng ở đây.

    Thiếu restype, ctypes hiểu HWND là int 32-bit -> handle 64-bit bị cắt,
    liệt kê sai cửa sổ mà không báo lỗi. Trả về module dwmapi (hoặc None).
    """
    import ctypes
    user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user32.GetWindowRect.restype = wt.BOOL
    user32.IsWindowVisible.argtypes = [wt.HWND]
    user32.IsWindowVisible.restype = wt.BOOL
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user32.GetWindowThreadProcessId.restype = wt.DWORD
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetCursorPos.restype = wt.BOOL
    user32.WindowFromPoint.argtypes = [wt.POINT]
    user32.WindowFromPoint.restype = wt.HWND
    user32.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
    user32.GetAncestor.restype = wt.HWND
    try:
        dwm = ctypes.windll.dwmapi
        dwm.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
        dwm.DwmGetWindowAttribute.restype = ctypes.c_long  # HRESULT
        return dwm
    except Exception:
        return None


_DWMWA_EXTENDED_FRAME_BOUNDS = 9
_GA_ROOT = 2


def _window_frame(user32, dwm, hwnd, extended: bool):
    """Khung cửa sổ. extended=True dùng DWM extended frame bounds: KHÍT với
    phần cửa sổ nhìn thấy, không gồm viền resize vô hình (~7px/cạnh) và bóng
    đổ như GetWindowRect."""
    import ctypes
    import ctypes.wintypes as wt
    r = wt.RECT()
    if extended and dwm is not None:
        hr = dwm.DwmGetWindowAttribute(
            hwnd, _DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r))
        if hr == 0 and (r.right - r.left) > 0:
            return (r.left, r.top, r.right, r.bottom)
    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return (r.left, r.top, r.right, r.bottom)
    return None


def _enumerate_win32(max_rects: int) -> list:
    import ctypes
    import ctypes.wintypes as wt
    import os

    user32 = ctypes.windll.user32
    dwm = _setup_user32(user32, wt)
    own_pid = os.getpid()
    rects: list = []
    seen = set()

    def is_own(hwnd):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == own_pid

    def add(hwnd, extended: bool):
        frame = _window_frame(user32, dwm, hwnd, extended)
        if not frame:
            return
        w, h = frame[2] - frame[0], frame[3] - frame[1]
        if w < 16 or h < 16:
            return
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value or ""
        if frame in seen and not title:
            return
        seen.add(frame)
        rects.append((frame[0], frame[1], frame[2], frame[3], title))

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def enum_top(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not is_own(hwnd):
            add(hwnd, extended=True)
        return True

    user32.EnumWindows(CB(enum_top), 0)

    # Ô con liệt kê cho HAI gốc: cửa sổ foreground VÀ cửa sổ nằm dưới con trỏ
    # — rê chuột sang ứng dụng nào cũng có ô chi tiết ở đó, thay vì chỉ 1 cửa sổ.
    roots = []
    fg = user32.GetForegroundWindow()
    if fg and not is_own(fg):
        roots.append(fg)
    pt = wt.POINT()
    if user32.GetCursorPos(ctypes.byref(pt)):
        under = user32.WindowFromPoint(pt)
        if under:
            root = user32.GetAncestor(under, _GA_ROOT) or under
            if root and not is_own(root) and root not in roots:
                roots.append(root)
    if not roots:
        found = []

        def enum_first(hwnd, _):
            if user32.IsWindowVisible(hwnd) and not is_own(hwnd):
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(CB(enum_first), 0)
        if found:
            roots = found[:1]

    for root in roots:
        def enum_child(hwnd, _):
            if user32.IsWindowVisible(hwnd):  # bỏ ô ẩn/khung chứa vô hình
                add(hwnd, extended=False)
            return len(rects) < max_rects

        user32.EnumChildWindows(root, CB(enum_child), 0)
        if len(rects) >= max_rects:
            break

    # Bỏ các rect trùng hệt nhau, giữ bản có tiêu đề
    uniq: dict = {}
    for r in rects:
        k = r[:4]
        if k not in uniq or (r[4] and not uniq[k][4]):
            uniq[k] = r
    return list(uniq.values())[:max_rects]
