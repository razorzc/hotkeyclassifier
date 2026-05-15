import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from core.settings import AppSettings


class ImageManager(QObject):
    image_list_changed = Signal()
    current_index_changed = Signal(int)
    image_loaded = Signal(str, QPixmap)
    load_error = Signal(str, str)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._file_list: list[str] = []
        self._current_index: int = -1
        self._current_dir: str = ""
        self._pixmap_cache: dict[int, QPixmap] = {}

    def load_directory(self, path: str) -> int:
        if not os.path.isdir(path):
            self.load_error.emit(path, "Directory not found")
            return 0
        self._current_dir = path
        self._file_list.clear()
        self._pixmap_cache.clear()
        formats = self._settings.supported_formats
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            if os.path.isfile(full):
                ext = os.path.splitext(entry)[1].lower()
                if ext in formats:
                    self._file_list.append(full)
        self._current_index = 0 if self._file_list else -1
        self.image_list_changed.emit()
        if self._file_list:
            self._load_and_emit(0)
        return len(self._file_list)

    def current_path(self) -> Optional[str]:
        if 0 <= self._current_index < len(self._file_list):
            return self._file_list[self._current_index]
        return None

    def current_index(self) -> int:
        return self._current_index

    def total_count(self) -> int:
        return len(self._file_list)

    def get_image_list(self) -> list[str]:
        return self._file_list.copy()

    def go_to(self, index: int):
        if not self._file_list:
            return
        index = max(0, min(index, len(self._file_list) - 1))
        if index != self._current_index:
            self._current_index = index
            self.current_index_changed.emit(index)
        self._load_and_emit(index)

    def go_next(self):
        if self._current_index < len(self._file_list) - 1:
            self.go_to(self._current_index + 1)

    def go_prev(self):
        if self._current_index > 0:
            self.go_to(self._current_index - 1)

    def go_home(self):
        self.go_to(0)

    def go_end(self):
        self.go_to(len(self._file_list) - 1)

    def remove_current(self):
        if 0 <= self._current_index < len(self._file_list):
            removed = self._file_list.pop(self._current_index)
            self._pixmap_cache.pop(self._current_index, None)
            new_cache = {}
            for idx, px in self._pixmap_cache.items():
                if idx > self._current_index:
                    new_cache[idx - 1] = px
                elif idx < self._current_index:
                    new_cache[idx] = px
            self._pixmap_cache = new_cache
            if self._current_index >= len(self._file_list):
                self._current_index = max(0, len(self._file_list) - 1)
            self.image_list_changed.emit()
            return removed
        return ""

    def load_pixmap(self, path: str) -> QPixmap:
        if not os.path.exists(path):
            return QPixmap()
        max_dim = 4096
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return QPixmap()
        if pixmap.width() > max_dim or pixmap.height() > max_dim:
            pixmap = pixmap.scaled(
                max_dim, max_dim, aspectRatioMode=1, transformMode=1
            )  # Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        return pixmap

    def thumb_at(self, index: int) -> Optional[QPixmap]:
        return self._pixmap_cache.get(index)

    def cache_pixmap(self, index: int, pixmap: QPixmap):
        self._pixmap_cache[index] = pixmap

    def _load_and_emit(self, index: int):
        if 0 <= index < len(self._file_list):
            path = self._file_list[index]
            cached = self._pixmap_cache.get(index)
            if cached and not cached.isNull():
                self.image_loaded.emit(path, cached)
                return
            pixmap = self.load_pixmap(path)
            if pixmap.isNull():
                self.load_error.emit(path, "Failed to load image")
                return
            self._pixmap_cache[index] = pixmap
            self.image_loaded.emit(path, pixmap)

    @property
    def current_dir(self) -> str:
        return self._current_dir
