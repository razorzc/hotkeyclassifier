from PySide6.QtWidgets import QGraphicsRectItem
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPen, QColor, QBrush

from core.settings import AppSettings


class CropOverlay(QGraphicsRectItem):
    def __init__(self, size: QSize, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._size = size
        self._settings = settings

        color = QColor(settings.get("display.crop_overlay_color", "#00FF88"))
        pen = QPen(color, settings.get("display.crop_overlay_width", 2))
        pen.setStyle(Qt.SolidLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        fill = QColor(color)
        fill.setAlpha(30)
        self.setBrush(QBrush(fill))

        self.setRect(0, 0, size.width(), size.height())
        self.setZValue(100)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setCursor(Qt.SizeAllCursor)

    def set_crop_size(self, size: QSize):
        self._size = size
        self.setRect(0, 0, size.width(), size.height())

    def reset_position(self, scene_rect: QRectF):
        x = scene_rect.center().x() - self._size.width() / 2
        y = scene_rect.center().y() - self._size.height() / 2
        self.setPos(x, y)

    def get_crop_rect(self) -> QRectF:
        return QRectF(self.pos(), self._size.toSizeF())

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemPositionChange:
            scene_rect = self.scene().sceneRect()
            new_pos = QPointF(value)
            # Constrain within scene bounds
            new_pos.setX(max(scene_rect.left(), min(new_pos.x(), scene_rect.right() - self._size.width())))
            new_pos.setY(max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom() - self._size.height())))
            return new_pos
        return super().itemChange(change, value)
