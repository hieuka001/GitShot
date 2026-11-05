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


def _rows_match(a: tuple[int, ...], b: tuple[int, ...], tol: int = 0) -> bool:
    # Ảnh chụp màn hình là PNG không mất dữ liệu -> hàng trùng phải khớp tuyệt đối.
    # Dùng sai số > 0 sẽ gây nhận nhầm trên các vùng gradient trơn.
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def find_overlap(top: Image.Image, bottom: Image.Image, min_overlap: int = 8) -> int:
    """Số hàng của `bottom` đã xuất hiện ở cuối `top` (0 nếu không chồng)."""
    if top.size[0] != bottom.size[0]:
        bottom = bottom.resize(top.size)
    sig_top = _row_signature(top)
    sig_bottom = _row_signature(bottom)
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


def stitch_images(images: list[Image.Image]) -> Image.Image:
    """Ghép danh sách ảnh (theo thứ tự cuộn xuống) thành 1 ảnh dài."""
    imgs = [im.convert("RGB") for im in images if im is not None]
    if not imgs:
        raise ValueError("Không có ảnh để ghép")
    result = imgs[0]
    for nxt in imgs[1:]:
        if nxt.size[0] != result.size[0]:
            nxt = nxt.resize((result.size[0], int(nxt.size[1] * result.size[0] / nxt.size[0])))
        overlap = find_overlap(result, nxt)
        if overlap >= nxt.size[1]:
            continue  # ảnh mới nằm trọn trong ảnh cũ (cuộn không đổi)
        piece = nxt.crop((0, overlap, nxt.size[0], nxt.size[1]))
        canvas = Image.new("RGB", (result.size[0], result.size[1] + piece.size[1]))
        canvas.paste(result, (0, 0))
        canvas.paste(piece, (0, result.size[1]))
        result = canvas
    return result
