"""增量元数据管理器 —— 每次分类写入独立 .json 文件，避免并发冲突。"""
import os
import json
from datetime import datetime, timezone, timedelta

from utils.logger import get_logger


def _tz_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tz_now_compact() -> str:
    """返回紧凑格式的时间戳，用于文件名。"""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _micro() -> str:
    """三位数微秒后缀避免同名。"""
    return str(int(datetime.now(timezone.utc).microsecond / 1000)).zfill(3)


class EntryManager:
    """管理 labels/.entries/ 下的增量 json 文件。"""

    def __init__(self, entries_dir: str = "labels/.entries"):
        self._entries_dir = entries_dir

    # ── 写入 ──────────────────────────────────────────
    def write_entry(
        self,
        image_path: str,
        label: str,
        classified_by: str,
        status: str = "pending",
    ) -> str:
        """写入一条元数据增量文件，返回文件路径。"""
        os.makedirs(self._entries_dir, exist_ok=True)
        entry = {
            "image_path": image_path,
            "label": label,
            "classified_by": classified_by,
            "modified_at": _tz_now(),
            "new_filename": "",
            "status": status,
        }
        # 文件名: {用户}_{时间}_{微秒}.json —— 无冲突
        filename = f"{classified_by}_{_tz_now_compact()}_{_micro()}.json"
        path = os.path.join(self._entries_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        get_logger().info(f"Entry written: {filename} -> {label} by {classified_by}")
        return path

    # ── 读取 ──────────────────────────────────────────
    def read_all_entries(self) -> list[dict]:
        """读取所有增量文件，返回 entry 列表（按 modified_at 排序）。"""
        entries = []
        if not os.path.isdir(self._entries_dir):
            return entries
        for fn in sorted(os.listdir(self._entries_dir)):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(self._entries_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                entry["_entry_file"] = fn
                entry.setdefault("modified_at", "")
                entry.setdefault("classified_by", "")
                entry.setdefault("new_filename", "")
                entry.setdefault("status", "pending")
                entries.append(entry)
            except (json.JSONDecodeError, IOError):
                pass
        entries.sort(key=lambda e: e.get("modified_at", ""))
        return entries

    def get_latest_for_path(self, image_path: str) -> dict | None:
        """获取某张图片的最新（最后）一条元数据。"""
        latest = None
        for entry in self.read_all_entries():
            if entry.get("image_path") == image_path:
                if latest is None or entry["modified_at"] > latest["modified_at"]:
                    latest = entry
        return latest

    def get_all_for_path(self, image_path: str) -> list[dict]:
        """获取某张图片的所有元数据（按时间排序）。"""
        return [e for e in self.read_all_entries() if e.get("image_path") == image_path]

    # ── 已分类集合（供筛选用）──────────────────────
    def get_classified_paths(self) -> set[str]:
        """返回所有已分类图片路径的集合。"""
        return {e["image_path"] for e in self.read_all_entries()}

    def get_classified_basename_map(self) -> dict[str, dict]:
        """返回 {basename: {label, by, at}} 字典（取最新记录）。"""
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

    # ── 删除（撤销用）───────────────────────────────
    def delete_entry_file(self, filename: str):
        """删除单个增量文件。"""
        path = os.path.join(self._entries_dir, filename)
        if os.path.isfile(path):
            os.remove(path)
            get_logger().info(f"Entry deleted: {filename}")

    # ── 导出/汇总 ───────────────────────────────────
    def set_synced(self, filename: str, new_filename: str):
        """将某条记录标记为已导出。"""
        path = os.path.join(self._entries_dir, filename)
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        entry["status"] = "synced"
        entry["new_filename"] = new_filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

    def build_csv(self, csv_path: str):
        """从所有增量文件重建汇总 CSV。"""
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
