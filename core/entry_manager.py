"""元数据管理器 —— 按用户单文件 .jsonl 追加写入。"""
import os
import json
import uuid
from datetime import datetime, timezone

from utils.logger import get_logger

ENTRIES_DIR = "labels"
ENTRIES_EXT = ".jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_for(user: str) -> str:
    return os.path.join(ENTRIES_DIR, f".entries.{user}{ENTRIES_EXT}")


class EntryManager:
    def __init__(self):
        os.makedirs(ENTRIES_DIR, exist_ok=True)

    # ── 写入 ──────────────────────────────────────────
    def write_entry(
        self,
        image_path: str,
        label: str,
        classified_by: str,
        batch_id: str = "",
        status: str = "pending",
    ) -> str:
        """追加一条记录到该用户的 .jsonl，返回记录 ID。"""
        entry_id = uuid.uuid4().hex[:12]
        entry = {
            "id": entry_id,
            "image_path": image_path,
            "label": label,
            "classified_by": classified_by,
            "batch_id": batch_id,
            "modified_at": _now(),
            "new_filename": "",
            "status": status,
            "_deleted": False,
        }
        path = _file_for(classified_by)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        get_logger().info(f"Entry appended: {entry_id} -> {label} by {classified_by}")
        return entry_id

    # ── 读取 ──────────────────────────────────────────
    def read_all_entries(self) -> list[dict]:
        """读取所有用户的 .jsonl，排除软删除，返回 entry 列表。"""
        entries = []
        if not os.path.isdir(ENTRIES_DIR):
            return entries
        for fn in sorted(os.listdir(ENTRIES_DIR)):
            if not fn.endswith(ENTRIES_EXT):
                continue
            path = os.path.join(ENTRIES_DIR, fn)
            for line in self._read_lines(path):
                if line.get("_deleted"):
                    continue
                entries.append(line)
        entries.sort(key=lambda e: e.get("modified_at", ""))
        return entries

    def read_all_entries_for_user(self, username: str) -> list[dict]:
        """读取单个用户的所有记录（含软删除）。"""
        path = _file_for(username)
        return self._read_lines(path)

    def _read_lines(self, path: str) -> list[dict]:
        lines = []
        if not os.path.isfile(path):
            return lines
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entry.setdefault("id", "")
                        entry.setdefault("modified_at", "")
                        entry.setdefault("classified_by", "")
                        entry.setdefault("batch_id", "")
                        entry.setdefault("new_filename", "")
                        entry.setdefault("status", "pending")
                        entry.setdefault("_deleted", False)
                        lines.append(entry)
                    except json.JSONDecodeError:
                        pass
        except (IOError, UnicodeDecodeError):
            pass
        return lines

    def get_latest_for_path(self, image_path: str) -> dict | None:
        latest = None
        for entry in self.read_all_entries():
            if entry.get("image_path") == image_path:
                if latest is None or entry["modified_at"] > latest["modified_at"]:
                    latest = entry
        return latest

    def get_all_for_path(self, image_path: str) -> list[dict]:
        return [e for e in self.read_all_entries() if e.get("image_path") == image_path]

    # ── 筛选用 ────────────────────────────────────────
    def get_classified_paths(self) -> set[str]:
        return {e["image_path"] for e in self.read_all_entries()}

    def get_classified_basename_map(self) -> dict[str, dict]:
        result = {}
        for e in self.read_all_entries():
            bn = os.path.basename(e["image_path"])
            if bn not in result or e["modified_at"] > result[bn]["modified_at"]:
                result[bn] = {
                    "label": e.get("label", ""),
                    "by": e.get("classified_by", ""),
                    "at": e.get("modified_at", ""),
                }
        return result

    # ── 软删除（撤销用）─────────────────────────────
    def soft_delete(self, entry_id: str, username: str):
        """将指定记录标记为软删除。"""
        self._update_line(username, entry_id, {"_deleted": True})
        get_logger().info(f"Entry soft-deleted: {entry_id}")

    # ── 导出标记 ─────────────────────────────────────
    def set_synced(self, entry_id: str, username: str, new_filename: str):
        """将记录标记为已导出。"""
        self._update_line(username, entry_id, {
            "status": "synced",
            "new_filename": new_filename,
        })
        get_logger().info(f"Entry synced: {entry_id} -> {new_filename}")

    def _update_line(self, username: str, entry_id: str, updates: dict):
        """修改指定 ID 行的字段。逐行读取→修改→全文写回。"""
        path = _file_for(username)
        if not os.path.isfile(path):
            return
        new_lines = []
        updated = False
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    new_lines.append("")
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                if e.get("id") == entry_id:
                    e.update(updates)
                    updated = True
                new_lines.append(json.dumps(e, ensure_ascii=False))
        if updated:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + ("\n" if new_lines else ""))

    # ── 删除元数据文件（兼容旧版独立文件）────────────
    def delete_entry_file(self, filename: str):
        """兼容旧版单文件删除。新版通过 soft_delete 替代。"""
        if "/" in filename or "\\" in filename:
            # 旧版完整路径
            if os.path.isfile(filename):
                os.remove(filename)
        else:
            # 可能只是 entry_id，尝试通过 scan 查找并软删除
            # 遍历所有用户文件
            pass

    # ── CSV 汇总 ─────────────────────────────────────
    def build_csv(self, csv_path: str):
        import csv
        entries = self.read_all_entries()
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        tmp = csv_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f,
                fieldnames=["image_path", "new_filename", "label", "classified_by", "modified_at"])
            writer.writeheader()
            for e in entries:
                writer.writerow({
                    "image_path": e.get("image_path", ""),
                    "new_filename": e.get("new_filename", ""),
                    "label": e.get("label", ""),
                    "classified_by": e.get("classified_by", ""),
                    "modified_at": e.get("modified_at", ""),
                })
        os.replace(tmp, csv_path)
        get_logger().info(f"CSV built: {csv_path} ({len(entries)} rows)")
