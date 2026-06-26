import os
from typing import Optional

from PySide6.QtCore import QObject, Signal, Qt, QThreadPool, QRunnable
from PySide6.QtGui import QPixmap

from core.settings import AppSettings


class _LoadSignaller(QObject):
    ready = Signal(int, QPixmap)
    error = Signal(int, str)


class _LoadTask(QRunnable):
    def __init__(self, path: str, index: int, max_dim: int):
        super().__init__()
        self._path = path
        self._index = index
        self._max_dim = max_dim
        self.signaller = _LoadSignaller()

    def run(self):
        if not os.path.exists(self._path):
            self.signaller.error.emit(self._index, "File not found")
            return
        pixmap = QPixmap(self._path)
        if pixmap.isNull():
            self.signaller.error.emit(self._index, "Failed to load")
            return
        if pixmap.width() > self._max_dim or pixmap.height() > self._max_dim:
            pixmap = pixmap.scaled(
                self._max_dim, self._max_dim,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        self.signaller.ready.emit(self._index, pixmap)


class ImageManager(QObject):
    image_list_changed = Signal()
    current_index_changed = Signal(int)
    image_loaded = Signal(str, QPixmap)
    load_started = Signal(str)        # path — 开始加载时触发
    load_error = Signal(str, str)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._file_list: list[str] = []
        self._all_files: list[str] = []
        self._current_index: int = -1
        self._current_dir: str = ""
        self._pixmap_cache: dict[int, QPixmap] = {}
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(2)
        self._max_dim = 4096
        self._pending_index: int = -1

    def load_directory(self, path: str) -> int:
        if not os.path.isdir(path):
            self.load_error.emit(path, "Directory not found")
            return 0
        self._current_dir = path
        self._file_list.clear()
        self._all_files.clear()
        self._pixmap_cache.clear()
        self._pool.waitForDone()
        formats = self._settings.supported_formats
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            if os.path.isfile(full):
                ext = os.path.splitext(entry)[1].lower()
                if ext in formats:
                    self._file_list.append(full)
        self._all_files = self._file_list.copy()
        self._current_index = 0 if self._file_list else -1
        self.image_list_changed.emit()
        if self._file_list:
            self._load_and_emit(0)
        return len(self._file_list)

    def apply_filter(self, excluded_paths: set):
        self._all_files = self._file_list.copy() if not self._all_files else self._all_files
        self._file_list = [f for f in self._all_files if f not in excluded_paths]
        self._current_index = 0 if self._file_list else -1
        self._pixmap_cache.clear()
        self.image_list_changed.emit()
        if self._file_list:
            self._load_and_emit(0)

    def clear_filter(self):
        if self._all_files:
            self._file_list = self._all_files.copy()
            self._all_files = []
        self._current_index = 0 if self._file_list else -1
        self._pixmap_cache.clear()
        self.image_list_changed.emit()
        if self._file_list:
            self._load_and_emit(0)

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
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return QPixmap()
        if pixmap.width() > self._max_dim or pixmap.height() > self._max_dim:
            pixmap = pixmap.scaled(
                self._max_dim, self._max_dim,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        return pixmap

    def thumb_at(self, index: int) -> Optional[QPixmap]:
        return self._pixmap_cache.get(index)

    def cache_pixmap(self, index: int, pixmap: QPixmap):
        self._pixmap_cache[index] = pixmap

    def _load_and_emit(self, index: int):
        if not (0 <= index < len(self._file_list)):
            return
        path = self._file_list[index]

        # 缓存命中 → 直接显示
        cached = self._pixmap_cache.get(index)
        if cached and not cached.isNull():
            self.image_loaded.emit(path, cached)
            return

        # 缓存未命中 → 通知 UI 开始加载，异步后台加载
        self._pending_index = index
        self.load_started.emit(path)
        task = _LoadTask(path, index, self._max_dim)
        task.signaller.ready.connect(self._on_load_ready)
        task.signaller.error.connect(self._on_load_error)
        self._pool.start(task)

    def _on_load_ready(self, index: int, pixmap: QPixmap):
        if index == self._pending_index:
            path = self._file_list[index] if index < len(self._file_list) else ""
            self._pixmap_cache[index] = pixmap
            self.image_loaded.emit(path, pixmap)

    def _on_load_error(self, index: int, msg: str):
        if index < len(self._file_list):
            self.load_error.emit(self._file_list[index], msg)

    @property
    def current_dir(self) -> str:
        return self._current_dir
