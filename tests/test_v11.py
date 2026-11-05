import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from gitshot.capture import apply_rounded_corners
from gitshot.tools_extra import combine_images, file_hashes, make_thumbnail, split_image
from gitshot.windows_detect import find_snap_rect, snap_edges

RECTS = [
    (0, 0, 1920, 1080, "Desktop"),
    (100, 100, 900, 700, "Trình duyệt"),
    (150, 200, 500, 320, "Ô tìm kiếm"),
    (600, 200, 850, 320, "Nút bấm"),
]


class TestSnap(unittest.TestCase):
    def test_smallest_containing(self):
        r = find_snap_rect(RECTS, 300, 250)
        self.assertEqual(r[4], "Ô tìm kiếm")  # ô nhỏ nhất chứa điểm, không phải cả cửa sổ

    def test_falls_back_to_window(self):
        r = find_snap_rect(RECTS, 950, 800)
        self.assertEqual(r[4], "Desktop")

    def test_none_outside(self):
        self.assertIsNone(find_snap_rect(RECTS, 5000, 5000))

    def test_snap_edges_within_threshold(self):
        out = snap_edges((108, 96, 905, 690), RECTS, threshold=12)
        self.assertEqual(out, (100, 100, 900, 700))

    def test_no_snap_far_away(self):
        bbox = (300, 300, 400, 400)
        self.assertEqual(snap_edges(bbox, RECTS, threshold=6), bbox)


class TestRoundedCorners(unittest.TestCase):
    def test_corners_transparent_center_opaque(self):
        img = Image.new("RGB", (100, 80), (200, 30, 30))
        out = apply_rounded_corners(img, radius=12)
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((0, 0))[3], 0)      # góc trong suốt
        self.assertEqual(out.getpixel((50, 40))[3], 255)   # giữa đục
        self.assertEqual(out.getpixel((50, 0))[3], 255)    # cạnh giữa đục


class TestToolsExtra(unittest.TestCase):
    def test_combine_vertical(self):
        a = Image.new("RGB", (100, 50), "red")
        b = Image.new("RGB", (80, 40), "blue")
        out = combine_images([a, b], "vertical", gap=10)
        self.assertEqual(out.size, (100, 100))

    def test_combine_horizontal(self):
        a = Image.new("RGB", (100, 50), "red")
        b = Image.new("RGB", (80, 40), "blue")
        out = combine_images([a, b], "horizontal", gap=0)
        self.assertEqual(out.size, (180, 50))

    def test_split_grid(self):
        img = Image.new("RGB", (101, 61), "white")
        parts = split_image(img, 2, 3)
        self.assertEqual(len(parts), 6)
        # ô cuối cùng phải gánh phần thừa để tổng khớp kích thước gốc
        self.assertEqual(sum(p.size[0] for p in parts[:3]), 101)
        self.assertEqual(parts[0].size[1] + parts[3].size[1], 61)

    def test_hash(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"gitshot")
            path = Path(f.name)
        h = file_hashes(path)
        self.assertEqual(len(h["md5"]), 32)
        self.assertEqual(len(h["sha256"]), 64)
        path.unlink()

    def test_thumbnail(self):
        img = Image.new("RGB", (2000, 1000), "white")
        out = make_thumbnail(img, 800)
        self.assertEqual(out.size, (800, 400))


if __name__ == "__main__":
    unittest.main()
