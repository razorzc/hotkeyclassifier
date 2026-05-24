import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

APP_VERSION = "1.0.0"
# 上次已知构建日期，发行版发布时间晚于此则认为有新版本
BUILD_DATE = "2026-05-17T00:00:00Z"
REPO_API = "https://api.github.com/repos/razorzc/hotkeyclassify/releases/latest"
DOWNLOAD_URL = "https://github.com/razorzc/hotkeyclassify/releases/latest"


def _fetch_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "PowerLineCV-Updater")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def check_update(parent) -> bool:
    """检查 GitHub 是否有比本地更新的版本。返回 True 表示弹出过更新提示。"""
    data = _fetch_json(REPO_API)
    if not data:
        return False

    published = data.get("published_at", "")
    tag = data.get("tag_name", "")
    body = (data.get("body") or "")[:200]

    try:
        remote_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        build_date = datetime.fromisoformat(BUILD_DATE.replace("Z", "+00:00"))
    except ValueError:
        return False

    if remote_date <= build_date:
        return False  # 没有新版本

    msg = f"GitHub 上有新版本可用\n\n版本: {tag}\n发布时间: {published[:10]}\n\n{body}"
    reply = QMessageBox.question(
        parent,
        "发现新版本",
        msg,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )
    if reply == QMessageBox.Yes:
        QDesktopServices.openUrl(QUrl(DOWNLOAD_URL))
        return True
    return False
