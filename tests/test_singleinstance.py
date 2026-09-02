"""单实例 IPC 测试。

策略：用唯一 server name 起一对 SingleInstance（主+副），在 offscreen
QApplication 下跑事件循环，验证：
  • 主实例 is_secondary=False 并建 server；
  • 副实例 is_secondary=True；
  • 副实例 send(paths) 后，主实例 files_received 收到同样路径；
  • 帧分帧正确（一次发多条 / 多次发）。

不依赖真实 MainWindow——只测 IPC 层，快且无 Chromium。
"""

import os
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtNetwork import QLocalServer  # noqa: E402
from singleinstance import SingleInstance  # noqa: E402


pytestmark = pytest.mark.smoke


@pytest.fixture
def unique_server():
    """每个测试一个唯一 server name，避免串扰 + 残留。"""
    name = f"MarkdownViewer-Test-{uuid.uuid4().hex}"
    QLocalServer.removeServer(name)
    yield name
    QLocalServer.removeServer(name)


def test_primary_is_not_secondary(qapp, unique_server):
    """第一个实例应建 server、is_secondary=False。"""
    si = SingleInstance(qapp, server_name=unique_server)
    try:
        assert si.is_secondary is False
    finally:
        si.close()


def test_secondary_connects_to_primary(qapp, unique_server):
    """主实例存在时，第二个实例 is_secondary=True。"""
    primary = SingleInstance(qapp, server_name=unique_server)
    try:
        secondary = SingleInstance(qapp, server_name=unique_server)
        assert secondary.is_secondary is True
        # 副实例的 socket 会在 send()/close 时清理；这里显式关
        secondary.close()
    finally:
        primary.close()


def test_files_forwarded_from_secondary_to_primary(qapp, unique_server, qtbot):
    """副实例 send([paths]) → 主实例 files_received 收到同样 paths。"""
    primary = SingleInstance(qapp, server_name=unique_server)
    received = []
    primary.files_received.connect(lambda paths: received.append(paths))
    try:
        secondary = SingleInstance(qapp, server_name=unique_server)
        assert secondary.is_secondary is True

        paths = ["C:/foo/a.md", "D:/bar/b.md"]
        secondary.send(paths)

        # pump 事件循环让主实例的 readyRead/newConnection 触发
        qtbot.wait_until(lambda: len(received) > 0, timeout=2000)

        assert received, "主实例未收到转发文件"
        assert received[0] == paths
    finally:
        primary.close()


def test_multiple_sends_each_received(qapp, unique_server, qtbot):
    """多次 send 各自独立成帧，主实例收到多次 files_received。"""
    primary = SingleInstance(qapp, server_name=unique_server)
    received = []
    primary.files_received.connect(lambda paths: received.extend(paths))
    try:
        secondary = SingleInstance(qapp, server_name=unique_server)
        secondary.send(["x.md"])
        secondary.send(["y.md", "z.md"])
        qtbot.wait_until(lambda: len(received) >= 3, timeout=2000)
        assert received == ["x.md", "y.md", "z.md"]
    finally:
        primary.close()
