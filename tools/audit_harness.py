"""Harness kiểm tra chức năng cho đợt rà soát GitShot (chạy trên Linux, không GUI).

Chạy: python3 tools/audit_harness.py
Mỗi kiểm tra in PASS/FAIL kèm ghi chú — FAIL ở đây nghĩa là HÀNH VI CẦN XEM LẠI
(không hẳn là crash), phục vụ báo cáo rà soát.
"""
import io
import json
import sys
import tempfile
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

RESULTS = []


def check(name, fn):
    try:
        note = fn()
        RESULTS.append(("PASS", name, note or ""))
    except AssertionError as e:
        RESULTS.append(("FAIL", name, str(e)))
    except Exception as e:  # noqa: BLE001
        RESULTS.append(("ERROR", name, f"{type(e).__name__}: {e}"))


# ---------- 1. Tên file có thật sự duy nhất? ----------
def t_filename_collision():
    from gitshot.utils import make_filename
    now = datetime(2026, 11, 5, 10, 0, 0)
    a = make_filename(now=now)
    b = make_filename(now=now)
    assert a != b, f"2 ảnh chụp trong cùng 1 giây trùng tên: {a} == {b} (ghi đè file + trùng đường dẫn upload)"
check("make_filename duy nhất trong cùng giây", t_filename_collision)


# ---------- 2. Config hỏng / sai kiểu dữ liệu ----------
def t_config_corrupt_json():
    from gitshot.config import AppConfig
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "config.json"
        p.write_text("{ hỏng json")
        cfg = AppConfig.load(p)
        assert cfg.github.repo == "gitshot-uploads", "config hỏng phải về mặc định an toàn"
check("Config JSON hỏng -> mặc định", t_config_corrupt_json)


def t_config_wrong_types():
    from gitshot.config import AppConfig
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "config.json"
        p.write_text(json.dumps({"github": {"token": 12345}, "record_fps": "mười lăm",
                                 "corner_radius": "mười", "last_region": "không-phải-list"}))
        cfg = AppConfig.load(p)
        assert isinstance(cfg.github.token, str), f"token bị nạp thành {type(cfg.github.token)} (uploader sẽ lỗi lạ)"
        assert isinstance(cfg.record_fps, int), "record_fps bị nạp thành chuỗi"
        assert isinstance(cfg.corner_radius, int), "corner_radius chuỗi -> QSpinBox.setValue crash khi mở Cài đặt"
check("Config sai kiểu dữ liệu được chuẩn hóa", t_config_wrong_types)


def t_config_save_atomic():
    import inspect
    from gitshot import config
    src = inspect.getsource(config.AppConfig.save)
    assert "atomic" in src or "tmp" in src or "replace" in src, \
        "save() ghi thẳng file thật: crash giữa chừng = hỏng config, mất token"
check("Config save nguyên tử (ghi tmp rồi thay)", t_config_save_atomic)


# ---------- 3. History: 1 mục hỏng có làm mất cả lịch sử? ----------
def t_history_one_bad_item():
    from gitshot.history import History
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "history.json"
        good = {"filename": "a.png", "local_path": "/tmp/a.png", "created_at": "2026-11-05T10:00:00"}
        bad = {"filename": "b.png"}  # thiếu trường bắt buộc
        p.write_text(json.dumps([good, bad]))
        h = History(p)
        assert len(h.items) == 1, f"1 mục hỏng làm mất cả lịch sử (còn {len(h.items)} mục)"
check("History: 1 mục hỏng không xóa cả lịch sử", t_history_one_bad_item)


# ---------- 4. Uploader với server GitHub giả ----------
class FakeGitHub(BaseHTTPRequestHandler):
    store = {}
    fail_mode = None

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    repos = set()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/user/repos":
            FakeGitHub.repos.add("tester/gitshot-uploads")
            FakeGitHub.repos.add("tester/r")
            return self._send(201, {"full_name": "tester/gitshot-uploads"})
        return self._send(404, {"message": "Not Found"})

    def do_GET(self):
        if self.path == "/user":
            return self._send(200, {"login": "tester"})
        if self.path.startswith("/repos/") and "/contents/" not in self.path:
            key = self.path[len("/repos/"):]
            return self._send(200, {}) if key in FakeGitHub.repos else self._send(404, {"message": "Not Found"})
        if self.path.startswith("/repos/") and "/contents/" in self.path:
            key = self.path.split("/contents/")[1]
            if key in self.store:
                return self._send(200, {"sha": "abc123", "name": key})
            return self._send(404, {"message": "Not Found"})
        return self._send(404, {"message": "Not Found"})

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if FakeGitHub.fail_mode == "conflict":
            return self._send(409, {"message": "sha required"})
        key = self.path.split("/contents/")[1]
        FakeGitHub.store[key] = payload
        return self._send(201, {"content": {"name": key, "path": key}})


