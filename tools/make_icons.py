"""Vẽ bộ icon điều hướng của GitShot (line icon, nét sáng trên nền trong suốt).

Chạy: python tools/make_icons.py  -> assets/icons/{home,tools,history,settings}.png
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

S = 128
COLOR = (216, 226, 238, 255)  # #D8E2EE
W = 7                        # độ dày nét


def canvas():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def home():
    img, d = canvas()
    d.line([(24, 68), (64, 30), (104, 68)], fill=COLOR, width=W, joint="curve")
    d.line([(36, 58), (36, 102), (92, 102), (92, 58)], fill=COLOR, width=W, joint="curve")
    d.line([(55, 102), (55, 78), (73, 78), (73, 102)], fill=COLOR, width=W)
    return img


def tools():
    # Ba thanh trượt (sliders) — biểu tượng công cụ/điều chỉnh
    img, d = canvas()
    for y, knob_x in ((38, 84), (64, 44), (90, 70)):
        d.line([(24, y), (104, y)], fill=COLOR, width=W)
        d.ellipse([knob_x - 10, y - 10, knob_x + 10, y + 10], outline=COLOR, width=W)
    return img


def history():
    img, d = canvas()
    d.ellipse([24, 24, 104, 104], outline=COLOR, width=W)
    d.line([(64, 44), (64, 66), (82, 76)], fill=COLOR, width=W, joint="curve")
    return img


def settings():
    # Bánh răng: vòng tròn + 8 răng + lỗ giữa
    img, d = canvas()
    cx = cy = 64
    for i in range(8):
        a = math.radians(i * 45)
        x1, y1 = cx + 30 * math.cos(a), cy + 30 * math.sin(a)
        x2, y2 = cx + 44 * math.cos(a), cy + 44 * math.sin(a)
        d.line([(x1, y1), (x2, y2)], fill=COLOR, width=11)
    d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], outline=COLOR, width=W)
    d.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], outline=COLOR, width=W)
    return img


def main():
    out = Path(__file__).resolve().parent.parent / "assets" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in (("home", home), ("tools", tools), ("history", history), ("settings", settings)):
        fn().save(out / f"{name}.png")
        print("wrote", out / f"{name}.png")


if __name__ == "__main__":
    main()
