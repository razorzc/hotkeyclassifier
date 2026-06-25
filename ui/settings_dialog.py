import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QFormLayout, QListWidget,
    QListWidgetItem, QDialogButtonBox, QFileDialog, QScrollArea,
    QGridLayout, QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QKeySequence

from core.settings import AppSettings

# 快捷键动作中英对照
BINDING_LABELS = [
    ("next",       "下一张"),
    ("prev",       "上一张"),
    ("first",      "第一张"),
    ("last",       "最后一张"),
    ("zoom_in",    "放大"),
    ("zoom_out",   "缩小"),
    ("zoom_fit",   "适应窗口"),
    ("zoom_100",   "原始尺寸"),
    ("undo",       "撤销"),
    ("crop_save",  "保存裁剪"),
    ("crop_small", "裁剪框 224"),
    ("crop_medium","裁剪框 384"),
    ("crop_large", "裁剪框 640"),
    ("fullscreen", "全屏"),
    ("toggle_info","信息面板"),
]


class _KeyCaptureDialog(QDialog):
    """Modal dialog that captures a single key combination."""

    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("按下新快捷键")
        self.setFixedSize(340, 180)
        self.setStyleSheet("QDialog { background-color: #1e1e2e; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        hint = QLabel("请按下新的快捷键组合...")
        hint.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: bold;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self._display = QLabel(current or "—")
        self._display.setStyleSheet("""
            color: #89b4fa; font-size: 20px; font-weight: bold;
            background-color: #313244; border-radius: 8px; padding: 14px;
        """)
        self._display.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._display)

        btns = QHBoxLayout()
        clear_btn = QPushButton("清除")
        clear_btn.clicked.connect(lambda: self._set_result(""))
        btns.addWidget(clear_btn)
        btns.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self._result = current
        self._modifiers = 0

    def _set_result(self, val):
        self._result = val
        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        parts = []
        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.AltModifier:
            parts.append("Alt")
        key = event.key()
        key_str = self._key_name(key)
        if key_str:
            parts.append(key_str)
        self._result = "+".join(parts)
        self._display.setText(self._result)

    def _key_name(self, key: int) -> str:
        names = {
            Qt.Key_Left: "Left", Qt.Key_Right: "Right",
            Qt.Key_Up: "Up", Qt.Key_Down: "Down",
            Qt.Key_Home: "Home", Qt.Key_End: "End",
            Qt.Key_Return: "Return", Qt.Key_Enter: "Enter",
            Qt.Key_Space: "Space", Qt.Key_Escape: "Escape",
            Qt.Key_Tab: "Tab", Qt.Key_Backspace: "Backspace",
            Qt.Key_Delete: "Delete", Qt.Key_Insert: "Insert",
            Qt.Key_PageUp: "PageUp", Qt.Key_PageDown: "PageDown",
            Qt.Key_Plus: "Plus", Qt.Key_Minus: "Minus",
            Qt.Key_Equal: "Equal",
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3",
            Qt.Key_F4: "F4", Qt.Key_F5: "F5", Qt.Key_F6: "F6",
            Qt.Key_F7: "F7", Qt.Key_F8: "F8", Qt.Key_F9: "F9",
            Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
        }
        if key in names:
            return names[key]
        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(key).upper()
        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(key)
        return ""

    def result(self) -> str:
        return self._result


class _BindingRow(QWidget):
    """One key binding row: label | current key | edit button."""

    def __init__(self, action: str, label: str, current: str):
        super().__init__()
        self._action = action
        self._current = current
        self.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background:transparent;")
        lbl.setFixedWidth(120)
        layout.addWidget(lbl)

        self._key_label = QLabel(current or "—")
        self._key_label.setStyleSheet("""
            color: #ffffff; font-size: 14px; font-weight: bold;
            background-color: #45475a; border-radius: 4px;
            padding: 5px 14px;
        """)
        self._key_label.setMinimumWidth(120)
        self._key_label.setMaximumWidth(160)
        self._key_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._key_label)

        edit_btn = QPushButton("修改")
        edit_btn.setFixedWidth(56)
        edit_btn.clicked.connect(self._on_edit)
        layout.addWidget(edit_btn)

        layout.addStretch()

    def _on_edit(self):
        dlg = _KeyCaptureDialog(self._current, self.window())
        dlg.keyPressEvent = lambda e: dlg.__class__.keyPressEvent(dlg, e)
        if dlg.exec():
            self._current = dlg.result()
            self._key_label.setText(self._current or "—")

    def get_data(self) -> tuple:
        return self._action, self._current


