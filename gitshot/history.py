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
        """Nạp từng mục một: mục nào hỏng chỉ bỏ mục đó, không mất cả lịch sử."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            raw = []
        items = []
        if isinstance(raw, list):
            for x in raw:
                try:
                    if isinstance(x, dict):
                        items.append(HistoryItem(**{k: v for k, v in x.items()
                                                    if k in HistoryItem.__dataclass_fields__}))
                except Exception:
                    continue
        self.items = items

    def _save(self):
        from .utils import atomic_write_text
        atomic_write_text(
            self.path,
            json.dumps([asdict(i) for i in self.items], ensure_ascii=False, indent=2),
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

    def mark_uploaded_by_filename(self, filename: str, url: str) -> None:
        for it in self.items:
            if it.filename == filename:
                it.uploaded_url = url
                break
        self._save()

    def remove(self, item: "HistoryItem") -> None:
        self.items = [i for i in self.items if i is not item]
        self._save()

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")
