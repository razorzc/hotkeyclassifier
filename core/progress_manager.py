import json
import os

from utils.logger import get_logger

PROGRESS_FILENAME = ".sort_progress.json"


class ProgressManager:
    """Per-directory progress: current index, classified images map."""

    def __init__(self):
        self._dir: str = ""
        self._data: dict = {}

    def load(self, directory: str) -> dict:
        self._dir = directory
        path = os.path.join(directory, PROGRESS_FILENAME)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                get_logger().info(f"Progress loaded: {directory} -> index {self._data.get('current_index', 0)}")
                return self._data
            except (json.JSONDecodeError, IOError):
                pass
        self._data = {"current_index": 0, "classified": {}, "total_images": 0}
        return self._data

    def save(self, current_index: int, file_list: list[str], classified_map: dict = None):
        if not self._dir:
            return
        if classified_map is not None:
            self._data["classified"] = classified_map
        self._data["current_index"] = current_index
        self._data["total_images"] = len(file_list)
        path = os.path.join(self._dir, PROGRESS_FILENAME)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def mark_classified(self, image_path: str, label: str):
        filename = os.path.basename(image_path)
        self._data.setdefault("classified", {})[filename] = label

    def unmark_classified(self, image_path: str):
        filename = os.path.basename(image_path)
        self._data.get("classified", {}).pop(filename, None)

    def get_classified(self) -> dict:
        return self._data.get("classified", {})

    def get_saved_index(self) -> int:
        return self._data.get("current_index", 0)

    def clear(self):
        if self._dir:
            path = os.path.join(self._dir, PROGRESS_FILENAME)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._data = {}
        self._dir = ""
