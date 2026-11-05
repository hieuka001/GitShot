"""Ghép ảnh chụp cuộn (scrolling capture) bằng cách tìm đoạn chồng lấp dọc.

Thuật toán: với mỗi ảnh tiếp theo, tìm vị trí chồng lấp lớn nhất mà các hàng
cuối của ảnh đã ghép trùng với các hàng đầu của ảnh mới (so sánh mức xám,
sai số nhỏ). Không tìm thấy -> nối thẳng (không chồng).
"""
from __future__ import annotations

from PIL import Image


def _row_signature(img: Image.Image, step: int = 4) -> list[tuple[int, ...]]:
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    sig = []
    for y in range(h):
        sig.append(tuple(px[x, y] for x in range(0, w, step)))
    return sig


def _rows_match(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    """Hai hàng coi như trùng khi >= 90% điểm mẫu GIỐNG HỆT và số điểm lệch
    hẳn (> 8 mức xám) cũng <= 10%.

    Lý do không dùng sai số đều: vùng gradient trơn dịch 1 hàng chỉ lệch mỗi
    điểm ~1 mức -> sai số đều sẽ nhận nhầm. Phần tử động trên trang thật
    (con trỏ nhấp nháy, đồng hồ giây) chỉ phá vài điểm mẫu, còn lại giống hệt
    vì cùng một lần render — tiêu chí "giống hệt đa số" phân biệt đúng cả hai.
    """
    if len(a) != len(b) or not a:
        return False
    exact = 0
    big = 0
    allowed_big = max(1, len(a) // 10)
    for x, y in zip(a, b):
        d = abs(x - y)
        if d == 0:
            exact += 1
        elif d > 8:
            big += 1
            if big > allowed_big:
                return False
    return exact * 10 >= len(a) * 9


def _find_overlap_sigs(sig_top, sig_bottom, min_overlap: int = 8) -> int:
    max_overlap = min(len(sig_top), len(sig_bottom)) - 1
    for overlap in range(max_overlap, min_overlap - 1, -1):
        start = len(sig_top) - overlap
        ok = True
        # Kiểm tra thưa 6 hàng đại diện cho nhanh, rồi kiểm tra kỹ nếu đạt
        probe = list(range(0, overlap, max(1, overlap // 6)))[:6]
        for i in probe:
            if not _rows_match(sig_top[start + i], sig_bottom[i]):
                ok = False
                break
        if not ok:
            continue
        if all(_rows_match(sig_top[start + i], sig_bottom[i]) for i in range(overlap)):
            return overlap
    return 0


def find_overlap(top: Image.Image, bottom: Image.Image, min_overlap: int = 8) -> int:
    """Số hàng của `bottom` đã xuất hiện ở cuối `top` (0 nếu không chồng)."""
    if top.size[0] != bottom.size[0]:
        bottom = bottom.resize((top.size[0], bottom.size[1]))
    return _find_overlap_sigs(_row_signature(top), _row_signature(bottom), min_overlap)


def stitch_images(images: list[Image.Image]) -> Image.Image:
    """Ghép danh sách ảnh (theo thứ tự cuộn xuống) thành 1 ảnh dài.

    Chữ ký hàng của ảnh kết quả được CACHE và nối dài dần — bản cũ tính lại
    chữ ký cho toàn bộ ảnh đã ghép ở mỗi frame khiến trang càng dài càng chậm.
    """
    imgs = [im.convert("RGB") for im in images if im is not None]
    if not imgs:
        raise ValueError("Không có ảnh để ghép")
    result = imgs[0]
    sig_result = _row_signature(result)
    for nxt in imgs[1:]:
        if nxt.size[0] != result.size[0]:
            nxt = nxt.resize((result.size[0], int(nxt.size[1] * result.size[0] / nxt.size[0])))
        sig_nxt = _row_signature(nxt)
        overlap = _find_overlap_sigs(sig_result, sig_nxt)
        if overlap >= nxt.size[1]:
            continue  # ảnh mới nằm trọn trong ảnh cũ (cuộn không đổi)
        piece = nxt.crop((0, overlap, nxt.size[0], nxt.size[1]))
        canvas = Image.new("RGB", (result.size[0], result.size[1] + piece.size[1]))
        canvas.paste(result, (0, 0))
        canvas.paste(piece, (0, result.size[1]))
        result = canvas
        sig_result = sig_result + sig_nxt[overlap:]
    return result
