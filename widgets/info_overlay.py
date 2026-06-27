from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
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

        self._status_label = QLabel()
        self._status_label.setFont(QFont("Microsoft YaHei", 9))

        for lbl in [self._filename_label, self._resolution_label,
                     self._zoom_label, self._index_label, self._status_label]:
            lbl.setFont(QFont("Microsoft YaHei", 10))
            layout.addWidget(lbl)

        self._status_label.hide()
        self.adjustSize()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def update_info(self, filename: str, resolution: str, zoom_percent: float,
                    index: int, total: int, directory: str,
                    classified_label: str = "", classified_by: str = "",
                    classified_at: str = "", multi_count: int = 0,
                    batch_id: str = "", export_status: str = ""):
        self._filename_label.setText(filename)
        self._resolution_label.setText(f"原始分辨率: {resolution}")
        self._zoom_label.setText(f"缩放: {zoom_percent:.0f}%")
        self._index_label.setText(f"{index + 1} / {total}")

        if classified_label:
            parts = [classified_label]
            if classified_by:
                parts.append(classified_by)
            if classified_at:
                parts.append(classified_at)
            if batch_id:
                parts.append(f"批次:{batch_id}")
            if export_status == "synced":
                parts.append("✓已导出")
            elif export_status == "pending":
                parts.append("○待导出")
            text = " | ".join(parts)
            if multi_count > 1:
                text = f"[{multi_count}人标注] {text}"
            self._status_label.setText(text)
            self._status_label.setStyleSheet(
                "color: #a6e3a1; font-weight: bold; font-size: 10px;"
                "background-color: rgba(24, 37, 24, 220);"
            )
            self._status_label.show()
        else:
            self._status_label.hide()
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()

    def _reposition(self):
        if self.parent():
            self.move(8, 8)
        self.raise_()
