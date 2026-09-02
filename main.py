"""
Markdown Viewer — PyQt6 Desktop Application
全功能 Markdown 桌面查看器
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from window import MainWindow
from singleinstance import SingleInstance


def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Markdown Viewer")
    app.setOrganizationName("MarkdownViewer")

    # 单实例守门：资源管理器双击 .md 时，若已有窗口运行，第二个进程把
    # 命令行文件转发给主实例后退出（文件作为后台页签加入，不抢当前焦点）。
    si = SingleInstance(app)
    if si.is_secondary:
        # 已有主实例：转发命令行文件，然后退出本进程
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            si.send([os.path.abspath(sys.argv[1])])
        sys.exit(0)

    # Set app icon
    icon_path = os.path.join(os.path.dirname(__file__), "build_assets", "app.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    # Global stylesheet for Qt widgets (toolbar, etc.)
    app.setStyleSheet("""
        QMainWindow {
            background: #0f1a24;
        }
        QToolTip {
            background: #233545;
            color: #eaf2fb;
            border: 1px solid #2d4258;
            padding: 4px 8px;
            font-size: 12px;
        }
    """)

    window = MainWindow()
    window.show()

    # 主实例：收到第二进程转发的文件路径时，作为后台页签加入（不切焦点）
    si.files_received.connect(window._open_background_batch)

    # Handle command-line file argument（首次启动：命令行文件成为前台活动页签）
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window._open(sys.argv[1])  # _cur<0 → 自动激活，成为前台

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
