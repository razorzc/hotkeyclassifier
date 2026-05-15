from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable
from PySide6.QtGui import QPixmap

from core.settings import AppSettings


class PreloadSignaller(QObject):
    ready = Signal(int, QPixmap)
    error = Signal(int, str)


class PreloadTask(QRunnable):
    def __init__(self, path: str, index: int, max_dim: int):
        super().__init__()
        self._path = path
        self._index = index
        self._max_dim = max_dim
        self.signaller = PreloadSignaller()

    def run(self):
        try:
            pixmap = QPixmap(self._path)
            if pixmap.isNull():
                self.signaller.error.emit(self._index, "Failed to load")
                return
            if pixmap.width() > self._max_dim or pixmap.height() > self._max_dim:
                pixmap = pixmap.scaled(
                    self._max_dim, self._max_dim,
                    aspectRatioMode=1,
                    transformMode=1,
                )
            self.signaller.ready.emit(self._index, pixmap)
        except Exception as e:
            self.signaller.error.emit(self._index, str(e))


class PreloadManager(QObject):
    preload_ready = Signal(int, QPixmap)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(4)
        self._cache: dict[int, QPixmap] = {}
        self._max_dim = 4096
        self._preload_count = settings.preload_count

    def set_current_index(self, index: int, file_list: list[str]):
        start = max(0, index - self._preload_count)
        end = min(len(file_list), index + self._preload_count + 1)
        for i in range(start, end):
            if i == index or i in self._cache:
                continue
            task = PreloadTask(file_list[i], i, self._max_dim)
            task.signaller.ready.connect(self._on_ready)
            task.signaller.error.connect(self._on_error)
            self._pool.start(task)

    def get_cached(self, index: int) -> QPixmap | None:
        return self._cache.get(index)

    def clear(self):
        self._cache.clear()

    def _on_ready(self, index: int, pixmap: QPixmap):
        self._cache[index] = pixmap
        if len(self._cache) > 20:
            current = min(self._cache.keys()) if self._cache else 0
            to_remove = []
            for k in list(self._cache.keys()):
                if abs(k - current) > 15:
                    to_remove.append(k)
                    if len(to_remove) >= 5:
                        break
            for k in to_remove:
                del self._cache[k]
        self.preload_ready.emit(index, pixmap)

    def _on_error(self, index: int, msg: str):
        pass
