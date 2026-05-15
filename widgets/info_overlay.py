from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class InfoOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("""
            QLabel {
                color: #cdd6f4;
                background-color: rgba(24, 24, 37, 200);
                border-radius: 6px;
                padding: 4px 10px;
                font-family: "Microsoft YaHei", "Consolas", "Menlo", monospace;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(1)

        self._filename_label = QLabel()
        self._filename_label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._resolution_label = QLabel()
        self._zoom_label = QLabel()
        self._index_label = QLabel()

        for lbl in [self._filename_label, self._resolution_label, self._zoom_label, self._index_label]:
            lbl.setFont(QFont("Microsoft YaHei", 10))
            layout.addWidget(lbl)

        self.adjustSize()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def update_info(self, filename: str, resolution: str, zoom_percent: float,
                    index: int, total: int, directory: str):
        self._filename_label.setText(filename)
        self._resolution_label.setText(f"原始分辨率: {resolution}")  # 原始分辨率
        self._zoom_label.setText(f"缩放: {zoom_percent:.0f}%")                    # 缩放
        self._index_label.setText(f"{index + 1} / {total}")
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        self.move(8, 8)
        self.raise_()
