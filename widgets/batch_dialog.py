"""批次管理与导出选择对话框。"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QCheckBox, QDialogButtonBox,
    QMessageBox, QInputDialog, QWidget,
)
from PySide6.QtCore import Qt

from core.batch_manager import BatchManager
from core.entry_manager import EntryManager


class BatchManageDialog(QDialog):
    """批次管理：切换 / 新建 / 删除。"""

    def __init__(self, batch_mgr: BatchManager, entry_mgr: EntryManager,
                 username: str, parent=None):
        super().__init__(parent)
        self._batch_mgr = batch_mgr
        self._entry_mgr = entry_mgr
        self._username = username
        self._result: str = ""  # selected batch id

        self.setWindowTitle("批次管理")
        self.setMinimumSize(500, 350)
        self.resize(550, 400)
        self.setStyleSheet("QDialog{background-color:#1e1e2e;}")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(f"当前用户: {username}")
        lbl.setStyleSheet("font-size:13px;color:#cdd6f4;")
        layout.addWidget(lbl)

        self._lst = QListWidget()
        self._lst.setStyleSheet("""
            QListWidget{background:#181825;color:#cdd6f4;border:1px solid #45475a;
                        border-radius:6px;font-size:13px;}
            QListWidget::item{padding:6px 8px;border-radius:4px;}
            QListWidget::item:hover{background:#313244;}
        """)
        self._refresh_list()
        layout.addWidget(self._lst)

        # Buttons
        btn_row = QHBoxLayout()
        new_btn = QPushButton("+ 新建批次")
        new_btn.clicked.connect(self._on_new)
        btn_row.addWidget(new_btn)
        switch_btn = QPushButton("切换到此批次")
        switch_btn.clicked.connect(self._on_switch)
        btn_row.addWidget(switch_btn)
        del_btn = QPushButton("删除批次")
        del_btn.setStyleSheet("QPushButton{color:#FF6B6B;}")
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    def _refresh_list(self):
        self._lst.clear()
        current = self._batch_mgr.current_id()
        all_entries = self._entry_mgr.read_all_entries()
        counts = {}
        for e in all_entries:
            bid = e.get("batch_id", "")
            counts[bid] = counts.get(bid, 0) + 1
        for b in self._batch_mgr.list_batches():
            bid = b["id"]
            n = counts.get(bid, 0)
            marker = " ◀ 当前" if bid == current else ""
            exported = " ✓已导出" if b.get("exported") else ""
            text = f"{b['name']} ({n} 条){exported}{marker}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, bid)
            if bid == current:
                item.setForeground(Qt.green)
            self._lst.addItem(item)

    def _selected_id(self) -> str | None:
        items = self._lst.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _on_switch(self):
        bid = self._selected_id()
        if bid:
            self._batch_mgr.set_current(bid)
            self._refresh_list()

    def _on_new(self):
        name, ok = QInputDialog.getText(self, "新建批次", "批次名称:")
        if ok and name.strip():
            self._batch_mgr.add_batch(name.strip(), self._username)
            self._refresh_list()

    def _on_delete(self):
        bid = self._selected_id()
        if not bid:
            return
        if bid == "默认":
            QMessageBox.warning(self, "提示", "不能删除默认批次。")
            return
        r = QMessageBox.question(self, "确认", f"删除批次「{bid}」及其所有元数据？",
                                 QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            self._batch_mgr.delete_batch(bid)
            self._refresh_list()


class BatchExportDialog(QDialog):
    """导出选择：勾选批次后导出。"""

    def __init__(self, batch_mgr: BatchManager, entry_mgr: EntryManager, parent=None):
        super().__init__(parent)
        self._batch_mgr = batch_mgr
        self._entry_mgr = entry_mgr
        self._checks: list[tuple[str, QCheckBox, int]] = []

        self.setWindowTitle("选择批次导出")
        self.setMinimumSize(400, 280)
        self.resize(450, 320)
        self.setStyleSheet("QDialog{background-color:#1e1e2e;}")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel("选择要导出的批次:")
        lbl.setStyleSheet("font-size:14px;font-weight:bold;color:#89b4fa;")
        layout.addWidget(lbl)

        all_entries = self._entry_mgr.read_all_entries()
        for b in batch_mgr.list_batches():
            bid = b["id"]
            pending = sum(1 for e in all_entries
                         if e.get("batch_id") == bid and e.get("status") == "pending")
            exported = sum(1 for e in all_entries
                          if e.get("batch_id") == bid and e.get("status") == "synced")
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            cb = QCheckBox(f"{b['name']}")
            cb.setChecked(not b.get("exported", False))
            cb.setStyleSheet("color:#cdd6f4;font-size:13px;")
            rl.addWidget(cb)
            info = QLabel(f"待导出: {pending}  已导出: {exported}")
            info.setStyleSheet("color:#a6adc8;font-size:11px;")
            rl.addWidget(info)
            rl.addStretch()
            layout.addWidget(row)
            self._checks.append((bid, cb, pending))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_batches(self) -> list[str]:
        return [bid for bid, cb, _ in self._checks if cb.isChecked()]
