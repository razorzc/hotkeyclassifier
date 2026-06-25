"""批次索引管理 —— labels/.batches.json。"""
import json
import os
from datetime import datetime, timezone

from utils.logger import get_logger

BATCH_INDEX = "labels/.batches.json"
DEFAULT_BATCH = "默认"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BatchManager:
    def __init__(self):
        self._data: dict = {}

    # ── 加载/保存 ─────────────────────────────────────
    def load(self) -> dict:
        if os.path.exists(BATCH_INDEX):
            try:
                with open(BATCH_INDEX, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                return self._data
            except (json.JSONDecodeError, IOError):
                pass
        self._data = {"batches": []}
        return self._data

    def save(self):
        os.makedirs(os.path.dirname(BATCH_INDEX), exist_ok=True)
        with open(BATCH_INDEX, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ── 当前批次 ──────────────────────────────────────
    def current_id(self) -> str:
        return self._data.get("current_batch", DEFAULT_BATCH)

    def set_current(self, batch_id: str):
        self._data["current_batch"] = batch_id
        self.save()

    # ── 确保默认存在 ──────────────────────────────────
    def ensure_default(self, username: str):
        self.load()
        if not self._data.get("batches"):
            self._data["batches"].append({
                "id": DEFAULT_BATCH,
                "name": DEFAULT_BATCH,
                "created_by": username,
                "created_at": _now(),
                "exported": False,
            })
            self._data["current_batch"] = DEFAULT_BATCH
            self.save()

    # ── CRUD ──────────────────────────────────────────
    def get_batch(self, batch_id: str) -> dict | None:
        for b in self._data.get("batches", []):
            if b["id"] == batch_id:
                return b
        return None

    def list_batches(self) -> list[dict]:
        return self._data.get("batches", [])

    def add_batch(self, name: str, username: str) -> dict:
        batch_id = name  # id = name for simplicity
        b = {
            "id": batch_id,
            "name": name,
            "created_by": username,
            "created_at": _now(),
            "exported": False,
        }
        self._data.setdefault("batches", []).append(b)
        self._data["current_batch"] = batch_id
        self.save()
        get_logger().info(f"Batch created: {batch_id} by {username}")
        return b

    def mark_exported(self, batch_id: str):
        b = self.get_batch(batch_id)
        if b:
            b["exported"] = True
            self.save()
            get_logger().info(f"Batch marked exported: {batch_id}")

    def delete_batch(self, batch_id: str, entries_dir: str = "labels/.entries"):
        """删除批次及其所有元数据文件。"""
        self.load()
        self._data["batches"] = [b for b in self._data.get("batches", []) if b["id"] != batch_id]
        if self._data.get("current_batch") == batch_id:
            remaining = self._data.get("batches", [])
            self._data["current_batch"] = remaining[0]["id"] if remaining else DEFAULT_BATCH
        self.save()
        # 删除该批次的元数据文件
        from core.entry_manager import EntryManager
        em = EntryManager(entries_dir)
        deleted = 0
        for e in em.read_all_entries():
            if e.get("batch_id") == batch_id:
                fn = e.get("_entry_file", "")
                em.delete_entry_file(fn)
                deleted += 1
        get_logger().info(f"Batch deleted: {batch_id} ({deleted} entries removed)")
