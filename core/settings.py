import json
import os
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class CropSize:
    name: str
    key: str
    width: int
    height: int


@dataclass
class ClassMapping:
    key: str
    label: str
    folder: str
    color: str


DEFAULT_CONFIG = {
    "general": {
        "supported_formats": [".png", ".jpg", ".jpeg", ".bmp", ".webp"],
        "max_undo_depth": 50,
        "preload_count": 5,
        "blur_threshold": 100.0,
        "blur_enabled": False,
        "auto_next": True,
        "skip_classified": False,
    },
    "display": {
        "zoom_step": 0.15,
        "max_zoom": 10.0,
        "min_zoom": 0.05,
        "crop_overlay_color": "#00FF88",
        "crop_overlay_width": 2,
        "info_overlay_opacity": 0.85,
        "background_color": "#1e1e2e",
        "thumbnail_size": 120,
    },
    "crop_sizes": [
        {"name": "224x224", "key": "1", "width": 224, "height": 224},
        {"name": "384x384", "key": "2", "width": 384, "height": 384},
        {"name": "640x640", "key": "3", "width": 640, "height": 640},
    ],
    "classifications": [
        {"key": "Q", "label": "Line_Broken_strands", "folder": "输电线/断股", "color": "#FF6B6B"},
        {"key": "W", "label": "Line_Damage", "folder": "输电线/损伤", "color": "#FF8C42"},
        {"key": "E", "label": "Line_Foreign_object", "folder": "输电线/异物", "color": "#FFD93D"},
        {"key": "R", "label": "Line_Normal", "folder": "输电线/正常", "color": "#6BCB77"},
        {"key": "A", "label": "Tower_Deformation", "folder": "塔杆/变形", "color": "#C084FC"},
        {"key": "S", "label": "Tower_Corrosion", "folder": "塔杆/锈蚀", "color": "#F472B6"},
        {"key": "D", "label": "Tower_Foreign_object", "folder": "塔杆/异物", "color": "#60A5FA"},
        {"key": "F", "label": "Tower_Normal", "folder": "塔杆/正常", "color": "#34D399"},
        {"key": "T", "label": "待定", "folder": "uncertain", "color": "#95A5A6"},
    ],
    "key_bindings": {
        "next": "Right",
        "prev": "Left",
        "first": "Home",
        "last": "End",
        "zoom_in": "Ctrl+Plus",
        "zoom_out": "Ctrl+Minus",
        "zoom_fit": "0",
        "zoom_100": "Ctrl+1",
        "undo": "Ctrl+Z",
        "crop_save": "Return",
        "crop_small": "1",
        "crop_medium": "2",
        "crop_large": "3",
        "fullscreen": "F11",
        "toggle_info": "I",
    },
    "paths": {
        "target_dir": "",
        "crop_output_dir": "crops",
        "label_csv_dir": "labels",
        "label_csv_name": "labels.csv",
        "thumbnail_cache": "cache/thumbnails",
        "log_dir": "logs",
        "log_file": "logs/app.log",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class AppSettings(QObject):
    config_changed = Signal()

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self._config_path = config_path
        self._data = {}
        self.reload()

    def reload(self):
        self._data = DEFAULT_CONFIG.copy()
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                self._data = _deep_merge(self._data, user_data)
            except (json.JSONDecodeError, IOError) as e:
                self._data = DEFAULT_CONFIG.copy()
        self.config_changed.emit()

    def save(self):
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key_path: str, default=None):
        keys = key_path.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key_path: str, value):
        keys = key_path.split(".")
        target = self._data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    @property
    def crop_sizes(self) -> list[CropSize]:
        sizes = self.get("crop_sizes", [])
        return [CropSize(**s) for s in sizes]

    @property
    def class_mappings(self) -> list[ClassMapping]:
        mappings = self.get("classifications", [])
        return [ClassMapping(**m) for m in mappings]

    @property
    def key_bindings(self) -> dict:
        return self.get("key_bindings", {})

    @property
    def preload_count(self) -> int:
        return self.get("general.preload_count", 5)

    @property
    def blur_threshold(self) -> float:
        return self.get("general.blur_threshold", 100.0)

    @property
    def supported_formats(self) -> list[str]:
        return self.get("general.supported_formats", [".png", ".jpg", ".jpeg", ".bmp", ".webp"])

    @property
    def auto_next(self) -> bool:
        return self.get("general.auto_next", True)

    @property
    def max_undo_depth(self) -> int:
        return self.get("general.max_undo_depth", 50)

    @property
    def target_dir(self) -> str:
        return self.get("paths.target_dir", "")

    @property
    def crop_output_dir(self) -> str:
        return self.get("paths.crop_output_dir", "crops")

    @property
    def label_csv_path(self) -> str:
        csv_dir = self.get("paths.label_csv_dir", "labels")
        csv_name = self.get("paths.label_csv_name", "labels.csv")
        return os.path.join(csv_dir, csv_name)

    @property
    def config_path(self) -> str:
        return self._config_path
