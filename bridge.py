"""
QWebChannel bridge — exposes Python file operations to JavaScript

这是 Python ↔ JS 的桥接对象，经 QWebChannel 注册为 "bridge"。
JS 实际调用的方法：
  - onPageReady()        页面就绪信号（触发 window._page_ready）
  - openFileFromPath(p)  从 wiki 链接/拖放打开文件
  - openImage(url)       在系统默认查看器打开图片
  - showImageInFolder(url)  资源管理器中定位图片
  - saveImageAs(url)     另存图片
"""

import json
import os
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal


class FileBridge(QObject):
    """Bridge object exposed to JavaScript via QWebChannel."""

    # JS 完成通道连接 + 库加载后回调 onPageReady()，由 Python 监听以推送文件
    pageReady = pyqtSignal()

    def __init__(self, window=None, parent=None):
        super().__init__(parent)
        self._window = window

    # ─── JS signals readiness ──────────────────────────────────────────

    @pyqtSlot()
    def onPageReady(self):
        """Called by JS when QWebChannel is connected and libs loaded."""
        self.pageReady.emit()

    # ─── File open (wiki link / drop) ──────────────────────────────────

    @pyqtSlot(str)
    def openFileFromPath(self, filepath):
        """Called from JS when a file is dropped onto the webview.
        拖放是用户主动把文件拖进窗口——显式激活（切过去显示），
        不走 _open 的后台默认，避免拖了文件却看不到。"""
        if self._window:
            self._window._open(filepath, activate=True)

    @pyqtSlot(str)
    def openWikiLink(self, candidates_json):
        """从 JS 处理 [[wiki]] 链接：接收候选路径 JSON 数组，
        依次检查是否存在，打开第一个找到的。避免逐个尝试时弹
        一串 'File not found' toast。点 wiki 链接即导航，显式激活。"""
        if not self._window:
            return
        try:
            candidates = json.loads(candidates_json)
        except Exception:
            candidates = []
        for c in candidates:
            if os.path.isfile(c):
                self._window._open(c, activate=True)
                return
        self._window._toast("Wiki link target not found", 3000)

    # ─── Image operations (called from JS context-menu / lightbox) ────

    @pyqtSlot(str)
    def openImage(self, url):
        """Open the source image in the OS default viewer."""
        if self._window:
            self._window._open_image_externally(url)

    @pyqtSlot(str)
    def showImageInFolder(self, url):
        """Reveal the source image in the system file explorer."""
        if self._window:
            self._window._show_image_in_folder(url)

    @pyqtSlot(str)
    def saveImageAs(self, url):
        """Prompt for a destination and save the source image there."""
        if self._window:
            self._window._save_image_as(url)
