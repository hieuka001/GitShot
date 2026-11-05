"""Test các điểm mới/sửa của v1.5.0."""
import tempfile
import unittest
from pathlib import Path

from gitshot import utils
from gitshot.github_uploader import GitHubError, GitHubUploader
from gitshot.hotkeys_util import validate_combo


class TestCaptureScale(unittest.TestCase):
    def test_scale_100_percent(self):
        from gitshot.capture import compute_capture_scale
        self.assertEqual(compute_capture_scale(1920, 1080, 1920, 1080), (1.0, 1.0))

    def test_scale_150_percent(self):
        from gitshot.capture import compute_capture_scale
        sx, sy = compute_capture_scale(2880, 1620, 1920, 1080)
        self.assertAlmostEqual(sx, 1.5)
        self.assertAlmostEqual(sy, 1.5)

    def test_tiny_diff_ignored(self):
        from gitshot.capture import compute_capture_scale
        self.assertEqual(compute_capture_scale(1925, 1080, 1920, 1080), (1.0, 1.0))


class TestVersionCompare(unittest.TestCase):
    def test_newer(self):
        self.assertTrue(utils.is_newer_version("v1.5.0", "1.4.1"))
        self.assertTrue(utils.is_newer_version("v1.4.2", "1.4.1"))
        self.assertFalse(utils.is_newer_version("v1.4.1", "1.4.1"))
        self.assertFalse(utils.is_newer_version("v1.3.9", "1.4.1"))


class TestValidateStrict(unittest.TestCase):
    def test_two_main_keys_rejected(self):
        self.assertNotEqual(validate_combo("ctrl+a+b"), "")

    def test_unknown_key_rejected(self):
        self.assertNotEqual(validate_combo("ctrl+banana"), "")

    def test_ok_combos(self):
        self.assertEqual(validate_combo("ctrl+shift+1"), "")
        self.assertEqual(validate_combo("alt+f4"), "")


class TestUploaderRetry(unittest.TestCase):
    def test_retries_transient_then_succeeds(self):
        calls = {"n": 0}

        def flaky(req):
            calls["n"] += 1
            if calls["n"] < 3:
                raise GitHubError("mất mạng tạm thời")
            return 200, {"login": "me"}

        up = GitHubUploader("tok", opener=flaky)
        self.assertEqual(up.whoami(), "me")
        self.assertEqual(calls["n"], 3)

    def test_links_url_encoded(self):
        links = utils.build_links("o", "r", "main", "uploads/2026/11/ảnh đẹp.png")
        self.assertNotIn(" ", links["raw"])
        self.assertIn("%", links["raw"])


class TestRecorderStreaming(unittest.TestCase):
    def test_streams_frames_to_disk(self):
        try:
            import numpy as np
            import imageio  # noqa: F401
        except Exception:
            self.skipTest("thiếu numpy/imageio trong môi trường test")
        from gitshot.recorder import ScreenRecorder
        frames = [np.full((16, 16, 3), 120, dtype=np.uint8) for _ in range(5)]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "r.gif"
            rec = ScreenRecorder(None, fps=10, frame_source=iter(frames))
            rec.start(p)
            out = rec.stop_and_save()
            self.assertTrue(out.exists())
            self.assertEqual(rec.frames_written, 5)
            self.assertFalse(hasattr(rec, "frames"))  # không giữ frame trong RAM


if __name__ == "__main__":
    unittest.main()
