from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame
from PySide6.QtCore import Signal, Qt, QRectF, QPointF, QPoint
from PySide6.QtGui import (
    QPixmap, QWheelEvent, QMouseEvent, QKeyEvent, QPainter,
    QPen, QColor, QCursor,
)

from core.settings import AppSettings
import json
import os


class ImageViewer(QGraphicsView):
    navigate_requested = Signal(str)
    classify_requested = Signal(str, str)
    undo_requested = Signal()
    crop_save_requested = Signal(QRectF)
    crop_size_changed = Signal(str)
    zoom_changed = Signal(float)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self._crop_overlay = None
        self._current_crop_idx = 0

        self._panning = False
        self._space_held = False
        self._pan_start = QPoint()
        self._current_zoom = 1.0

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)

        self._load_key_maps()

    def _load_key_maps(self):
        self._key_to_class = {}
        self._key_to_crop = {}
        self._bindings_reverse = {}
        for mapping in self._settings.class_mappings:
            self._key_to_class[mapping.key.upper()] = mapping.label
        for cs in self._settings.crop_sizes:
            self._key_to_crop[cs.key] = cs
        bindings = self._settings.key_bindings
        for action, key_str in bindings.items():
            self._bindings_reverse[key_str] = action

    def set_image(self, pixmap: QPixmap):
        self._scene.clear()
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        if self._crop_overlay:
            from widgets.crop_overlay import CropOverlay
            if isinstance(self._crop_overlay, CropOverlay):
                self._scene.addItem(self._crop_overlay)
                self._crop_overlay.reset_position(self._scene.sceneRect())

        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._current_zoom = self.transform().m11()
        self.zoom_changed.emit(self._current_zoom * 100)

    def reset_view(self):
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._current_zoom = self.transform().m11()
        self.zoom_changed.emit(self._current_zoom * 100)

    def zoom_percent(self) -> float:
        return self._current_zoom * 100

    def set_crop_overlay(self, overlay):
        if self._crop_overlay:
            self._scene.removeItem(self._crop_overlay)
        self._crop_overlay = overlay
        if overlay:
            self._scene.addItem(overlay)
            overlay.reset_position(self._scene.sceneRect())

    def _get_crop_overlay_rect(self) -> QRectF:
        if self._crop_overlay:
            from widgets.crop_overlay import CropOverlay
            if isinstance(self._crop_overlay, CropOverlay):
                return self._crop_overlay.get_crop_rect()
        return QRectF()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1 + self._settings.get("display.zoom_step", 0.15)
            if delta < 0:
                factor = 1 / factor
            self._apply_zoom(factor, event.position())
            event.accept()
        else:
            # Without Ctrl: pass to parent for natural scrolling
            event.ignore()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and self._space_held
        ):
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and self._space_held
        ):
            self._panning = False
            self.setCursor(Qt.OpenHandCursor if self._space_held else Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()
        key_text = event.text().upper()

        # Space for panning
        if key == Qt.Key_Space:
            self._space_held = True
            self.setCursor(Qt.OpenHandCursor)
            return

        # Check classification shortcuts
        if key_text in self._key_to_class:
            label = self._key_to_class[key_text]
            self.classify_requested.emit(key_text, label)
            return

        # Check crop size shortcuts
        if key_text in self._key_to_crop:
            cs = self._key_to_crop[key_text]
            from widgets.crop_overlay import CropOverlay
            from PySide6.QtCore import QSize
            overlay = CropOverlay(QSize(cs.width, cs.height), self._settings)
            self.set_crop_overlay(overlay)
            self.crop_size_changed.emit(cs.name)
            return

        # Check key bindings
        binding_str = ""
        if modifiers & Qt.ControlModifier:
            binding_str += "Ctrl+"
        binding_str += event.text() if event.text() else self._key_to_string(key)
        action = self._bindings_reverse.get(binding_str, "")

        if action == "next":
            self.navigate_requested.emit("next")
        elif action == "prev":
            self.navigate_requested.emit("prev")
        elif action == "first":
            self.navigate_requested.emit("home")
        elif action == "last":
            self.navigate_requested.emit("end")
        elif action == "zoom_fit":
            self.reset_view()
        elif action == "zoom_100":
            self.resetTransform()
            self._current_zoom = 1.0
            self.zoom_changed.emit(100.0)
        elif action == "zoom_in":
            self._apply_zoom(1.15, self.viewport().rect().center())
        elif action == "zoom_out":
            self._apply_zoom(1 / 1.15, self.viewport().rect().center())
        elif action == "crop_save":
            rect = self._get_crop_overlay_rect()
            if not rect.isEmpty():
                self.crop_save_requested.emit(rect)
        elif action == "undo":
            self.undo_requested.emit()
        elif key == Qt.Key_Escape:
            self.set_crop_overlay(None)
        elif key == Qt.Key_Enter or key == Qt.Key_Return:
            rect = self._get_crop_overlay_rect()
            if not rect.isEmpty():
                self.crop_save_requested.emit(rect)
        elif key == Qt.Key_Left:
            self.navigate_requested.emit("prev")
        elif key == Qt.Key_Right:
            self.navigate_requested.emit("next")
        elif key == Qt.Key_Home:
            self.navigate_requested.emit("home")
        elif key == Qt.Key_End:
            self.navigate_requested.emit("end")
        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            self._apply_zoom(1.15, self.viewport().rect().center())
        elif key == Qt.Key_Minus:
            self._apply_zoom(1 / 1.15, self.viewport().rect().center())
        elif key == Qt.Key_0:
            self.reset_view()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space:
            self._space_held = False
            self.setCursor(Qt.ArrowCursor)
            return
        super().keyReleaseEvent(event)

    def _apply_zoom(self, factor: float, anchor):
        max_z = self._settings.get("display.max_zoom", 10.0)
        min_z = self._settings.get("display.min_zoom", 0.05)
        new_zoom = self._current_zoom * factor
        if new_zoom > max_z or new_zoom < min_z:
            return
        self._current_zoom = new_zoom
        self.scale(factor, factor)
        self.zoom_changed.emit(self._current_zoom * 100)

    def _key_to_string(self, key: int) -> str:
        key_map = {
            Qt.Key_Left: "Left", Qt.Key_Right: "Right",
            Qt.Key_Up: "Up", Qt.Key_Down: "Down",
            Qt.Key_Home: "Home", Qt.Key_End: "End",
            Qt.Key_Return: "Return", Qt.Key_Enter: "Enter",
            Qt.Key_Plus: "Plus", Qt.Key_Minus: "Minus",
            Qt.Key_Space: "Space",
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3",
            Qt.Key_F4: "F4", Qt.Key_F5: "F5", Qt.Key_F6: "F6",
            Qt.Key_F7: "F7", Qt.Key_F8: "F8", Qt.Key_F9: "F9",
            Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
        }
        return key_map.get(key, "")
