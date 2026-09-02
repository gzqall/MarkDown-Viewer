"""单实例 IPC —— 资源管理器双击 .md 时复用已开窗口而非开新窗口。

机制：QLocalServer / QLocalSocket（Qt 跨平台本地套接字）。
  • 启动时尝试连接 server name：连上 → 第二实例，把命令行文件路径
    发给主实例后退出；连不上 → 主实例，建 server 监听后续连接。
  • 主实例收到路径 JSON 后，逐个 _open_background 加入为后台页签
    （不抢当前页签焦点），符合用户期望的"双击第二个文件保持当前页"。
  • Server name 全局唯一即可——用户一般只想要一个主实例；多窗口
    仍由应用内 _new_window 支持。

异常 fallback：任何 IPC 错误都退化成"多实例模式"（各开各的），绝不
让单实例机制挡住正常启动。
"""

import json
import sys

from PyQt6.QtCore import QObject, pyqtSignal

# QtNetwork 在极少数精简发行版可能被裁掉，给一层兜底：找不到模块就
# 退化成一个永远走多实例的空壳，单实例机制失效但不影响程序启动。
try:
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    _HAS_QTNET = True
except ImportError:  # pragma: no cover - 罕见
    QLocalServer = None
    QLocalSocket = None
    _HAS_QTNET = False

SERVER_NAME = "MarkdownViewer-SingleInstance"


class SingleInstance(QObject):
    """单实例守门 + 文件转发。

    用法（main.py）::

        app = QApplication(...)
        si = SingleInstance(app)
        if si.is_secondary:
            if len(sys.argv) > 1: si.send([sys.argv[1]])
            sys.exit(0)
        si.files_received.connect(on_files)

    - is_secondary：True 表示自己是第二实例，应转发后退出。
    - files_received：主实例收到路径列表时发出。
    """

    files_received = pyqtSignal(list)

    def __init__(self, app, parent=None, server_name=None):
        super().__init__(parent)
        self._app = app
        self._server_name = server_name or SERVER_NAME
        self._server = None
        self._is_secondary = False
        self._pending_socket = None  # 第二实例：连上主实例的 socket
        if not _HAS_QTNET:  # 模块缺失 → 多实例模式
            self._is_secondary = False
            return
        self._init()

    @property
    def is_secondary(self) -> bool:
        return self._is_secondary

    # ─── 初始化：探测主实例 / 建服务 ──────────────────────────────────
    def _init(self):
        # 清理上次崩溃留下的残留锁（removeServer 在 Windows 上会删除
        # 命名管道 / unix domain socket 残留文件），否则 listen 会失败。
        QLocalServer.removeServer(self._server_name)

        # 先当客户端去连：连上说明已有主实例
        sock = QLocalSocket()
        sock.connectToServer(self._server_name)
        # waitForConnected 是同步的；给 200ms，主实例本机回环几乎瞬时
        if sock.waitForConnected(200):
            self._is_secondary = True
            self._pending_socket = sock  # 留着 send() 用
            return
        sock.close()

        # 没主实例 → 自己建 server
        self._server = QLocalServer(self)
        # server 监听要在事件循环里跑，newConnection 信号触发 _on_conn
        self._server.newConnection.connect(self._on_conn)
        if not self._server.listen(self._server_name):
            # listen 失败（权限/命名冲突等）→ 退化多实例，不挡启动
            print(
                f"[SingleInstance] listen failed: {self._server.errorString()}",
                file=sys.stderr,
            )
            self._server = None

    # ─── 第二实例：发送文件路径 ────────────────────────────────────────
    def send(self, paths):
        """第二实例把文件路径列表发给主实例。发完由调用方 sys.exit() 退出，
        不在此 close socket——避免主实例尚未读完时关管道导致 write failed。"""
        if not self._pending_socket:
            return
        data = json.dumps(list(paths), ensure_ascii=False).encode("utf-8")
        # 帧格式：4 字节大端长度 + JSON payload，便于主实例按帧切包
        n = len(data).to_bytes(4, "big")
        sock = self._pending_socket
        sock.write(n + data)
        sock.flush()
        sock.waitForBytesWritten(2000)

    # ─── 主实例：监听新连接 ────────────────────────────────────────────
    def _on_conn(self):
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        sock._buf = bytearray()
        sock._got_header = False
        sock._expected = 0
        sock.readyRead.connect(lambda s=sock: self._on_ready(s))
        sock.disconnected.connect(sock.deleteLater)
        # 万一连上后对方没发就走了，兜底读一次已有数据
        self._on_ready(sock)

    def _on_ready(self, sock):
        try:
            if sock.bytesAvailable():
                sock._buf += bytes(sock.readAll())
            while True:
                if not sock._got_header:
                    if len(sock._buf) < 4:
                        return
                    sock._expected = int.from_bytes(sock._buf[:4], "big")
                    sock._buf = sock._buf[4:]
                    sock._got_header = True
                if sock._got_header and len(sock._buf) >= sock._expected:
                    payload = bytes(sock._buf[:sock._expected])
                    sock._buf = sock._buf[sock._expected:]
                    sock._got_header = False
                    sock._expected = 0
                    try:
                        paths = json.loads(payload.decode("utf-8"))
                        if isinstance(paths, list):
                            self.files_received.emit([str(p) for p in paths])
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                else:
                    return
        except Exception:
            # 解析异常不影响后续连接，吞掉
            pass

    def close(self):
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self._server_name)
