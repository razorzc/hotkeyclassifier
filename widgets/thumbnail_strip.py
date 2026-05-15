from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QPixmap, QFont, QColor


THUMB_SIZE = QSize(200, 150)


class ThumbnailItem(QWidget):
    clicked = Signal(int)

    def __init__(self, index: int, pixmap: QPixmap, filename: str, is_current: bool = False):
        super().__init__()
        self._index = index
        self.setFixedSize(THUMB_SIZE.width() + 12, THUMB_SIZE.height() + 36)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        thumb = pixmap.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        img_label = QLabel()
        img_label.setPixmap(thumb)
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(THUMB_SIZE)

        if is_current:
            img_label.setStyleSheet("border: 2px solid #89b4fa; border-radius: 4px;")
        else:
            img_label.setStyleSheet("border: 2px solid transparent; border-radius: 4px;")

        layout.addWidget(img_label, alignment=Qt.AlignCenter)

        text_label = QLabel(filename)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #cdd6f4; font-size: 10px;")
        text_label.setFont(QFont("Microsoft YaHei", 9))
        text_label.setWordWrap(True)
        text_label.setMaximumWidth(THUMB_SIZE.width())
        layout.addWidget(text_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self._index)

    def set_current(self, is_current: bool):
        img_label = self.findChild(QLabel)
        if img_label:
            if is_current:
                img_label.setStyleSheet("border: 2px solid #89b4fa; border-radius: 4px;")
            else:
                img_label.setStyleSheet("border: 2px solid transparent; border-radius: 4px;")


class ThumbnailStrip(QScrollArea):
    thumbnail_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWidgetResizable(True)
        self.setFixedWidth(THUMB_SIZE.width() + 26)
        self.setStyleSheet("""
            QScrollArea {
                background-color: #181825;
                border: none;
            }
        """)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignTop)
        self._items: list[ThumbnailItem] = []
        self._current_idx = -1
        self.setWidget(self._container)

    def set_images(self, current_idx: int, file_list: list[str], pixmap_cache: dict[int, QPixmap]):
        # Remove old items
        for item in self._items:
            item.setParent(None)
            self._layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()
        self._current_idx = current_idx

        total = len(file_list)
        half = 10
        start = max(0, current_idx - half)
        end = min(total, current_idx + half + 1)

        # Header
        header = QLabel(f"图片列表  {current_idx + 1}/{total}")
        header.setStyleSheet("color: #a6adc8; font-size: 10px; padding: 2px 4px;")
        header.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(header)

        for i in range(start, end):
            filename = file_list[i].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            px = pixmap_cache.get(i)
            if px and not px.isNull():
                thumb = px
            else:
                thumb = QPixmap(THUMB_SIZE)
                thumb.fill(QColor("#313244"))
            item = ThumbnailItem(i, thumb, filename, i == current_idx)
            item.clicked.connect(self._on_clicked)
            self._items.append(item)
            self._layout.addWidget(item)

        # Spacer at bottom
        self._layout.addStretch()

    def update_current(self, current_idx: int):
        for item in self._items:
            item.set_current(item._index == current_idx)

    def _on_clicked(self, index: int):
        self.thumbnail_clicked.emit(index)
