"""进度管理器 —— 按用户拆分进度文件，合并读取。

进度文件格式 (.sort_progress.{user}.json):

    {
        "current_index": 42,
        "current_batch": "默认",
        "total_images": 300,
        "classified": {
            "basename.jpg": {
                "label": "Line_Broken_strands",
                "by": "zjc",
                "at": "2026-06-26T08:26:12Z",
                "batch_id": "默认",
                "status": "pending"
            }
        }
    }

旧格式兼容: 缺少 current_batch / batch_id / status 时用默认值填充。
"""
import json
import os
import glob as glob_mod

from utils.logger import get_logger

PROGRESS_PREFIX = ".sort_progress"


class ProgressManager:
    """Per-directory, per-user progress files."""

    def __init__(self, username: str = ""):
        self._dir: str = ""
        self._username: str = username
        self._data: dict = {}

    def set_username(self, username: str):
        self._username = username

    def _progress_path(self, user: str) -> str:
        return os.path.join(self._dir, f"{PROGRESS_PREFIX}.{user}.json")

    # ── 我的进度读写 ──────────────────────────────────
    def load_my(self, directory: str) -> dict:
        self._dir = directory
        if not self._username:
            return {"current_index": 0}
        # 优先读取新格式 (.sort_progress.{user}.json)
        path = self._progress_path(self._username)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                return self._data
            except (json.JSONDecodeError, IOError):
                pass
        # 兼容旧格式 (.sort_progress.json)
        old_path = os.path.join(directory, f"{PROGRESS_PREFIX}.json")
        if os.path.exists(old_path):
            try:
                with open(old_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                return self._data
            except (json.JSONDecodeError, IOError):
                pass
        self._data = {"current_index": 0}
        return self._data

    def save_my(self, current_index: int, file_list: list[str],
                classified: dict = None, current_batch: str = ""):
        """保存当前用户的进度。

        Args:
            current_index: 当前图片索引
            file_list: 图片文件列表
            classified: {basename: {label, by, at, batch_id, status}, ...}
            current_batch: 当前目录使用的批次 ID
        """
        if not self._dir or not self._username:
            return
        self._data["current_index"] = current_index
        self._data["total_images"] = len(file_list)
        if current_batch:
            self._data["current_batch"] = current_batch
        if classified is not None:
            # 保证每条记录都有 batch_id 和 status（兼容旧调用方）
            for bn, info in classified.items():
                info.setdefault("batch_id", current_batch or "")
                info.setdefault("status", "pending")
            self._data["classified"] = classified
        path = self._progress_path(self._username)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    # ── 合并读取所有用户的已分类信息 ─────────────────
    def load_all_users(self, directory: str) -> list[dict]:
        """读取目录下所有用户的进度文件（含旧格式），返回合并后的进度列表。"""
        self._dir = directory
        results = []
        # 新格式: .sort_progress.{user}.json
        pattern = os.path.join(directory, f"{PROGRESS_PREFIX}.*.json")
        for path in sorted(glob_mod.glob(pattern)):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["_user"] = os.path.basename(path).replace(PROGRESS_PREFIX + ".", "").replace(".json", "")
                results.append(data)
            except (json.JSONDecodeError, IOError):
                pass
        # 兼容旧格式: .sort_progress.json
        old_path = os.path.join(directory, f"{PROGRESS_PREFIX}.json")
        if os.path.exists(old_path) and not any(
                old_path == os.path.join(directory, f"{PROGRESS_PREFIX}.{r.get('_user', '')}.json")
                for r in results):
            try:
                with open(old_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["_user"] = "legacy"
                results.append(data)
            except (json.JSONDecodeError, IOError):
                pass
        return results

    def get_merged_classified(self, directory: str) -> dict[str, dict]:
        """合并所有用户的已分类信息 → {basename: {label, by, at, batch_id, status}}"""
        merged = {}
        for pd in self.load_all_users(directory):
            user = pd.get("_user", "unknown")
            for bn, info in (pd.get("classified") or {}).items():
                if isinstance(info, dict):
                    merged[bn] = {
                        "label": info.get("label", ""),
                        "by": info.get("by", user),
                        "at": info.get("at", ""),
                        "batch_id": info.get("batch_id", ""),
                        "status": info.get("status", "pending"),
                    }
                else:
                    # 极旧的格式：classified 值直接是 label 字符串
                    merged[bn] = {
                        "label": str(info),
                        "by": user,
                        "at": "",
                        "batch_id": "",
                        "status": "pending",
                    }
        return merged

    def get_dir_batch(self, directory: str) -> str:
        """读取当前用户在该目录的进度文件中记录的 current_batch。"""
        data = self.load_my(directory)
        return data.get("current_batch", "")

    # ── 清理 ──────────────────────────────────────────
    def clear(self):
        self._data = {}
        self._dir = ""
