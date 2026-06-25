"""进度管理器 —— 按用户拆分进度文件，合并读取。"""
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

    def save_my(self, current_index: int, file_list: list[str], classified: dict = None):
        if not self._dir or not self._username:
            return
        self._data["current_index"] = current_index
        self._data["total_images"] = len(file_list)
        if classified is not None:
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
        """合并所有用户的已分类信息 → {basename: {label, by, at}}"""
        merged = {}
        for pd in self.load_all_users(directory):
            user = pd.get("_user", "unknown")
            for bn, info in (pd.get("classified") or {}).items():
                merged[bn] = {
                    "label": info.get("label", info) if isinstance(info, dict) else info,
                    "by": info.get("by", user) if isinstance(info, dict) else user,
                    "at": info.get("at", "") if isinstance(info, dict) else "",
                }
        return merged

    # ── 清理 ──────────────────────────────────────────
    def clear(self):
        self._data = {}
        self._dir = ""
