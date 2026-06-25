from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class UndoEntry:
    src_path: str          # 分类时 = 元数据文件路径；移动时 = 目标路径
    dst_path: str          # 裁剪文件路径/entry 文件名（可为空）
    original_src: str      # 原始图片路径
    label: str
    action_type: str       # "classify" | "move" | "crop"
    original_index: int
    classified_by: str = ""  # 标注人
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

    def remove_at(self, index: int) -> Optional[UndoEntry]:
        """移除并返回指定位置的条目，用于撤销非最后一次操作。"""
        if 0 <= index < len(self._stack):
            entry = self._stack.pop(index)
            self.undo_stack_changed.emit(len(self._stack) > 0)
            return entry
        return None

    def list_by_user(self, username: str) -> list[tuple[int, UndoEntry]]:
        """返回当前用户的所有可撤销条目 (stack_index, entry)。index 大的为最近操作。"""
        result = []
        for i, entry in enumerate(self._stack):
            if entry.classified_by == username and entry.action_type == "classify":
                result.append((i, entry))
        result.reverse()  # 最近的在前面
        return result

    def can_undo(self) -> bool:
        return len(self._stack) > 0

    def clear(self):
        self._stack.clear()
        self.undo_stack_changed.emit(False)