def with_server(fn):
    FakeGitHub.store = {}
    FakeGitHub.fail_mode = None
    srv = HTTPServer(("127.0.0.1", 0), FakeGitHub)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        fn(f"http://127.0.0.1:{port}")
    finally:
        srv.shutdown()


def make_opener(base):
    import urllib.error
    import urllib.request
    def opener(req):
        url = req.full_url.replace("https://api.github.com", base)
        new_req = urllib.request.Request(url, data=req.data, method=req.get_method())
        for k, v in req.header_items():
            new_req.add_header(k, v)
        try:
            with urllib.request.urlopen(new_req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode() or "{}")
            except Exception:
                return e.code, {}
    return opener


def t_upload_basic_and_links():
    from gitshot.github_uploader import GitHubUploader
    def run(base):
        up = GitHubUploader("tok", opener=make_opener(base))
        r = up.upload_bytes(b"\x89PNG fake", "shot_1.png", owner="tester", repo="gitshot-uploads")
        assert "uploads/" in r.path and r.path.endswith("shot_1.png"), r.path
        assert r.link("raw").startswith("https://raw.githubusercontent.com/tester/gitshot-uploads/main/"), r.link("raw")
    with_server(run)
check("Uploader: tải file mới + link raw/cdn", t_upload_basic_and_links)


def t_upload_duplicate_gets_sha():
    from gitshot.github_uploader import GitHubUploader
    def run(base):
        up = GitHubUploader("tok", opener=make_opener(base))
        up.upload_bytes(b"v1", "dup.png", owner="tester", repo="r")
        r2 = up.upload_bytes(b"v2", "dup.png", owner="tester", repo="r")
        assert r2.path.endswith("dup.png")
    with_server(run)
check("Uploader: trùng tên -> lấy sha ghi đè", t_upload_duplicate_gets_sha)


# ---------- 5. tools_extra ----------
def t_tools_extra():
    from gitshot.tools_extra import combine_images, file_hashes, make_thumbnail, split_image
    a = Image.new("RGB", (100, 50), (255, 0, 0))
    b = Image.new("RGB", (80, 50), (0, 0, 255))
    v = combine_images([a, b], "vertical")
    assert v.size == (100, 108), f"ghép dọc sai kích thước: {v.size} (kỳ vọng 100x108 gồm gap 8 mặc định)"
    parts = split_image(Image.new("RGB", (101, 51)), 2, 2)
    assert len(parts) == 4 and parts[0].size[0] in (50, 51), "tách lưới sai"
    th = make_thumbnail(Image.new("RGB", (400, 200)), 100)
    assert max(th.size) == 100, "thumbnail sai"
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello")
        name = f.name
    h = file_hashes(Path(name))
    assert h["md5"] == "5d41402abc4b2a76b9719d911017c592", "hash sai"
check("tools_extra: ghép/tách/thumbnail/hash", t_tools_extra)


# ---------- 6. stitch (chụp cuộn) ----------
def t_stitch_overlap():
    from gitshot.stitch import stitch_images
    base = Image.new("RGB", (60, 300))
    px = base.load()
    for y in range(300):
        for x in range(60):
            px[x, y] = (y % 256, x, 128)
    top = base.crop((0, 0, 60, 100))
    nxt = base.crop((0, 60, 60, 160))  # chồng 40px với top
    out = stitch_images([top, nxt])
    assert out.size[1] == 160, f"ghép cuộn sai chiều cao: {out.size[1]} (kỳ vọng 160)"
check("stitch: khử phần chồng khi ghép cuộn", t_stitch_overlap)


# ---------- 7. hotkeys_util ----------
def t_hotkeys():
    from gitshot.hotkeys_util import build_combo, find_conflicts, validate_combo
    assert build_combo(["shift", "ctrl"], "a") == "ctrl+shift+a"
    assert validate_combo("a") != "", "phím trơ không modifier phải bị chặn"
    assert validate_combo("ctrl+shift+a") == ""
    c = find_conflicts({"region": "ctrl+shift+1", "window": "ctrl+shift+1", "gif": ""})
    assert "ctrl+shift+1" in c, "không phát hiện trùng"
check("hotkeys_util: build/validate/conflict", t_hotkeys)


def main():
    width = max(len(n) for _, n, _ in RESULTS)
    fails = 0
    for status, name, note in RESULTS:
        print(f"[{status:5}] {name:<{width}}  {note}")
        if status != "PASS":
            fails += 1
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} PASS — {fails} mục cần xem lại")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
