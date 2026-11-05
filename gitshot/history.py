"""Lịch sử ảnh đã chụp / đã upload — lưu JSON trong thư mục dữ liệu của app."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .config import data_dir


@dataclass
class HistoryItem:
    filename: str
    local_path: str
    created_at: str
    uploaded_url: str = ""
    kind: str = "image"  # image | video | gif
    size: int = 0


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "history.json")
        self.items: list[HistoryItem] = []
        self._load()

    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [HistoryItem(**x) for x in raw]
        except Exception:
            self.items = []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(i) for i in self.items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, item: HistoryItem) -> None:
        self.items.insert(0, item)
        self.items = self.items[:500]
        self._save()

    def mark_uploaded(self, local_path: str, url: str) -> None:
        for it in self.items:
            if it.local_path == local_path:
                it.uploaded_url = url
                break
        self._save()

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")
