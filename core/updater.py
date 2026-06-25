"""启动时检查 GitHub 是否有新版本。"""
import json
import urllib.request
import urllib.error

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

APP_VERSION = "1.0.3"
# 检查所有 release（不限于 latest）
RELEASES_API = "https://api.github.com/repos/razorzc/hotkeyclassify/releases"
DOWNLOAD_URL = "https://github.com/razorzc/hotkeyclassify/releases/tag/"


def _parse_version(tag: str):
    """从 tag 中提取版本元组，如 v1.0.3 -> (1, 0, 3)。"""
    v = tag.lstrip("vV")
    try:
        parts = [int(x) for x in v.split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except (ValueError, IndexError):
        return (0, 0, 0)


def _fetch_json(url: str) -> list | None:
    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "PowerLineCV-Updater")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def check_update(parent) -> bool:
    """检查远程是否有比本地版本号更高的版本。"""
    current_ver = _parse_version(APP_VERSION)

    releases = _fetch_json(RELEASES_API + "?per_page=10")
    if not releases:
        return False

    latest_tag = ""
    latest_ver = (0, 0, 0)
    for rel in releases:
        tag = rel.get("tag_name", "")
        ver = _parse_version(tag)
        if ver > latest_ver:
            latest_ver = ver
            latest_tag = tag

    if latest_ver <= current_ver:
        return False

    msg = f"GitHub 上有新版本可用\n\n当前版本: v{APP_VERSION}\n最新版本: {latest_tag}\n\n是否前往下载？"
    reply = QMessageBox.question(
        parent,
        "发现新版本",
        msg,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )
    if reply == QMessageBox.Yes:
        QDesktopServices.openUrl(QUrl(DOWNLOAD_URL + latest_tag))
        return True
    return False
