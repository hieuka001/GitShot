import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitshot.hotkeys_util import build_combo, find_conflicts, prettify, validate_combo


class TestHotkeysUtil(unittest.TestCase):
    def test_build_orders_modifiers(self):
        self.assertEqual(build_combo(["shift", "ctrl"], "A"), "ctrl+shift+a")
        self.assertEqual(build_combo(["alt"], "F9"), "alt+f9")
        self.assertEqual(build_combo([], "print screen"), "print screen")

    def test_validate(self):
        self.assertEqual(validate_combo("ctrl+shift+1"), "")
        self.assertEqual(validate_combo(""), "")            # trống = chưa đặt, hợp lệ
        self.assertEqual(validate_combo("f5"), "")          # F đứng một mình được
        self.assertNotEqual(validate_combo("a"), "")        # chữ trơ -> phải có modifier
        self.assertNotEqual(validate_combo("ctrl+shift"), "")  # thiếu phím chính

    def test_conflicts(self):
        m = {"region": "ctrl+shift+1", "window": "ctrl+shift+1", "gif": "", "home": "ctrl+shift+2"}
        conf = find_conflicts(m)
        self.assertEqual(list(conf.keys()), ["ctrl+shift+1"])
        self.assertEqual(sorted(conf["ctrl+shift+1"]), ["region", "window"])

    def test_prettify(self):
        self.assertEqual(prettify("ctrl+shift+1"), "Ctrl + Shift + 1")
        self.assertEqual(prettify("alt+f9"), "Alt + F9")
        self.assertEqual(prettify(""), "— chưa đặt —")


if __name__ == "__main__":
    unittest.main()
