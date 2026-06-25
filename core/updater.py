"""启动时检查 GitHub 是否有新版本，以及手动检查更新。"""
import json
import urllib.request
import urllib.error

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

APP_VERSION = "1.0.3"
RELEASES_API = "https://api.github.com/repos/razorzc/hotkeyclassifier/releases"
DOWNLOAD_URL = "https://github.com/razorzc/hotkeyclassifier/releases/tag/"


def _parse_version(tag: str):
    """从 tag 中提取版本元组，如 v1.0.3 -> (1, 0, 3)。nightly 返回 None。"""
    v = tag.lstrip("vV")
    if v == "nightly":
        return None
    try:
        parts = [int(x) for x in v.split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except (ValueError, IndexError):
        return None


def _fetch_json(url: str) -> list | None:
    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "PowerLineCV-Updater")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def check_update(parent, silent: bool = False) -> bool:
    """检查远程版本。silent=True 时无更新不弹窗。返回 True 表示有新版本。"""
    current_ver = _parse_version(APP_VERSION)
    if current_ver is None:
        # nightly build — skip auto-check, allow manual
        if silent:
            return False

    releases = _fetch_json(RELEASES_API + "?per_page=10")
    if not releases:
        if not silent:
            QMessageBox.information(parent, "检查更新", "无法连接 GitHub，请检查网络。")
        return False

    latest_tag = ""
    latest_ver = None
    for rel in releases:
        tag = rel.get("tag_name", "")
        ver = _parse_version(tag)
        if ver is None:
            continue
        if latest_ver is None or ver > latest_ver:
            latest_ver = ver
            latest_tag = tag

    if latest_ver is None:
        if not silent:
            QMessageBox.information(parent, "检查更新", "未找到正式版本。")
        return False

    if current_ver is not None and latest_ver <= current_ver:
        if not silent:
            QMessageBox.information(
                parent, "检查更新",
                f"当前已是最新版本 v{APP_VERSION}。\nGitHub 最新: {latest_tag}"
            )
        return False

    msg = f"GitHub 上有新版本可用\n\n当前版本: v{APP_VERSION}\n最新版本: {latest_tag}\n\n是否前往下载？"
    reply = QMessageBox.question(
        parent, "发现新版本", msg,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
    )
    if reply == QMessageBox.Yes:
        QDesktopServices.openUrl(QUrl(DOWNLOAD_URL + latest_tag))
        return True
    return False


def get_version() -> str:
    return APP_VERSION
