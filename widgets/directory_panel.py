from PySide6.QtWidgets import QTreeView, QFileSystemModel, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Signal, Qt, QDir


class DirectoryPanel(QWidget):
    directory_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("文件夹")  # 文件夹
        title.setStyleSheet("""
            QLabel {
                background-color: #11111b;
                color: #cdd6f4;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 12px;
                border-bottom: 1px solid #313244;
            }
        """)
        layout.addWidget(title)

        self._model = QFileSystemModel()
        self._model.setRootPath(QDir.rootPath())
        self._model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(True)
        self._tree.setColumnHidden(1, True)
        self._tree.setColumnHidden(2, True)
        self._tree.setColumnHidden(3, True)
        self._tree.clicked.connect(self._on_clicked)
        self._tree.setStyleSheet("""
            QTreeView {
                background-color: #181825;
                color: #cdd6f4;
                font-size: 13px;
                border: none;
            }
            QTreeView::item {
                padding: 4px 8px;
            }
        """)

        layout.addWidget(self._tree)

    def _on_clicked(self, index):
        path = self._model.filePath(index)
        self.directory_selected.emit(path)
