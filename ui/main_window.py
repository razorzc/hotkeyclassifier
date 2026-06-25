import os
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QWidget, QMessageBox,
    QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QFileDialog, QMenuBar,
    QInputDialog, QProgressDialog, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence

from core.settings import AppSettings
from core.image_manager import ImageManager
from core.entry_manager import EntryManager
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

        self._entry_manager = EntryManager()
        self._undo_manager = UndoManager(settings.max_undo_depth)
        self._crop_manager = CropManager(settings.target_dir)
        self._preload_manager = PreloadManager(settings)
        self._progress = ProgressManager(settings.get("general.username", ""))

        self._viewer = None
        self._info_overlay = None
        self._drag_zones: list = []
        self._status_label = QLabel("就绪")
        self._index_label = QLabel("")

        self._crop_size_name = ""
        self._blur_enabled = settings.get("general.blur_enabled", False)
        self._blur_threshold = settings.blur_threshold
        self._classified_map: dict[str, dict] = {}       # basename -> {label, by, at}
        self._multi_count: dict[str, int] = {}           # basename -> 标注人数

        self.setWindowTitle("电力巡检图像数据集构建工具")
        self.setMinimumSize(800, 500)
        self.resize(1400, 900)
        self._ensure_username()
        self._build_menu()
        self._build_ui()
        self._connect_signals()
        self._apply_dark_theme()

    # ── Username ──────────────────────────────────────────
    def _ensure_username(self):
        user = self._settings.get("general.username", "")
        if user:
            self._progress.set_username(user)
            return
        # 延迟弹窗
        from PySide6.QtCore import QTimer
        QTimer.singleShot(200, self._prompt_username)

    def _prompt_username(self):
        name, ok = QInputDialog.getText(
            self, "设置用户名", "首次使用请输入用户名（用于协作标注）:",
            text="user"
        )
        if ok and name.strip():
            self._settings.set("general.username", name.strip())
            self._settings.save()
            self._progress.set_username(name.strip())
            self._status_label.setText(f"欢迎, {name.strip()}!")
        elif not self._settings.get("general.username", ""):
            self._status_label.setText("未设置用户名，请到设置→通用中配置")
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
        export_action = QAction("导出到目标目录(&E)...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)
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
        tools_menu.addSeparator()
        undo_list_menu = QAction("撤销列表(&L)...", self)
        undo_list_menu.triggered.connect(self._on_undo_list)
        tools_menu.addAction(undo_list_menu)

        help_menu = menu.addMenu("帮助(&H)")
        update_action = QAction("检查更新(&U)...", self)
        update_action.triggered.connect(self._on_check_update)
        help_menu.addAction(update_action)
        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    # ── UI Layout ─────────────────────────────────────────
    def _build_ui(self):
        self._build_toolbar()
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from widgets.image_viewer import ImageViewer
        self._viewer = ImageViewer(self._settings)

        from widgets.info_overlay import InfoOverlay
        self._info_overlay = InfoOverlay(self._viewer)
        self._info_overlay.hide()

        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.addWidget(self._viewer)

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
        self._filter_action = QAction("∨ 仅未分类", self)
        self._filter_action.setCheckable(True)
        self._filter_action.setToolTip("切换显示：全部 / 仅未分类")
        self._filter_action.triggered.connect(self._on_toggle_filter)
        toolbar.addAction(self._filter_action)
        toolbar.addSeparator()

        export_btn = QAction("导出", self)
        export_btn.setToolTip("将已分类图片批量复制到目标目录")
        export_btn.triggered.connect(self._on_export)
        toolbar.addAction(export_btn)
        toolbar.addSeparator()

        undo_action = QAction("↩ 撤销", self)
        undo_action.setToolTip("Ctrl+Z — 撤销最近一次分类")
        undo_action.triggered.connect(self._on_undo)
        toolbar.addAction(undo_action)
        undo_list_action = QAction("≡ 撤销列表", self)
        undo_list_action.setToolTip("查看并撤销本批次的分类")
        undo_list_action.triggered.connect(self._on_undo_list)
        toolbar.addAction(undo_list_action)
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

    # ── Slots: Navigation ─────────────────────────────────
    def _on_open_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if path:
            self._save_progress()
            # 合并所有用户进度 + entry_manager 元数据
            self._classified_map = self._progress.get_merged_classified(path)
            self._multi_count.clear()
            all_entries = self._entry_manager.read_all_entries()
            for e in all_entries:
                bn = os.path.basename(e["image_path"])
                self._multi_count[bn] = self._multi_count.get(bn, 0) + 1
            data = self._progress.load_my(path)
            self._image_manager.load_directory(path)
            saved_idx = data.get("current_index", 0)
            total = self._image_manager.total_count()
            if 0 < saved_idx < total:
                self._image_manager.go_to(saved_idx)
            if self._filter_action and self._filter_action.isChecked():
                self._apply_unclassified_filter()
            classified_count = len(self._classified_map)
            if classified_count:
                self._status_label.setText(
                    f"已加载: {classified_count} 张已分类 | 当前 {min(saved_idx+1, total)}/{total}"
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
        self._save_progress()

    def _on_image_loaded(self, path: str, pixmap):
        self._viewer.set_image(pixmap)
        filename = os.path.basename(path)

        # 从合并后的进度获取分类信息
        info = self._classified_map.get(filename, {})
        classified_label = info.get("label", "")
        classified_by = info.get("by", "")
        classified_at = info.get("at", "")[:10] if info.get("at") else ""
        multi = self._multi_count.get(filename, 0)

        self._info_overlay.update_info(
            filename=filename,
            resolution=f"{pixmap.width()}x{pixmap.height()}",
            zoom_percent=self._viewer.zoom_percent(),
            index=self._image_manager.current_index(),
            total=self._image_manager.total_count(),
            directory=self._image_manager.current_dir,
            classified_label=classified_label,
            classified_by=classified_by,
            classified_at=classified_at,
            multi_count=multi,
        )
        self._info_overlay.show()

        blur_msg = ""
        if self._blur_enabled:
            try:
                import cv2
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    var = cv2.Laplacian(img, cv2.CV_64F).var()
                    if var < self._blur_threshold:
                        blur_msg = f"  [模糊: {var:.1f}]"
            except ImportError:
                pass
        self.setWindowTitle(f"{filename}{blur_msg} - 电力巡检图像数据集构建工具")

        has_crop = self._viewer_has_crop_overlay()
        if has_crop:
            self._status_label.setText("拖动裁剪框定位缺陷，按分类键保存")
            self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        else:
            self._status_label.setText("按 1/2/3 可选裁剪，直接按分类键标记标签")
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

    # ── Slots: Crop ───────────────────────────────────────
    def _on_crop_size_changed(self, size_name: str):
        self._crop_size_name = size_name
        self._status_label.setText(f"裁剪框: {size_name}  |  拖动定位，按分类键")

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

    def _on_standalone_crop(self, rect):
        """Enter key — standalone crop (不分类，直接保存到目标目录)"""
        src = self._image_manager.current_path()
        if not src:
            return
        target_dir = self._settings.target_dir
        if not target_dir:
            self._status_label.setText("裁剪失败: 未设置目标目录")
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

    # ── Slots: Classify (元数据记录，不操作文件) ──────────
    def _on_classify(self, key: str, label: str):
        logger = get_logger()
        username = self._settings.get("general.username", "")
        if not username:
            self._prompt_username()
            if not self._settings.get("general.username", ""):
                self._status_label.setText("请先设置用户名再分类")
                self._status_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
                return

        src = self._image_manager.current_path()
        if not src:
            return

        # 保存裁剪（如果有裁剪框）
        crop_rect = self._get_crop_rect()
        has_crop = crop_rect is not None and not crop_rect.isEmpty()
        if has_crop:
            target_dir = self._settings.target_dir
            if target_dir:
                pixmap = self._get_current_pixmap()
                if not pixmap or pixmap.isNull():
                    pixmap = self._image_manager.load_pixmap(src)
                if pixmap and not pixmap.isNull():
                    folder = ""
                    mapping = next((m for m in self._settings.class_mappings if m.label == label), None)
                    if mapping:
                        folder = mapping.folder
                    self._crop_manager.save_crop(pixmap, crop_rect, src, self._crop_size_name, folder)

        # 写元数据
        entry_path = self._entry_manager.write_entry(src, label, username)
        self._classified_map[os.path.basename(src)] = {"label": label, "by": username, "at": ""}
        self._multi_count[os.path.basename(src)] = self._multi_count.get(os.path.basename(src), 0) + 1

        # 记录 undo
        saved_idx = self._image_manager.current_index()
        entry = UndoEntry(
            src_path=src,
            dst_path=entry_path,
            original_src=src,
            label=label,
            action_type="classify",
            original_index=saved_idx,
            classified_by=username,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._undo_manager.push(entry)

        # 自动下一张
        self._viewer.set_crop_overlay(None)
        self._crop_size_name = ""
        auto_next = self._settings.get("general.auto_next", True)
        total = self._image_manager.total_count()
        if auto_next and saved_idx < total - 1:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._image_manager.go_to(saved_idx + 1))
        else:
            self._image_manager.go_to(saved_idx)

        self._status_label.setText(
            f"已分类 '{label}' | 标注人: {username} | Ctrl+Z 撤销"
        )
        self._status_label.setStyleSheet("")
        self._save_progress()
        logger.info(f"Classified: {os.path.basename(src)} -> {label} by {username}")

    def _on_drag_classify(self, label: str):
        self._on_classify("", label)

    # ── Slots: Export ─────────────────────────────────────
    def _on_export(self):
        """批量导出：将 pending 记录复制到目标目录并重命名。"""
        import shutil
        import glob as glob_mod

        target_dir = self._settings.target_dir
        if not target_dir:
            QMessageBox.warning(self, "导出", "请先在设置中指定分类输出目录。")
            return

        entries = [e for e in self._entry_manager.read_all_entries()
                   if e.get("status") == "pending"]
        if not entries:
            QMessageBox.information(self, "导出", "没有需要导出的记录。")
            return

        total = len(entries)
        progress = QProgressDialog("正在导出...", "取消", 0, total, self)
        progress.setWindowTitle("导出到目标目录")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()

        exported = 0
        for i, entry in enumerate(entries):
            if progress.wasCanceled():
                break
            progress.setValue(i + 1)
            progress.setLabelText(f"导出: {os.path.basename(entry['image_path'])}")
            QApplication.processEvents()

            src = entry["image_path"]
            if not os.path.isfile(src):
                continue

            label = entry.get("label", "unknown")
            folder = ""
            for m in self._settings.class_mappings:
                if m.label == label:
                    folder = m.folder
                    break
            if not folder:
                folder = label

            dst_dir = os.path.join(target_dir, folder)
            os.makedirs(dst_dir, exist_ok=True)
            ext = os.path.splitext(src)[1].lower()
            prefix = label

            existing = glob_mod.glob(os.path.join(dst_dir, f"{prefix}_*{ext}"))
            max_seq = 0
            for f in existing:
                try:
                    num = int(os.path.splitext(os.path.basename(f))[0].rsplit("_", 1)[-1])
                    max_seq = max(max_seq, num)
                except ValueError:
                    pass
            seq = max_seq + 1
            new_fn = f"{prefix}_{seq:06d}{ext}"
            dst = os.path.join(dst_dir, new_fn)

            try:
                shutil.copy2(src, dst)
                self._entry_manager.set_synced(
                    entry.get("_entry_file", f"{entry['classified_by']}_{entry['modified_at'].replace(':', '')}.json"),
                    new_fn
                )
                exported += 1
            except OSError as e:
                get_logger().error(f"Export failed: {src} -> {dst}: {e}")

        progress.close()
        # 重建汇总 CSV
        self._entry_manager.build_csv(self._settings.get("paths.label_csv_dir", "labels") +
                                       "/" + self._settings.get("paths.label_csv_name", "labels.csv"))
        self._status_label.setText(f"导出完成: {exported}/{total} 条")
        self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")

    # ── Slots: Undo ───────────────────────────────────────
    def _on_undo(self):
        logger = get_logger()
        entry = self._undo_manager.pop()
        if entry is None:
            self._status_label.setText("没有可撤销的操作")
            return

        # 删除元数据增量文件
        if entry.dst_path and os.path.isfile(entry.dst_path):
            fn = os.path.basename(entry.dst_path)
            self._entry_manager.delete_entry_file(fn)

        # 更新 classified_map
        bn = os.path.basename(entry.original_src or entry.src_path)
        self._classified_map.pop(bn, None)
        cnt = self._multi_count.get(bn, 1)
        if cnt <= 1:
            self._multi_count.pop(bn, None)
        else:
            self._multi_count[bn] = cnt - 1

        target_idx = min(entry.original_index, self._image_manager.total_count() - 1)
        if target_idx >= 0:
            self._image_manager.go_to(target_idx)

        self._status_label.setText(f"已撤销: {os.path.basename(entry.src_path)}")
        self._status_label.setStyleSheet("")
        self._save_progress()
        logger.info(f"Undo: {entry.dst_path}")

    # ── Slots: Filter ─────────────────────────────────────
    def _on_toggle_filter(self, checked: bool):
        if checked:
            self._filter_action.setText("∨ 仅未分类")
            self._apply_unclassified_filter()
        else:
            self._filter_action.setText("∧ 全部图片")
            self._image_manager.clear_filter()

    def _apply_unclassified_filter(self):
        excluded = self._entry_manager.get_classified_paths()
        self._image_manager.apply_filter(excluded)
        total = self._image_manager.total_count()
        self._status_label.setText(f"仅未分类: {total} 张")
        self._status_label.setStyleSheet("color: #89b4fa; font-weight: bold;")

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
        # 收集当前目录下所有图片的分类信息（来自 entry_manager 元数据）
        dir_prefix = self._image_manager.current_dir.replace("\\", "/") + "/"
        classified = {}
        for entry in self._entry_manager.read_all_entries():
            path = entry["image_path"].replace("\\", "/")
            if path.startswith(dir_prefix):
                bn = os.path.basename(path)
                if bn not in classified or entry["modified_at"] > classified[bn].get("at", ""):
                    classified[bn] = {
                        "label": entry.get("label", ""),
                        "by": entry.get("classified_by", ""),
                        "at": entry.get("modified_at", ""),
                    }
        self._progress.save_my(idx, flist, classified if classified else None)

    def _on_open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings.reload()
            self._crop_manager._output_dir = self._settings.target_dir
            self._progress.set_username(self._settings.get("general.username", ""))
            self._viewer._load_key_maps()
            self._rebuild_drag_zones()

    def _rebuild_drag_zones(self):
        from widgets.drag_zone import DragZone
        for z in self._drag_zones:
            z.setParent(None)
            z.deleteLater()
        self._drag_zones.clear()
        if not hasattr(self, '_zone_layout') or self._zone_layout is None:
            return
        while self._zone_layout.count() > 2:
            item = self._zone_layout.takeAt(self._zone_layout.count() - 2)
            if item and item.widget():
                item.widget().deleteLater()
        for mapping in self._settings.class_mappings:
            zone = DragZone(mapping)
            zone.image_dropped.connect(self._on_drag_classify)
            self._drag_zones.append(zone)
            self._zone_layout.insertWidget(self._zone_layout.count() - 1, zone)

    # ── Help / About ───────────────────────────────────────
    def _on_check_update(self):
        from core.updater import check_update
        check_update(self, silent=False)

    def _on_undo_list(self):
        username = self._settings.get("general.username", "")
        entries = self._undo_manager.list_by_user(username)
        if not entries:
            QMessageBox.information(self, "撤销列表", "没有可撤销的记录。")
            return

        from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("撤销列表 — 选择要撤销的分类")
        dlg.setMinimumSize(600, 400)
        dlg.resize(650, 450)
        dlg.setStyleSheet("QDialog{background-color:#1e1e2e;} QLabel{color:#cdd6f4;background:transparent;}")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        lbl = QLabel(f"标注人: {username}  共 {len(entries)} 条可撤销记录")
        lbl.setStyleSheet("font-size:14px;font-weight:bold;color:#89b4fa;")
        layout.addWidget(lbl)

        lst = QListWidget()
        lst.setStyleSheet("""
            QListWidget{background-color:#181825;color:#cdd6f4;border:1px solid #45475a;
                        border-radius:6px;font-size:13px;}
            QListWidget::item{padding:8px;border-radius:4px;}
            QListWidget::item:hover{background-color:#313244;}
            QListWidget::item:selected{background-color:#45475a;}
        """)
        # Build items
        from datetime import datetime
        for idx, e in entries:
            when = ""
            try:
                dt = datetime.fromisoformat(e.timestamp.replace("Z", "+00:00"))
                when = dt.strftime("%H:%M:%S")
            except Exception:
                pass
            text = f"[{when}] {os.path.basename(e.original_src)}  →  {e.label}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, idx)
            lst.addItem(item)
        layout.addWidget(lst)

        btns = QDialogButtonBox()
        undo_btn = btns.addButton("撤销选中", QDialogButtonBox.ActionRole)
        undo_btn.setStyleSheet("background-color:#45475a;color:#cdd6f4;padding:8px 22px;border-radius:6px;font-weight:bold;")
        undo_btn.clicked.connect(lambda: self._do_batch_undo(lst, dlg, username))
        close_btn = btns.addButton("关闭", QDialogButtonBox.RejectRole)
        layout.addWidget(btns)

        dlg.exec()

    def _do_batch_undo(self, lst, dlg, username):
        selected = []
        for item in lst.selectedItems():
            selected.append(item.data(Qt.UserRole))
        if not selected:
            QMessageBox.information(dlg, "提示", "请先选中要撤销的记录。")
            return

        # 从大到小排序，从栈中移除
        for idx in sorted(selected, reverse=True):
            entry = self._undo_manager.remove_at(idx)
            if entry is None:
                continue
            # 删除元数据文件
            if entry.dst_path and os.path.isfile(entry.dst_path):
                try:
                    os.remove(entry.dst_path)
                except OSError:
                    pass
            # 更新 classified_map
            bn = os.path.basename(entry.original_src)
            self._classified_map.pop(bn, None)
            cnt = self._multi_count.get(bn, 1)
            if cnt <= 1:
                self._multi_count.pop(bn, None)
            else:
                self._multi_count[bn] = cnt - 1

        count = len(selected)
        self._status_label.setText(f"已撤销 {count} 条分类记录")
        self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self._save_progress()
        dlg.accept()

    def _on_about(self):
        from core.updater import get_version
        QMessageBox.about(
            self,
            "关于 PowerLineCV",
            f"<h3>电力巡检图像数据集构建工具</h3>"
            f"<p>版本: v{get_version()}</p>"
            f"<p>面向计算机视觉数据集构建的桌面应用，<br>"
            f"用于巡检图像的快速筛选、分类、裁剪与标注。</p>"
            f"<p>GitHub: <a href='https://github.com/razorzc/hotkeyclassifier'>razorzc/hotkeyclassifier</a></p>"
            f"<p style='color:#a6adc8;font-size:11px;'>PySide6 + Python 3.12</p>"
        )
