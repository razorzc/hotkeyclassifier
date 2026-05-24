import sys
import os
import signal
import shutil

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from core.settings import AppSettings
from core.image_manager import ImageManager
from ui.main_window import MainWindow
from utils.logger import setup_logger


def _get_writable_dir():
    """返回可写入的配置目录。打包后为 exe 同目录，源码运行时为项目根目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _resolve_config(writable_dir: str) -> str:
    """确保可写入的 config 目录存在，首次运行从内置资源复制。"""
    user_config_dir = os.path.join(writable_dir, "config")
    user_config = os.path.join(user_config_dir, "config.json")
    if not os.path.exists(user_config):
        os.makedirs(user_config_dir, exist_ok=True)
        # 尝试从内置资源复制
        if getattr(sys, 'frozen', False):
            bundled = os.path.join(sys._MEIPASS, "config", "config.json")
        else:
            bundled = os.path.join(os.path.dirname(__file__), "config", "config.json")
        if os.path.exists(bundled):
            shutil.copy2(bundled, user_config)
        # 同样复制主题文件
        if getattr(sys, 'frozen', False):
            bundled_qss = os.path.join(sys._MEIPASS, "config", "dark_theme.qss")
        else:
            bundled_qss = os.path.join(os.path.dirname(__file__), "config", "dark_theme.qss")
        user_qss = os.path.join(user_config_dir, "dark_theme.qss")
        if os.path.exists(bundled_qss) and not os.path.exists(user_qss):
            shutil.copy2(bundled_qss, user_qss)
    return user_config


def main():
    writable_dir = _get_writable_dir()
    config_path = _resolve_config(writable_dir)
    settings = AppSettings(config_path)

    log_dir = settings.get("paths.log_dir", "logs")
    log_file = settings.get("paths.log_file", "logs/app.log")
    setup_logger(log_dir, log_file)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Power Line CV Dataset Builder")
    app.setOrganizationName("PowerLineCV")

    image_manager = ImageManager(settings)
    window = MainWindow(settings, image_manager)
    window.show()

    def _check_update():
        from core.updater import check_update
        check_update(window)

    QTimer.singleShot(1500, _check_update)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
