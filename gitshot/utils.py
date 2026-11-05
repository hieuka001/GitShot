"""Hàm tiện ích thuần (không phụ thuộc GUI) — có unit test riêng."""
from __future__ import annotations

import hashlib
import itertools
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

_counter = itertools.count()


def atomic_write_text(path: Path, text: str, backup: bool = True) -> None:
    """Ghi file NGUYÊN TỬ: ghi file tạm cùng thư mục rồi thay thế (os.replace).

    App bị tắt/crash giữa chừng khi ghi cũng không làm hỏng file thật.
    Giữ thêm 1 bản .bak của nội dung trước đó để khôi phục khi cần.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        try:
            shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))
        except Exception:
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def make_filename(prefix: str = "shot", ext: str = "png", now: datetime | None = None) -> str:
    """Tên file DUY NHẤT dạng shot_2026-11-05_14-30-05_12307.png.

    Thêm mili-giây + bộ đếm trong tiến trình: 2 lần chụp trong cùng 1 giây
    (thậm chí cùng mili-giây) vẫn khác tên — hết ghi đè ảnh cũ.
    """
    now = now or datetime.now()
    ext = ext.lstrip(".").lower() or "png"
    seq = next(_counter) % 100
    return f"{prefix}_{now:%Y-%m-%d_%H-%M-%S}_{now.microsecond // 1000:03d}{seq:02d}.{ext}"


def make_upload_path(folder_pattern: str, filename: str, now: datetime | None = None) -> str:
    """Đường dẫn trong repo, hỗ trợ pattern {yyyy} {MM} {dd}.

    Mặc định: uploads/{yyyy}/{MM}/<file>
    """
    now = now or datetime.now()
    folder = (
        (folder_pattern or "uploads/{yyyy}/{MM}")
        .replace("{yyyy}", f"{now:%Y}")
        .replace("{MM}", f"{now:%m}")
        .replace("{dd}", f"{now:%d}")
        .strip("/")
    )
    return f"{folder}/{filename}" if folder else filename


def build_links(owner: str, repo: str, branch: str, path: str) -> dict[str, str]:
    """Ba dạng link cho 1 file đã upload lên GitHub (đường dẫn được URL-encode)."""
    from urllib.parse import quote
    enc = quote(path, safe="/")
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{enc}"
    cdn = f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{enc}"
    page = f"https://github.com/{owner}/{repo}/blob/{branch}/{enc}"
    return {"raw": raw, "cdn": cdn, "page": page}


def format_link(kind: str, url: str) -> str:
    """Định dạng copy: link thuần / Markdown / HTML."""
    if kind == "markdown":
        return f"![]({url})"
    if kind == "html":
        return f'<img src="{url}" alt="">'
    return url


_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_repo_name(name: str) -> str:
    name = _SAFE.sub("-", (name or "").strip()).strip("-.")
    return name or "gitshot-uploads"


def short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _version_tuple(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer_version(latest: str, current: str) -> bool:
    """True nếu `latest` (vd 'v1.5.0') mới hơn `current` (vd '1.4.1')."""
    return _version_tuple(latest) > _version_tuple(current)
