import base64
import io
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw

from gitshot.github_uploader import GitHubUploader
from gitshot.stitch import find_overlap, stitch_images
from gitshot.utils import build_links, format_link, make_filename, make_upload_path, sanitize_repo_name


class FakeOpener:
    """Giả lập GitHub API: ghi lại request, trả đáp án theo kịch bản."""

    def __init__(self):
        self.requests = []
        self.repo_exists = False
        self.conflict_once = False

    def __call__(self, req):
        url = req.full_url
        method = req.get_method()
        body = json.loads(req.data.decode()) if req.data else {}
        self.requests.append((method, url, body))
        if url.endswith("/user") and method == "GET":
            return 200, {"login": "hieuka001"}
        if "/repos/" in url and method == "GET" and "contents" not in url:
            return (200, {"name": "gitshot-uploads"}) if self.repo_exists else (404, {"message": "Not Found"})
        if url.endswith("/user/repos") and method == "POST":
            self.repo_exists = True
            return 201, {"name": body["name"]}
        if "contents" in url and method == "PUT":
            if self.conflict_once:
                self.conflict_once = False
                return 422, {"message": "sha wasn't supplied"}
            path = url.split("contents/")[1]
            return 201, {"content": {
                "sha": "abc123",
                "download_url": f"https://raw.githubusercontent.com/hieuka001/gitshot-uploads/main/{path}",
                "html_url": f"https://github.com/hieuka001/gitshot-uploads/blob/main/{path}",
            }}
        if "contents" in url and method == "GET":
            return 200, {"sha": "oldsha"}
        return 404, {"message": "?"}


class TestUtils(unittest.TestCase):
    def test_filename(self):
        n = make_filename(now=datetime(2026, 11, 5, 14, 30, 5))
        self.assertEqual(n, "shot_2026-11-05_14-30-05.png")

    def test_upload_path(self):
        p = make_upload_path("uploads/{yyyy}/{MM}", "a.png", now=datetime(2026, 11, 5))
        self.assertEqual(p, "uploads/2026/11/a.png")

    def test_links(self):
        links = build_links("hieuka001", "gitshot-uploads", "main", "uploads/2026/11/a.png")
        self.assertEqual(links["raw"], "https://raw.githubusercontent.com/hieuka001/gitshot-uploads/main/uploads/2026/11/a.png")
        self.assertIn("cdn.jsdelivr.net", links["cdn"])

    def test_format(self):
        self.assertEqual(format_link("markdown", "http://x"), "![](http://x)")
        self.assertEqual(format_link("link", "http://x"), "http://x")

    def test_sanitize(self):
        self.assertEqual(sanitize_repo_name("My Repo!"), "My-Repo")
        self.assertEqual(sanitize_repo_name(""), "gitshot-uploads")


class TestUploader(unittest.TestCase):
    def test_upload_creates_repo_and_returns_raw_link(self):
        fake = FakeOpener()
        up = GitHubUploader("token123", opener=fake)
        data = b"\x89PNG fake"
        result = up.upload_bytes(data, "shot.png", owner="", repo="gitshot-uploads")
        self.assertTrue(result.raw_url.startswith("https://raw.githubusercontent.com/hieuka001/"))
        self.assertTrue(result.path.startswith("uploads/"))
        # request PUT phải chứa content base64 đúng
        put = [r for r in fake.requests if r[0] == "PUT"][0]
        self.assertEqual(base64.b64decode(put[2]["content"]), data)
        # repo chưa có -> phải có POST tạo repo
        self.assertTrue(any(r[0] == "POST" and r[1].endswith("/user/repos") for r in fake.requests))

    def test_upload_conflict_retries_with_sha(self):
        fake = FakeOpener()
        fake.repo_exists = True
        fake.conflict_once = True
        up = GitHubUploader("t", opener=fake)
        result = up.upload_bytes(b"x", "a.png", owner="hieuka001", repo="gitshot-uploads")
        self.assertEqual(result.sha, "abc123")
        puts = [r for r in fake.requests if r[0] == "PUT"]
        self.assertEqual(len(puts), 2)
        self.assertEqual(puts[1][2].get("sha"), "oldsha")

    def test_no_token_raises(self):
        up = GitHubUploader("", opener=FakeOpener())
        with self.assertRaises(Exception):
            up.whoami()


class TestStitch(unittest.TestCase):
    def _striped_image(self, y0, h=200, w=60):
        img = Image.new("RGB", (w, h), "white")
        d = ImageDraw.Draw(img)
        for y in range(h):
            v = (y0 + y) % 256
            d.line([(0, y), (w, y)], fill=(v, v, v))
        return img

    def test_overlap_and_stitch(self):
        a = self._striped_image(0)          # hàng 0..199
        b = self._striped_image(150)        # hàng 150..349 -> chồng 50 hàng
        self.assertEqual(find_overlap(a, b), 50)
        merged = stitch_images([a, b])
        self.assertEqual(merged.size, (60, 350))

    def test_stitch_single(self):
        a = self._striped_image(0, h=100)
        self.assertEqual(stitch_images([a]).size, (60, 100))


if __name__ == "__main__":
    unittest.main()
