"""Test ánh xạ tọa độ logic <-> vật lý theo DPI từng màn hình."""
import unittest

from gitshot.windows_detect import (
    build_screen_map, logical_to_physical, physical_to_logical,
)


class TestScreenMap(unittest.TestCase):
    def test_dpr1_identity(self):
        smap = build_screen_map([(0, 0, 1920, 1080, 1.0)])
        self.assertEqual(logical_to_physical(500, 300, smap), (500, 300))
        self.assertEqual(physical_to_logical(500, 300, smap), (500, 300))

    def test_single_screen_150_percent(self):
        smap = build_screen_map([(0, 0, 1280, 720, 1.5)])
        self.assertEqual(logical_to_physical(100, 100, smap), (150, 150))
        self.assertEqual(physical_to_logical(150, 150, smap), (100, 100))
        # Điểm cuối màn hình logic -> cuối màn hình vật lý (1920x1080)
        self.assertEqual(logical_to_physical(1279, 719, smap), (1918, 1078))

    def test_roundtrip_mixed(self):
        smap = build_screen_map([
            (0, 0, 1920, 1080, 1.0),
            (1920, 0, 1280, 720, 1.5),
        ])
        for pt in [(100, 100), (2000, 100), (2500, 600), (1919, 1079)]:
            phys = logical_to_physical(*pt, smap)
            self.assertEqual(physical_to_logical(*phys, smap), pt, f"roundtrip {pt}")

    def test_second_screen_uses_its_own_dpr(self):
        smap = build_screen_map([
            (0, 0, 1920, 1080, 1.0),
            (1920, 0, 1280, 720, 1.5),
        ])
        # Gốc logic 1920 của màn 2 -> gốc vật lý 1920*1.5 = 2880 theo quy ước ánh xạ
        self.assertEqual(logical_to_physical(1920, 0, smap), (2880, 0))
        self.assertEqual(logical_to_physical(2020, 100, smap), (3030, 150))


if __name__ == "__main__":
    unittest.main()
