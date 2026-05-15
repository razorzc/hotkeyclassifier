from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor, QPainter, QFont

from core.settings import ClassMapping


class DragZone(QFrame):
    image_dropped = Signal(str)

    def __init__(self, mapping: ClassMapping, parent=None):
        super().__init__(parent)
        self._mapping = mapping

        self.setAcceptDrops(True)
        self.setMinimumHeight(64)
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet(f"""
            DragZone {{
                background-color: {mapping.color}22;
                border: 2px solid {mapping.color};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(1)

        key_label = QLabel(f"[{mapping.key}]")
        key_label.setStyleSheet(
            f"color: {mapping.color}; font-weight: bold; font-size: 15px;"
        )
        key_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(key_label)

        folder_label = QLabel(mapping.folder)
        folder_label.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: bold;")
        folder_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(folder_label)

        name_label = QLabel(mapping.label)
        name_label.setStyleSheet("color: #a6adc8; font-size: 9px;")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

    def set_active(self, active: bool):
        if active != getattr(self, '_active', False):
            self._active = active
            self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.set_active(True)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.set_active(False)

    def dropEvent(self, event: QDropEvent):
        self.set_active(False)
        event.acceptProposedAction()
        self.image_dropped.emit(self._mapping.label)

    def paintEvent(self, event):
        super().paintEvent(event)
        if getattr(self, '_active', False):
            painter = QPainter(self)
            color = QColor(self._mapping.color)
            color.setAlpha(80)
            painter.fillRect(self.rect(), color)
            painter.end()
