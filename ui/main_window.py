import os
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QWidget,
    QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QFileDialog, QMenuBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence

from core.settings import AppSettings
from core.image_manager import ImageManager
from core.label_manager import LabelManager
from core.undo_manager import UndoManager, UndoEntry
from core.crop_manager import CropManager
from core.preload_manager import PreloadManager
from core.progress_manager import ProgressManager
from utils.logger import get_logger


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, image_manager: ImageManager):
        super().__init__()
        self._settings = settings
        self._image_manager = image_manager

        self._label_manager = LabelManager(settings.label_csv_path)
        self._undo_manager = UndoManager(settings.max_undo_depth)
        self._crop_manager = CropManager(settings.target_dir)
        self._preload_manager = PreloadManager(settings)
        self._progress = ProgressManager()

        self._viewer = None
        self._info_overlay = None
        self._drag_zones: list = []
        self._status_label = QLabel("就绪")
        self._index_label = QLabel("")

        self._crop_size_name = ""
        self._blur_enabled = settings.get("general.blur_enabled", False)
        self._blur_threshold = settings.blur_threshold

        self.setWindowTitle("电力巡检图像数据集构建工具")
        self.setMinimumSize(800, 500)
        self.resize(1400, 900)
        self._build_menu()
        self._build_ui()
        self._connect_signals()
        self._apply_dark_theme()
        self._check_target_dir_on_startup()

    def _check_target_dir_on_startup(self):
        target = self._settings.target_dir
        if not target or not os.path.isdir(target):
            self._status_label.setText("请先在设置中指定分类输出目标目录")
            self._status_label.setStyleSheet("color: #FFD93D; font-weight: bold;")

    # ── Menu ──────────────────────────────────────────────
    def _build_menu(self):
        menu = QMenuBar()
        self.setMenuBar(menu)

        file_menu = menu.addMenu("文件(&F)")
        open_action = QAction("打开图片文件夹(&O)...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_open_directory)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu.addMenu("视图(&V)")
        fit_action = QAction("适应窗口(&F)", self)
        fit_action.setShortcut(QKeySequence("0"))
        fit_action.triggered.connect(lambda: self._viewer and self._viewer.reset_view())
        view_menu.addAction(fit_action)
        zoom100_action = QAction("原始尺寸(&1)", self)
        zoom100_action.setShortcut(QKeySequence("Ctrl+1"))
        zoom100_action.triggered.connect(
            lambda: self._viewer and self._viewer.resetTransform()
        )
        view_menu.addAction(zoom100_action)

        tools_menu = menu.addMenu("工具(&T)")
        settings_action = QAction("设置(&S)...", self)
        settings_action.triggered.connect(self._on_open_settings)
        tools_menu.addAction(settings_action)

    # ── UI Layout ─────────────────────────────────────────
    def _build_ui(self):
        self._build_toolbar()
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Center: Image viewer + info overlay ────────
        from widgets.image_viewer import ImageViewer
        self._viewer = ImageViewer(self._settings)

        from widgets.info_overlay import InfoOverlay
        self._info_overlay = InfoOverlay(self._viewer)
        self._info_overlay.hide()

        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.addWidget(self._viewer)

        # ── Right: Drag zones ──────────────────────────
        from widgets.drag_zone import DragZone
        self._drag_zones = []
        zone_container = QWidget()
        zone_container.setFixedWidth(160)
        self._zone_layout = QVBoxLayout(zone_container)
        self._zone_layout.setContentsMargins(4, 4, 4, 4)
        self._zone_layout.setSpacing(6)
        hint_label = QLabel("按键快速分类")
        hint_label.setStyleSheet("color: #a6adc8; font-size: 10px;")
        hint_label.setAlignment(Qt.AlignCenter)
        self._zone_layout.addWidget(hint_label)
        for mapping in self._settings.class_mappings:
            zone = DragZone(mapping)
            zone.image_dropped.connect(self._on_drag_classify)
            self._drag_zones.append(zone)
            self._zone_layout.addWidget(zone)
        self._zone_layout.addStretch()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(viewer_container)
        splitter.addWidget(zone_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1440, 160])
        layout.addWidget(splitter)

        self._build_status_bar()

    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        open_action = QAction("打开文件夹", self)
        open_action.triggered.connect(self._on_open_directory)
        toolbar.addAction(open_action)
        toolbar.addSeparator()

        for direction, text, tip in [
            ("prev", "◀ 上一张", "左方向键 / ←"),
            ("next", "下一张 ▶", "右方向键 / →"),
        ]:
            action = QAction(text, self)
            action.setToolTip(tip)
            action.triggered.connect(
                lambda d=direction: (
                    self._image_manager.go_prev() if d == "prev"
                    else self._image_manager.go_next()
                )
            )
            toolbar.addAction(action)

        toolbar.addSeparator()
        undo_action = QAction("↩ 撤销", self)
        undo_action.setToolTip("Ctrl+Z")
        undo_action.triggered.connect(self._on_undo)
        toolbar.addAction(undo_action)
        toolbar.addSeparator()

        settings_btn = QAction("设置", self)
        settings_btn.triggered.connect(self._on_open_settings)
        toolbar.addAction(settings_btn)

    def _build_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        status.addWidget(self._status_label, 1)
        status.addPermanentWidget(self._index_label)

    def _apply_dark_theme(self):
        config_dir = os.path.dirname(self._settings.config_path)
        # 优先从 config 目录加载，回退到源码目录
        qss_path = os.path.join(config_dir, "dark_theme.qss")
        if not os.path.exists(qss_path):
            import sys
            if getattr(sys, 'frozen', False):
                qss_path = os.path.join(sys._MEIPASS, "config", "dark_theme.qss")
            else:
                qss_path = os.path.join(os.path.dirname(__file__), "..", "config", "dark_theme.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    # ── Signal Wiring ─────────────────────────────────────
    def _connect_signals(self):
        self._image_manager.image_list_changed.connect(self._on_list_changed)
        self._image_manager.current_index_changed.connect(self._on_index_changed)
        self._image_manager.image_loaded.connect(self._on_image_loaded)
        self._image_manager.load_error.connect(self._on_load_error)
        self._viewer.navigate_requested.connect(self._on_navigate)
        self._viewer.classify_requested.connect(self._on_classify)
        self._viewer.undo_requested.connect(self._on_undo)
        self._viewer.crop_save_requested.connect(self._on_standalone_crop)
        self._viewer.crop_size_changed.connect(self._on_crop_size_changed)
        self._viewer.zoom_changed.connect(self._on_zoom_changed)
        self._preload_manager.preload_ready.connect(self._on_preload_ready)
        self._crop_manager.crop_saved.connect(self._on_crop_file_saved)
        self._crop_manager.crop_error.connect(
            lambda p, e: self._status_label.setText(f"裁剪失败: {e}")
        )

    # ── Slots: Navigation ─────────────────────────────────
    def _on_open_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if path:
            # 保存旧进度
            self._save_progress()
            # 加载新文件夹进度
            data = self._progress.load(path)
            self._image_manager.load_directory(path)
            # 恢复上次进度
            saved_idx = data.get("current_index", 0)
            total = self._image_manager.total_count()
            if 0 < saved_idx < total:
                self._image_manager.go_to(saved_idx)
            # 更新状态提示
            classified = data.get("classified", {})
            if classified:
                self._status_label.setText(
                    f"已加载进度: {len(classified)} 张已分类 | 当前 {saved_idx + 1}/{total}"
                )
                self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")

    def _on_list_changed(self):
        total = self._image_manager.total_count()
        idx = self._image_manager.current_index()
        self._index_label.setText(f"{idx + 1} / {total}" if total > 0 else "0 / 0")

    def _on_index_changed(self, index: int):
        total = self._image_manager.total_count()
        self._index_label.setText(f"{index + 1} / {total}")
        self._preload_manager.set_current_index(index, self._image_manager.get_image_list())

    def _on_image_loaded(self, path: str, pixmap):
        self._viewer.set_image(pixmap)
        filename = os.path.basename(path)
        self._info_overlay.update_info(
            filename=filename,
            resolution=f"{pixmap.width()}x{pixmap.height()}",
            zoom_percent=self._viewer.zoom_percent(),
            index=self._image_manager.current_index(),
            total=self._image_manager.total_count(),
            directory=self._image_manager.current_dir,
        )
        self._info_overlay.show()

        blur_msg = ""
        if self._blur_enabled:
            import cv2
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                var = cv2.Laplacian(img, cv2.CV_64F).var()
                if var < self._blur_threshold:
                    blur_msg = f"  [模糊: {var:.1f}]"
        self.setWindowTitle(f"{filename}{blur_msg} - 电力巡检图像数据集构建工具")

        has_crop = self._viewer_has_crop_overlay()
        if has_crop:
            self._status_label.setText("拖动裁剪框定位缺陷，按分类键保存裁剪+分类")
            self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        else:
            self._status_label.setText("按 1/2/3 可选裁剪，直接按分类键(QWER/ASDF/T)标记标签")
            self._status_label.setStyleSheet("")

    def _on_load_error(self, path: str, error: str):
        self._status_label.setText(f"加载失败: {error}")

    def _on_navigate(self, direction: str):
        nav_map = {
            "next": self._image_manager.go_next,
            "prev": self._image_manager.go_prev,
            "home": self._image_manager.go_home,
            "end": self._image_manager.go_end,
        }
        if direction in nav_map:
            nav_map[direction]()

    # ── Slots: Crop Overlay ──────────────────────────────
    def _on_crop_size_changed(self, size_name: str):
        self._crop_size_name = size_name
        self._status_label.setText(f"裁剪框: {size_name}  |  拖动定位，按分类键(QWER)保存")
        self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")

    def _viewer_has_crop_overlay(self) -> bool:
        from widgets.crop_overlay import CropOverlay
        for item in self._viewer.scene().items():
            if isinstance(item, CropOverlay):
                return True
        return False

    def _get_crop_rect(self):
        from widgets.crop_overlay import CropOverlay
        for item in self._viewer.scene().items():
            if isinstance(item, CropOverlay):
                return item.get_crop_rect()
        return None

    def _get_current_pixmap(self):
        from PySide6.QtWidgets import QGraphicsPixmapItem
        for item in self._viewer.scene().items():
            if isinstance(item, QGraphicsPixmapItem):
                return item.pixmap()
        return None

    # ── Slots: Standalone Crop (Enter key) ───────────────
    def _on_standalone_crop(self, rect):
        """Enter key — save crop to target dir without classifying."""
        src = self._image_manager.current_path()
        if not src:
            return
        target_dir = self._settings.target_dir
        if not target_dir:
            self._status_label.setText("裁剪失败: 未设置分类输出目录")
            return
        pixmap = self._get_current_pixmap()
        if not pixmap or pixmap.isNull():
            pixmap = self._image_manager.load_pixmap(src)
        if not pixmap or pixmap.isNull():
            self._status_label.setText("裁剪失败: 无法加载图片")
            return
        mgr = CropManager(target_dir)
        mgr.crop_saved.connect(
            lambda p: self._status_label.setText(f"裁剪已保存: {os.path.basename(p)}")
        )
        mgr.crop_error.connect(
            lambda p, e: self._status_label.setText(f"裁剪失败: {e}")
        )
        mgr.save_crop(pixmap, rect, src, self._crop_size_name)

    # ── Slots: Classify (QWER etc.) ────────────────────────
    def _on_classify(self, key: str, label: str):
        logger = get_logger()

        src = self._image_manager.current_path()
        if not src:
            return

        # 1) 检查目标目录
        target_dir = self._settings.target_dir
        if not target_dir:
            self._status_label.setText("目标目录未设置，请在设置中指定分类输出目录")
            self._status_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
            return
        os.makedirs(target_dir, exist_ok=True)

        mapping = next((m for m in self._settings.class_mappings if m.label == label), None)
        folder = mapping.folder if mapping else label

        # 2) 复制原图到目标目录，重命名为 label_6位流水号
        import shutil
        import glob as glob_mod
        dst_dir = os.path.join(target_dir, folder)
        os.makedirs(dst_dir, exist_ok=True)
        ext = os.path.splitext(src)[1].lower()
        # 计算下一个流水号（以 label 为文件名前缀）
        prefix = mapping.label if mapping else label
        existing = glob_mod.glob(os.path.join(dst_dir, f"{prefix}_*{ext}"))
        max_seq = 0
        for f in existing:
            stem = os.path.splitext(os.path.basename(f))[0]
            try:
                num = int(stem.rsplit("_", 1)[-1])
                max_seq = max(max_seq, num)
            except ValueError:
                pass
        seq = max_seq + 1
        new_filename = f"{prefix}_{seq:06d}{ext}"
        dst = os.path.join(dst_dir, new_filename)
        shutil.copy2(src, dst)
        logger.info(f"Copied: {src} -> {dst}")

        # 3) 如果有裁剪框，同时保存裁剪图
        crop_path = ""
        crop_rect = self._get_crop_rect()
        has_crop = crop_rect is not None and not crop_rect.isEmpty()
        if has_crop:
            pixmap = self._get_current_pixmap()
            if not pixmap or pixmap.isNull():
                pixmap = self._image_manager.load_pixmap(src)
            if pixmap and not pixmap.isNull():
                crop_path = self._crop_manager.save_crop(
                    pixmap, crop_rect, src, self._crop_size_name, folder
                )

        # 4) 记录标签
        self._label_manager.append(src, label, new_filename=new_filename)

        # 5) 记录 undo
        saved_idx = self._image_manager.current_index()
        entry = UndoEntry(
            src_path=dst,
            dst_path=crop_path,
            original_src=src,
            label=label,
            action_type="classify",
            original_index=saved_idx,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._undo_manager.push(entry)

        # 6) 清除裁剪框，自动下一张
        self._viewer.set_crop_overlay(None)
        self._crop_size_name = ""

        auto_next = self._settings.get("general.auto_next", True)
        total = self._image_manager.total_count()
        if auto_next and saved_idx < total - 1:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._image_manager.go_to(saved_idx + 1))
        else:
            self._image_manager.go_to(saved_idx)

        crop_msg = f" | 裁剪: {os.path.basename(crop_path)}" if crop_path else ""
        self._status_label.setText(
            f"已分类 '{label}' -> {os.path.basename(dst)}{crop_msg}  |  Ctrl+Z 撤销"
        )
        self._status_label.setStyleSheet("")
        self._save_progress()
        logger.info(f"Classified: {os.path.basename(src)} -> {label}, copy: {dst}" +
                    (f", crop: {crop_path}" if crop_path else ""))

    def _on_drag_classify(self, label: str):
        self._on_classify("", label)

    def _on_crop_file_saved(self, saved_path: str):
        """Signal from CropManager after classify-triggered crop."""
        pass  # _on_classify already updates status

    # ── Slots: Undo ───────────────────────────────────────
    def _on_undo(self):
        logger = get_logger()
        entry = self._undo_manager.pop()
        if entry is None:
            self._status_label.setText("没有可撤销的操作")
            return

        # 删除复制到目标目录的文件
        if entry.src_path and os.path.isfile(entry.src_path):
            try:
                os.remove(entry.src_path)
                logger.info(f"Deleted copy: {entry.src_path}")
            except OSError as e:
                logger.error(f"Failed to delete copy: {entry.src_path}: {e}")

        # 删除裁剪文件（如果有）
        if entry.dst_path and os.path.isfile(entry.dst_path):
            try:
                os.remove(entry.dst_path)
                logger.info(f"Deleted crop: {entry.dst_path}")
            except OSError as e:
                logger.error(f"Failed to delete crop: {entry.dst_path}: {e}")

        # 删除 CSV 记录（用原始路径查找）
        csv_key = entry.original_src or entry.src_path
        self._label_manager.remove_entry(csv_key)

        # 回到当时的图片位置
        target_idx = min(entry.original_index, self._image_manager.total_count() - 1)
        if target_idx >= 0:
            self._image_manager.go_to(target_idx)

        self._status_label.setText(f"已撤销: {os.path.basename(csv_key)} 已从目标目录删除")
        self._status_label.setStyleSheet("")
        self._save_progress()
        logger.info(f"Undo: removed {entry.src_path}" +
                    (f" and {entry.dst_path}" if entry.dst_path else ""))

    # ── Slots: Other ──────────────────────────────────────
    def _on_zoom_changed(self, percent: float):
        pass

    def _on_preload_ready(self, index: int, pixmap):
        self._image_manager.cache_pixmap(index, pixmap)

    def _save_progress(self):
        idx = self._image_manager.current_index()
        flist = self._image_manager.get_image_list()
        if not flist or not self._image_manager.current_dir:
            return
        # 从 label_manager 获取当前已分类图片
        classified = {}
        for row in self._label_manager.get_labels():
            fn = os.path.basename(row["image_path"])
            classified[fn] = row["label"]
        self._progress.save(idx, flist, classified)

    def _on_open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings.reload()
            self._crop_manager._output_dir = self._settings.target_dir
            self._viewer._load_key_maps()
            self._rebuild_drag_zones()
            self._check_target_dir_on_startup()

    def _rebuild_drag_zones(self):
        from widgets.drag_zone import DragZone
        # 删除旧拖拽区
        for z in self._drag_zones:
            z.setParent(None)
            z.deleteLater()
        self._drag_zones.clear()
        # 找到 self._zone_layout（在 _build_ui 中创建）
        if not hasattr(self, '_zone_layout') or self._zone_layout is None:
            return
        # 移除旧的 DragZone（保留 hint_label 和 stretch）
        while self._zone_layout.count() > 2:
            item = self._zone_layout.takeAt(self._zone_layout.count() - 2)
            if item and item.widget():
                item.widget().deleteLater()
        # 重新添加
        for mapping in self._settings.class_mappings:
            zone = DragZone(mapping)
            zone.image_dropped.connect(self._on_drag_classify)
            self._drag_zones.append(zone)
            self._zone_layout.insertWidget(self._zone_layout.count() - 1, zone)