class _ClassRow(QWidget):
    """Editable classification row: key | label | folder | color | delete."""

    def __init__(self, key: str, label: str, folder: str, color: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.key_edit = QLineEdit(key)
        self.key_edit.setFixedWidth(32)
        self.key_edit.setMaxLength(1)
        self.key_edit.setAlignment(Qt.AlignCenter)
        self.key_edit.setToolTip("快捷键（单个字母）")

        self.label_edit = QLineEdit(label)
        self.label_edit.setToolTip("英文标签")

        self.folder_edit = QLineEdit(folder)
        self.folder_edit.setToolTip("子目录名")

        self._color = color
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setToolTip("点击修改颜色")
        self._update_color()
        self.color_btn.clicked.connect(self._pick_color)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(32, 28)
        self.del_btn.setStyleSheet(
            "QPushButton{background-color:#313244;color:#FF6B6B;border:1px solid #45475a;"
            "border-radius:4px;font-size:12px;font-weight:bold;padding:0;}"
            "QPushButton:hover{background-color:#45475a;}"
        )
        self.del_btn.setToolTip("删除")

        layout.addWidget(self.key_edit)
        layout.addWidget(self.label_edit, 1)
        layout.addWidget(self.folder_edit, 1)
        layout.addWidget(self.color_btn)
        layout.addWidget(self.del_btn)

    def _update_color(self):
        self.color_btn.setStyleSheet(f"""
            QPushButton {{ background-color:{self._color}; border:2px solid #585b70;
                         border-radius:14px; }} QPushButton:hover {{ border-color:#cdd6f4; }}
        """)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "选择颜色")
        if c.isValid():
            self._color = c.name()
            self._update_color()

    def get_data(self) -> dict:
        return {
            "key": self.key_edit.text().strip().upper(),
            "label": self.label_edit.text().strip(),
            "folder": self.folder_edit.text().strip(),
            "color": self._color,
        }


