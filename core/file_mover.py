import os
import shutil
from typing import Optional

from PySide6.QtCore import QObject, Signal

from utils.logger import get_logger


class FileMover(QObject):
    file_moved = Signal(str, str)
    move_error = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[tuple[str, str]] = []

    def move_to_class(self, src: str, class_folder: str, base_dir: str) -> Optional[str]:
        logger = get_logger()
        if not os.path.isfile(src):
            self.move_error.emit(src, "Source file not found")
            return None
        dst_dir = os.path.join(base_dir, class_folder)
        os.makedirs(dst_dir, exist_ok=True)
        filename = os.path.basename(src)
        dst = os.path.join(dst_dir, filename)
        dst = self._resolve_conflict(dst)
        try:
            shutil.move(src, dst)
            self._history.append((src, dst))
            logger.info(f"Moved: {src} -> {dst}")
            self.file_moved.emit(src, dst)
            return dst
        except OSError as e:
            logger.error(f"Move failed: {src} -> {dst}: {e}")
            self.move_error.emit(src, str(e))
            return None

    def undo_last(self) -> Optional[tuple[str, str]]:
        logger = get_logger()
        if not self._history:
            return None
        src, dst = self._history.pop()
        try:
            shutil.move(dst, src)
            logger.info(f"Undo move: {dst} -> {src}")
            self.file_moved.emit(dst, src)
            return (dst, src)
        except OSError as e:
            logger.error(f"Undo move failed: {dst} -> {src}: {e}")
            self.move_error.emit(dst, str(e))
            self._history.append((src, dst))
            return None

    def can_undo(self) -> bool:
        return len(self._history) > 0

    def _resolve_conflict(self, dst: str) -> str:
        if not os.path.exists(dst):
            return dst
        base, ext = os.path.splitext(dst)
        counter = 1
        while True:
            candidate = f"{base}_{counter:03d}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
