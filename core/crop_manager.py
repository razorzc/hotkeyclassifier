import os

from PySide6.QtCore import QObject, Signal, QRectF
from PySide6.QtGui import QPixmap

from utils.logger import get_logger


class CropManager(QObject):
    crop_saved = Signal(str)
    crop_error = Signal(str, str)

    def __init__(self, output_dir: str = "crops", parent=None):
        super().__init__(parent)
        self._output_dir = output_dir
        self._seq: dict[str, int] = {}

    def save_crop(
        self, pixmap: QPixmap, rect: QRectF, src_path: str,
        size_name: str = "", label: str = ""
    ) -> str:
        logger = get_logger()
        if rect.isEmpty():
            self.crop_error.emit("", "Empty crop rect")
            return ""

        # Map scene coords to pixmap coords (rect is in scene coords)
        x = max(0, int(rect.x()))
        y = max(0, int(rect.y()))
        w = min(int(rect.width()), pixmap.width() - x)
        h = min(int(rect.height()), pixmap.height() - y)

        if w <= 0 or h <= 0:
            self.crop_error.emit("", "Crop region outside image bounds")
            return ""

        cropped = pixmap.copy(x, y, w, h)

        if label:
            out_dir = os.path.join(self._output_dir, label)
        else:
            out_dir = self._output_dir
        os.makedirs(out_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(src_path))[0]
        suffix = f"_{size_name}" if size_name else ""

        key = f"{base_name}{suffix}"
        seq = self._seq.get(key, 0) + 1
        self._seq[key] = seq

        filename = f"{base_name}{suffix}_{seq:03d}.png"
        out_path = os.path.join(out_dir, filename)

        if cropped.save(out_path, "PNG"):
            logger.info(f"Crop saved: {out_path}")
            self.crop_saved.emit(out_path)
            return out_path
        else:
            self.crop_error.emit(out_path, "Failed to save crop")
            return ""
