"""Bộ công cụ phụ — logic thuần PIL/hashlib, có unit test."""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


def combine_images(images: list[Image.Image], direction: str = "vertical", gap: int = 8,
                   bg: str = "#0b0e1a") -> Image.Image:
    """Ghép nhiều ảnh thành 1: dọc (căn giữa theo chiều ngang) hoặc ngang."""
    imgs = [im.convert("RGB") for im in images if im is not None]
    if not imgs:
        raise ValueError("Chưa chọn ảnh nào để ghép")
    if direction == "vertical":
        w = max(i.size[0] for i in imgs)
        h = sum(i.size[1] for i in imgs) + gap * (len(imgs) - 1)
        canvas = Image.new("RGB", (w, h), bg)
        y = 0
        for im in imgs:
            canvas.paste(im, ((w - im.size[0]) // 2, y))
            y += im.size[1] + gap
        return canvas
    w = sum(i.size[0] for i in imgs) + gap * (len(imgs) - 1)
    h = max(i.size[1] for i in imgs)
    canvas = Image.new("RGB", (w, h), bg)
    x = 0
    for im in imgs:
        canvas.paste(im, (x, (h - im.size[1]) // 2))
        x += im.size[0] + gap
    return canvas


def split_image(img: Image.Image, rows: int, cols: int) -> list[Image.Image]:
    """Tách 1 ảnh thành lưới rows x cols (phần thừa dồn vào ô cuối)."""
    if rows < 1 or cols < 1:
        raise ValueError("Số hàng/cột phải >= 1")
    w, h = img.size
    # Lưới không được mịn hơn số pixel (tránh sinh ô 0 pixel)
    rows, cols = min(rows, h), min(cols, w)
    cw, ch = w // cols, h // rows
    parts = []
    for r in range(rows):
        for c in range(cols):
            x2 = w if c == cols - 1 else (c + 1) * cw
            y2 = h if r == rows - 1 else (r + 1) * ch
            parts.append(img.crop((c * cw, r * ch, x2, y2)))
    return parts


def file_hashes(path: Path) -> dict[str, str]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha.hexdigest()}


def make_thumbnail(img: Image.Image, max_side: int = 800) -> Image.Image:
    out = img.copy()
    out.thumbnail((max_side, max_side), Image.LANCZOS)
    return out


def ocr_image(img: Image.Image, lang: str = "vie+eng") -> str:
    """Trích chữ bằng Tesseract nếu máy có cài; không có -> báo rõ cách cài."""
    import shutil
    if shutil.which("tesseract") is None:
        raise RuntimeError(
            "Máy chưa có Tesseract OCR nên tính năng này chưa dùng được. "
            "Cài Tesseract từ https://github.com/UB-Mannheim/tesseract/wiki rồi mở lại app. "
            "(Bản .exe hiện chưa đóng gói kèm Tesseract.)"
        )
    try:
        import pytesseract
    except ImportError as e:
        raise RuntimeError(
            "Thiếu thư viện pytesseract (chỉ gặp khi chạy từ mã nguồn: pip install pytesseract)."
        ) from e
    try:
        return pytesseract.image_to_string(img, lang=lang).strip()
    except Exception:
        # Thiếu gói ngôn ngữ vie -> thử tiếng Anh
        try:
            return pytesseract.image_to_string(img, lang="eng").strip()
        except Exception as e2:
            raise RuntimeError(
                "Không chạy được Tesseract. Hãy chắc chắn đã cài Tesseract OCR và thêm vào PATH."
            ) from e2
