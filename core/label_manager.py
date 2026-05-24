import os
import csv
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QObject


class LabelManager(QObject):
    def __init__(self, csv_path: str, parent=None):
        super().__init__(parent)
        self._csv_path = csv_path
        self._rows: list[dict] = []
        self._seen: set[str] = set()
        self._load()

    def _load(self):
        if not os.path.exists(self._csv_path):
            return
        try:
            with open(self._csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row.setdefault("timestamp", "")
                    row.setdefault("label", "")
                    row.setdefault("new_filename", "")
                    self._rows.append(row)
                    self._seen.add(row.get("image_path", ""))
        except Exception:
            return

    def append(self, image_path: str, label: str, new_filename: str = "",
               timestamp: Optional[str] = None):
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        self._rows.append({
            "image_path": image_path,
            "new_filename": new_filename,
            "label": label,
            "timestamp": timestamp,
        })
        self._seen.add(image_path)
        self.flush()

    def has_label(self, image_path: str) -> bool:
        return image_path in self._seen

    def get_label_for(self, image_path: str) -> dict | None:
        for row in self._rows:
            if row.get("image_path") == image_path:
                return row
        return None

    def remove_entry(self, image_path: str):
        self._rows = [r for r in self._rows if r.get("image_path") != image_path]
        self._seen.discard(image_path)
        self.flush()

    def flush(self):
        os.makedirs(os.path.dirname(self._csv_path), exist_ok=True)
        tmp_path = self._csv_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["image_path", "new_filename", "label", "timestamp"])
            writer.writeheader()
            writer.writerows(self._rows)
        os.replace(tmp_path, self._csv_path)

    def get_labels(self) -> list[dict]:
        return self._rows.copy()
