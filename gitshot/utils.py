"""Hàm tiện ích thuần (không phụ thuộc GUI) — có unit test riêng."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime


def make_filename(prefix: str = "shot", ext: str = "png", now: datetime | None = None) -> str:
    """Tên file duy nhất dạng shot_2026-11-05_14-30-05.png."""
    now = now or datetime.now()
    ext = ext.lstrip(".").lower() or "png"
    return f"{prefix}_{now:%Y-%m-%d_%H-%M-%S}.{ext}"


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
    """Ba dạng link cho 1 file đã upload lên GitHub."""
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    cdn = f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}"
    page = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
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