class _CropRow(QWidget):
    """Editable crop size row: key | name | width | height | delete."""

    def __init__(self, key: str, name: str, w: int, h: int):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.key_edit = QLineEdit(key)
        self.key_edit.setFixedWidth(32)
        self.key_edit.setMaxLength(1)
        self.key_edit.setAlignment(Qt.AlignCenter)
        self.key_edit.setToolTip("快捷键")

        self.name_edit = QLineEdit(name)
        self.name_edit.setToolTip("名称")

        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 4096)
        self.w_spin.setValue(w)
        self.w_spin.setFixedWidth(56)
        self.w_spin.setToolTip("宽度(px)")

        self.h_spin = QSpinBox()
        self.h_spin.setRange(1, 4096)
        self.h_spin.setValue(h)
        self.h_spin.setFixedWidth(56)
        self.h_spin.setToolTip("高度(px)")

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(32, 28)
        self.del_btn.setStyleSheet(
            "QPushButton{background-color:#313244;color:#FF6B6B;border:1px solid #45475a;"
            "border-radius:4px;font-size:12px;font-weight:bold;padding:0;}"
            "QPushButton:hover{background-color:#45475a;}"
        )
        self.del_btn.setToolTip("删除")

        layout.addWidget(self.key_edit)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.w_spin)
        layout.addWidget(QLabel("x"))
        layout.addWidget(self.h_spin)
        layout.addWidget(self.del_btn)

    def get_data(self) -> dict:
        return {
            "key": self.key_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "width": self.w_spin.value(),
            "height": self.h_spin.value(),
        }


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._binding_rows: list[_BindingRow] = []
        self._class_rows: list[_ClassRow] = []
        self._crop_rows: list[_CropRow] = []
        self.setWindowTitle("设置")
        self.setMinimumSize(640, 540)
        self.resize(700, 580)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "通用")
        tabs.addTab(self._build_paths_tab(), "路径")
        tabs.addTab(self._build_display_tab(), "显示")
        tabs.addTab(self._build_keybindings_tab(), "快捷键")
        tabs.addTab(self._build_classifications_tab(), "分类配置")
        tabs.addTab(self._build_crop_tab(), "裁剪尺寸")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox()
        self._ok_btn = buttons.addButton("确定", QDialogButtonBox.AcceptRole)
        self._cancel_btn = buttons.addButton("取消", QDialogButtonBox.RejectRole)
        self._apply_btn = buttons.addButton("应用", QDialogButtonBox.ApplyRole)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        self._apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(buttons)

        self.setStyleSheet("""
            * { font-family: \"Microsoft YaHei\"; }
            QTabWidget::pane {
                border: 1px solid #45475a; border-radius: 6px;
                background-color: #1e1e2e;
            }
            QTabBar::tab {
                background-color: #313244; color: #cdd6f4;
                padding: 10px 20px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                font-size: 14px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #1e1e2e; color: #ffffff;
                border-bottom: 3px solid #89b4fa;
            }
            QTabBar::tab:hover:!selected {
                background-color: #45475a; color: #ffffff;
            }
            QFormLayout { spacing: 12px; }
            QLabel {
                color: #cdd6f4; font-size: 14px;
                padding: 3px 0; background-color: transparent;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #313244; color: #ffffff;
                border: 1px solid #585b70; border-radius: 4px;
                padding: 6px 10px; font-size: 14px; min-width: 100px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus { border-color: #89b4fa; }
            QLineEdit {
                background-color: #313244; color: #ffffff;
                border: 1px solid #585b70; border-radius: 4px;
                padding: 6px 10px; font-size: 14px;
            }
            QLineEdit:focus { border-color: #89b4fa; }
            QLineEdit[readOnly=\"true\"] {
                color: #a6adc8;
            }
            QCheckBox {
                color: #cdd6f4; font-size: 14px; spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px; height: 20px; border: 2px solid #585b70;
                border-radius: 4px; background-color: #313244;
            }
            QCheckBox::indicator:checked {
                background-color: #89b4fa; border-color: #89b4fa;
            }
            QCheckBox::indicator:hover { border-color: #89b4fa; }
            QListWidget {
                background-color: #181825; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 4px; font-size: 14px;
            }
            QListWidget::item { padding: 8px 10px; border-radius: 4px; }
            QListWidget::item:hover { background-color: #313244; }
            QPushButton {
                background-color: #45475a; color: #ffffff;
                border: 1px solid #585b70; border-radius: 6px;
                padding: 8px 24px; font-size: 14px; font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #585b70; border-color: #89b4fa; }
            QPushButton:pressed { background-color: #6c7086; }
            QPushButton[text=\"确定\"] {
                background-color: #89b4fa; color: #1e1e2e; border-color: #89b4fa;
            }
            QPushButton[text=\"确定\"]:hover { background-color: #b4d0fb; }
            QScrollBar:vertical { background: #181825; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #45475a; border-radius: 5px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #585b70; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    # ── General Tab ───────────────────────────────────────
    def _build_general_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(20, 16, 20, 16)

        title = QLabel("通用设置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa; margin-bottom: 8px;")
        form.addRow(title)

        self._username_edit = QLineEdit()
        self._username_edit.setText(self._settings.get("general.username", ""))
        self._username_edit.setPlaceholderText("多人协作时的标注人标识")
        form.addRow(QLabel("用户名:"), self._username_edit)

        self._preload_spin = QSpinBox()
        self._preload_spin.setRange(1, 20)
        self._preload_spin.setValue(self._settings.get("general.preload_count", 5))
        form.addRow(QLabel("预加载数量:"), self._preload_spin)

        self._blur_thresh_spin = QDoubleSpinBox()
        self._blur_thresh_spin.setRange(0, 1000)
        self._blur_thresh_spin.setValue(self._settings.get("general.blur_threshold", 100.0))
        form.addRow(QLabel("模糊阈值:"), self._blur_thresh_spin)

        self._auto_next_cb = QCheckBox()
        self._auto_next_cb.setChecked(self._settings.get("general.auto_next", True))
        form.addRow(QLabel("自动下一张:"), self._auto_next_cb)

        self._skip_classified_cb = QCheckBox()
        self._skip_classified_cb.setChecked(self._settings.get("general.skip_classified", False))
        form.addRow(QLabel("跳过已分类:"), self._skip_classified_cb)

        self._undo_depth_spin = QSpinBox()
        self._undo_depth_spin.setRange(1, 200)
        self._undo_depth_spin.setValue(self._settings.get("general.max_undo_depth", 50))
        form.addRow(QLabel("最大撤销步数:"), self._undo_depth_spin)

        return w

    # ── Paths Tab ─────────────────────────────────────────
    def _build_paths_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(20, 16, 20, 16)

        title = QLabel("路径设置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa; margin-bottom: 8px;")
        form.addRow(title)

        target_row = QWidget()
        target_layout = QHBoxLayout(target_row)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(8)
        self._target_dir_edit = QLineEdit()
        self._target_dir_edit.setText(self._settings.target_dir)
        self._target_dir_edit.setReadOnly(True)
        self._target_dir_edit.setPlaceholderText("未设置 — 选择分类图片和裁剪图的输出目录")
        target_layout.addWidget(self._target_dir_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._on_browse_target_dir)
        target_layout.addWidget(browse_btn)
        form.addRow(QLabel("分类输出目录:"), target_row)

        return w

    def _on_browse_target_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择分类输出目录")
        if path:
            self._target_dir_edit.setText(path)

    # ── Display Tab ───────────────────────────────────────
    def _build_display_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(20, 16, 20, 16)

        title = QLabel("显示设置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa; margin-bottom: 8px;")
        form.addRow(title)

        self._zoom_step_spin = QDoubleSpinBox()
        self._zoom_step_spin.setRange(0.01, 0.5)
        self._zoom_step_spin.setSingleStep(0.05)
        self._zoom_step_spin.setValue(self._settings.get("display.zoom_step", 0.15))
        form.addRow(QLabel("缩放步长:"), self._zoom_step_spin)

        self._max_zoom_spin = QDoubleSpinBox()
        self._max_zoom_spin.setRange(1.0, 50.0)
        self._max_zoom_spin.setValue(self._settings.get("display.max_zoom", 10.0))
        form.addRow(QLabel("最大缩放:"), self._max_zoom_spin)

        self._min_zoom_spin = QDoubleSpinBox()
        self._min_zoom_spin.setRange(0.01, 1.0)
        self._min_zoom_spin.setSingleStep(0.05)
        self._min_zoom_spin.setValue(self._settings.get("display.min_zoom", 0.05))
        form.addRow(QLabel("最小缩放:"), self._min_zoom_spin)

        self._overlay_opacity_spin = QDoubleSpinBox()
        self._overlay_opacity_spin.setRange(0.1, 1.0)
        self._overlay_opacity_spin.setSingleStep(0.05)
        self._overlay_opacity_spin.setValue(self._settings.get("display.info_overlay_opacity", 0.85))
        form.addRow(QLabel("信息面板透明度:"), self._overlay_opacity_spin)

        return w

    # ── Key Bindings Tab ──────────────────────────────────
    def _build_keybindings_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        title = QLabel("快捷键设置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa; margin-bottom: 4px;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:#11111b;border:1px solid #45475a;border-radius:6px;} QScrollArea>QWidget{background:#11111b;}")
        container = QWidget()
        container.setStyleSheet("background-color: #11111b;")
        grid = QVBoxLayout(container)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        grid.setAlignment(Qt.AlignTop)

        bindings = self._settings.key_bindings
        self._binding_rows.clear()
        for action, zh_name in BINDING_LABELS:
            current = bindings.get(action, "")
            row = _BindingRow(action, zh_name, current)
            self._binding_rows.append(row)
            grid.addWidget(row)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        hint = QLabel("点击「修改」，在弹出窗口中按下新快捷键，回车保存。")
        hint.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 4px 0;")
        layout.addWidget(hint)

        return w

    # ── Classifications Tab ────────────────────────────────
    def _build_classifications_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("分类配置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa;")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("+ 添加")
        add_btn.setFixedWidth(70)
        add_btn.clicked.connect(lambda: self._add_class_row())
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Scrollable rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:#11111b;border:1px solid #45475a;border-radius:6px;} QScrollArea>QWidget{background:#11111b;}")
        self._class_container = QWidget()
        self._class_container.setStyleSheet("background-color: #11111b;")
        self._class_layout = QVBoxLayout(self._class_container)
        self._class_layout.setContentsMargins(4, 2, 4, 2)
        self._class_layout.setSpacing(2)
        self._class_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._class_container)
        layout.addWidget(scroll, 1)

        self._class_rows.clear()
        for m in self._settings.class_mappings:
            self._add_class_row(m.key, m.label, m.folder, m.color)

        hint = QLabel("修改后点击「应用」或「确定」生效。键不可重复。")
        hint.setStyleSheet("color: #cdd6f4; font-size: 12px; padding: 4px 0;")
        layout.addWidget(hint)
        return w

    def _add_class_row(self, key="", label="", folder="", color="#89B4FA"):
        row = _ClassRow(key, label, folder, color)
        row.del_btn.clicked.connect(lambda: self._remove_class_row(row))
        self._class_rows.append(row)
        self._class_layout.addWidget(row)
        self._class_container.adjustSize()

    def _remove_class_row(self, row):
        if len(self._class_rows) <= 1:
            return
        self._class_rows.remove(row)
        self._class_layout.removeWidget(row)
        row.deleteLater()

    # ── Crop Tab ──────────────────────────────────────────
    def _build_crop_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        title = QLabel("裁剪尺寸配置")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa;")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = QPushButton("+ 添加")
        add_btn.setFixedWidth(70)
        add_btn.clicked.connect(lambda: self._add_crop_row())
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:#11111b;border:1px solid #45475a;border-radius:6px;} QScrollArea>QWidget{background:#11111b;}")
        self._crop_container = QWidget()
        self._crop_container.setStyleSheet("background-color: #11111b;")
        self._crop_layout = QVBoxLayout(self._crop_container)
        self._crop_layout.setContentsMargins(4, 2, 4, 2)
        self._crop_layout.setSpacing(2)
        self._crop_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._crop_container)
        layout.addWidget(scroll, 1)

        self._crop_rows.clear()
        for cs in self._settings.crop_sizes:
            self._add_crop_row(cs.key, cs.name, cs.width, cs.height)

        hint = QLabel("修改后点击「应用」或「确定」生效。")
        hint.setStyleSheet("color: #cdd6f4; font-size: 12px; padding: 4px 0;")
        layout.addWidget(hint)
        return w

    def _add_crop_row(self, key="", name="", w=224, h=224):
        row = _CropRow(key, name, w, h)
        row.del_btn.clicked.connect(lambda: self._remove_crop_row(row))
        self._crop_rows.append(row)
        self._crop_layout.addWidget(row)
        self._crop_container.adjustSize()

    def _remove_crop_row(self, row):
        if len(self._crop_rows) <= 1:
            return
        self._crop_rows.remove(row)
        self._crop_layout.removeWidget(row)
        row.deleteLater()

    # ── Apply / OK ────────────────────────────────────────
    def _on_apply(self):
        self._settings.set("general.username", self._username_edit.text().strip())
        self._settings.set("general.preload_count", self._preload_spin.value())
        self._settings.set("general.blur_threshold", self._blur_thresh_spin.value())
        self._settings.set("general.auto_next", self._auto_next_cb.isChecked())
        self._settings.set("general.skip_classified", self._skip_classified_cb.isChecked())
        self._settings.set("general.max_undo_depth", self._undo_depth_spin.value())
        self._settings.set("display.zoom_step", self._zoom_step_spin.value())
        self._settings.set("display.max_zoom", self._max_zoom_spin.value())
        self._settings.set("display.min_zoom", self._min_zoom_spin.value())
        self._settings.set("display.info_overlay_opacity", self._overlay_opacity_spin.value())
        self._settings.set("paths.target_dir", self._target_dir_edit.text())

        # Save key bindings
        binding_data = {}
        for row in self._binding_rows:
            action, key = row.get_data()
            if key:
                binding_data[action] = key
        if binding_data:
            self._settings.set("key_bindings", binding_data)

        # Save classifications
        class_data = []
        seen = set()
        for row in self._class_rows:
            d = row.get_data()
            if not d["key"] or not d["label"] or not d["folder"]:
                continue
            if d["key"] in seen:
                continue
            seen.add(d["key"])
            class_data.append(d)
        if class_data:
            self._settings.set("classifications", class_data)

        # Save crop sizes
        crop_data = []
        for row in self._crop_rows:
            d = row.get_data()
            if not d["key"] or not d["name"]:
                continue
            crop_data.append(d)
        if crop_data:
            self._settings.set("crop_sizes", crop_data)

        self._settings.save()

    def _on_ok(self):
        self._on_apply()
        self.accept()
