"""Logic tổ hợp phím thuần (không phụ thuộc Qt) — dùng cho ô tự thiết lập phím tắt.

Định dạng chuẩn (thư viện `keyboard` hiểu được): "ctrl+shift+1", "alt+f9",
"ctrl+alt+print screen". Tên phím chính: chữ thường, số, f1–f24 và các tên
đặc biệt: space, tab, enter, print screen, insert, delete, home, end,
page up, page down, up, down, left, right, backspace, caps lock, hoặc 1 ký tự
dấu câu như , . / ; ' [ ] - = \\ `
"""
from __future__ import annotations

MOD_ORDER = ["ctrl", "alt", "shift", "windows"]
MODIFIERS = set(MOD_ORDER)
NO_MODIFIER_KEYS = {f"f{i}" for i in range(1, 25)} | {"print screen"}


SPECIAL_KEYS = {
    "space", "tab", "enter", "print screen", "insert", "delete", "home", "end",
    "page up", "page down", "up", "down", "left", "right", "backspace",
    "caps lock", ",", ".", "/", ";", "'", "[", "]", "-", "=", "\\", "`",
}


def _is_known_key(key: str) -> bool:
    if len(key) == 1:
        return key.isalnum() or key in SPECIAL_KEYS
    if key in SPECIAL_KEYS:
        return True
    return key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24


def build_combo(modifiers, key: str) -> str:
    """Ghép danh sách modifier + phím chính thành tổ hợp chuẩn, đúng thứ tự."""
    mods = [m for m in MOD_ORDER if m in set(x.lower() for x in modifiers)]
    key = (key or "").strip().lower()
    return "+".join(mods + [key] if key else mods)


def split_combo(combo: str) -> tuple[list[str], str]:
    parts = [p.strip().lower() for p in (combo or "").split("+") if p.strip()]
    mods = [p for p in parts if p in MODIFIERS]
    keys = [p for p in parts if p not in MODIFIERS]
    return mods, (keys[-1] if keys else "")


def validate_combo(combo: str) -> str:
    """Trả về "" nếu hợp lệ, ngược lại là câu báo lỗi tiếng Việt."""
    if not combo or not combo.strip():
        return ""  # trống = không đặt phím tắt cho hành động này (hợp lệ)
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    mods = [p for p in parts if p in MODIFIERS]
    keys = [p for p in parts if p not in MODIFIERS]
    if not keys:
        return "Thiếu phím chính (hãy nhấn thêm 1 phím chữ/số/F)."
    if len(keys) > 1:
        return "Tổ hợp chỉ được có 1 phím chính."
    if len(set(mods)) != len(mods):
        return "Tổ hợp có phím bổ trợ bị lặp."
    key = keys[0]
    if not _is_known_key(key):
        return f"Phím '{key}' không được hỗ trợ."
    if not mods and key not in NO_MODIFIER_KEYS:
        return "Hãy thêm Ctrl, Alt hoặc Shift (chỉ phím F1–F24 và Print Screen mới được đứng một mình)."
    return ""


def find_conflicts(mapping: dict[str, str]) -> dict[str, list[str]]:
    """Tìm tổ hợp bị dùng cho nhiều hành động. Trả {combo: [hành động,...]}."""
    by_combo: dict[str, list[str]] = {}
    for action, combo in mapping.items():
        c = (combo or "").strip().lower()
        if c:
            by_combo.setdefault(c, []).append(action)
    return {c: acts for c, acts in by_combo.items() if len(acts) > 1}


def prettify(combo: str) -> str:
    """Hiển thị đẹp: 'ctrl+shift+1' -> 'Ctrl + Shift + 1'."""
    if not combo:
        return "— chưa đặt —"
    names = {
        "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "windows": "Win",
        "space": "Space", "enter": "Enter", "tab": "Tab",
        "print screen": "Print Screen", "page up": "Page Up", "page down": "Page Down",
        "backspace": "Backspace", "caps lock": "Caps Lock",
        "up": "↑", "down": "↓", "left": "←", "right": "→",
    }
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    return " + ".join(names.get(p, p.upper() if len(p) == 1 else p.title()) for p in parts)
