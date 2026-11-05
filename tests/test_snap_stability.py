"""Test chống nhảy ô: StableRectTracker + tie-break xác định của find_snap_rect."""
import random
import unittest

from gitshot.windows_detect import StableRectTracker, find_snap_rect

WIN = (0, 0, 800, 600, "Cửa sổ")
BTN = (100, 100, 220, 150, "Nút bấm")
PANEL_A = (40, 40, 420, 320, "")
PANEL_B = (46, 46, 426, 326, "")   # ô chồng gần bằng PANEL_A (lệch vài px)


class TestDeterministicPick(unittest.TestCase):
    def test_shuffled_input_same_result(self):
        rects = [WIN, BTN, PANEL_A, PANEL_B]
        expected = find_snap_rect(rects, 150, 120)
        for _ in range(20):
            shuffled = rects[:]
            random.shuffle(shuffled)
            self.assertEqual(find_snap_rect(shuffled, 150, 120), expected)

    def test_smallest_wins(self):
        self.assertEqual(find_snap_rect([WIN, BTN], 150, 120), BTN)


class TestStableTracker(unittest.TestCase):
    def test_no_flicker_between_overlapping_panels(self):
        """Di chuột trong vùng giao nhau của 2 ô chồng nhau: ô giữ nguyên."""
        t = StableRectTracker()
        rects = [WIN, PANEL_A, PANEL_B]
        first = t.update(rects, 200, 200)
        for x, y in [(201, 200), (199, 202), (205, 198), (200, 200), (203, 204)]:
            self.assertEqual(t.update(rects, x, y), first)

    def test_point_leaves_rect_switches(self):
        t = StableRectTracker()
        rects = [WIN, BTN]
        self.assertEqual(t.update(rects, 150, 120), BTN)
        # Ra khỏi nút (vẫn trong cửa sổ) -> chuyển sang cửa sổ ngay
        self.assertEqual(t.update(rects, 500, 400), WIN)

    def test_smaller_candidate_needs_confirmation(self):
        """Ô nhỏ hơn hẳn xuất hiện 1 nhịp không được cướp; 2 nhịp liên tiếp mới chuyển."""
        t = StableRectTracker()
        big_only = [WIN]
        with_btn = [WIN, BTN]
        self.assertEqual(t.update(big_only, 150, 120), WIN)
        once = t.update(with_btn, 150, 120)
        self.assertEqual(once, WIN)               # nhịp 1: chưa chuyển
        self.assertEqual(t.update(with_btn, 150, 120), BTN)  # nhịp 2: chuyển

    def test_similar_size_candidate_never_steals(self):
        """Ô ứng viên to gần bằng ô hiện tại (không nhỏ hơn hẳn) không được cướp."""
        t = StableRectTracker()
        rects = [WIN, PANEL_A, PANEL_B]
        first = t.update(rects, 200, 200)
        for _ in range(5):
            self.assertEqual(t.update(rects, 200, 200), first)

    def test_none_outside_all_rects(self):
        t = StableRectTracker()
        self.assertIsNone(t.update([WIN], 900, 700))
        self.assertIsNone(t.current)


if __name__ == "__main__":
    unittest.main()
