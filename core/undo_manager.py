from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class UndoEntry:
    src_path: str       # 分类时 = 复制到目标目录的文件路径；移动时 = 目标路径
    dst_path: str       # 裁剪文件路径（可为空）
    original_src: str   # 原始图片路径（用于 CSV 删除和还原）
    label: str
    action_type: str    # "classify" | "move" | "crop"
    original_index: int
    timestamp: str = ""


class UndoManager(QObject):
    undo_stack_changed = Signal(bool)

    def __init__(self, max_depth: int = 50, parent=None):
        super().__init__(parent)
        self._max_depth = max_depth
        self._stack: list[UndoEntry] = []

    def push(self, entry: UndoEntry):
        self._stack.append(entry)
        if len(self._stack) > self._max_depth:
            self._stack.pop(0)
        self.undo_stack_changed.emit(True)

    def pop(self) -> Optional[UndoEntry]:
        if not self._stack:
            return None
        entry = self._stack.pop()
        self.undo_stack_changed.emit(len(self._stack) > 0)
        return entry

    def can_undo(self) -> bool:
        return len(self._stack) > 0

    def clear(self):
        self._stack.clear()
        self.undo_stack_changed.emit(False)
