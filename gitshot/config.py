"""Cấu hình GitShot — lưu tại %APPDATA%/GitShot/config.json (Windows)
hoặc ~/.config/GitShot/config.json (hệ khác).

Token GitHub CHỈ lưu trên máy người dùng, không bao giờ nằm trong code/repo.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "GitShot"
    return Path.home() / ".config" / "GitShot"


def data_dir() -> Path:
    d = config_dir() / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class GitHubConfig:
    token: str = ""
    owner: str = ""                       # để trống = tự lấy từ token
    repo: str = "gitshot-uploads"         # repo CHỨA ẢNH (nên để Public để link mở được)
    branch: str = "main"
    folder_pattern: str = "uploads/{yyyy}/{MM}"
    link_type: str = "raw"                # raw | cdn
    copy_format: str = "link"             # link | markdown | html
    auto_copy: bool = True
    auto_create_repo: bool = True


@dataclass
class HotkeyConfig:
    region: str = "ctrl+shift+1"
    fullscreen: str = "ctrl+shift+2"
    window: str = "ctrl+shift+3"
    scrolling: str = "ctrl+shift+4"
    record: str = "ctrl+shift+5"
    gif: str = "ctrl+shift+6"
    last_region: str = "ctrl+shift+7"
    color_picker: str = "ctrl+shift+8"


@dataclass
class AppConfig:
    github: GitHubConfig = field(default_factory=GitHubConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    save_local_copy: bool = True
    local_folder: str = ""                # trống = Pictures/GitShot
    open_editor_after_capture: bool = True
    record_fps: int = 15
    smart_snap: bool = True               # chụp vùng: tự nhận ô/cửa sổ có sẵn
    rounded_corners: bool = True          # ảnh chụp theo ô/cửa sổ được bo góc tròn
    corner_radius: int = 10
    last_region: list = field(default_factory=list)  # [x1, y1, x2, y2]

    # ---------- load / save ----------
    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or (config_dir() / "config.json")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        cfg = cls()
        gh = raw.get("github") or {}
        for k, v in gh.items():
            if hasattr(cfg.github, k):
                setattr(cfg.github, k, v)
        hk = raw.get("hotkeys") or {}
        for k, v in hk.items():
            if hasattr(cfg.hotkeys, k):
                setattr(cfg.hotkeys, k, v)
        for k in ("save_local_copy", "local_folder", "open_editor_after_capture", "record_fps",
                  "smart_snap", "rounded_corners", "corner_radius", "last_region"):
            if k in raw:
                setattr(cfg, k, raw[k])
        return cfg

    def save(self, path: Path | None = None) -> Path:
        path = path or (config_dir() / "config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def pictures_folder(self) -> Path:
        if self.local_folder:
            p = Path(self.local_folder)
        else:
            p = Path.home() / "Pictures" / "GitShot"
        p.mkdir(parents=True, exist_ok=True)
        return p
