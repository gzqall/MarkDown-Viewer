"""共享 pytest fixtures。

测试策略：
- 纯逻辑（utils/frontmatter/wordcount）不依赖 Qt GUI，直接测。
- 端到端冒烟（test_smoke）用 pytest-qt 的 qtbot，QT_QPA_PLATFORM=offscreen，
  并 mock 掉 QWebEngineView 的 setUrl/runJavaScript，只验证 Python 侧状态机，
  避免测试起真实 Chromium（CI 无显示环境跑不动）。
"""

import os
import sys
import importlib
import tempfile
from pathlib import Path

import pytest

# 确保导入根目录模块（window/bridge/utils 都在仓库根）
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 无显示环境：Qt 用离屏平台（必须在 QApplication 创建前设置）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# WebEngine 在 offscreen/无事件循环下析构易 segfault（Chromium sandbox/GPU
# 子进程清理）。关闭 sandbox 与 GPU 加速，并禁用子进程，让测试稳定。
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu --disable-software-rasterizer")

# QtWebEngine 硬要求：必须在 QCoreApplication 创建之前 import，
# 否则报 "QtWebEngineWidgets must be imported before a QCoreApplication
# instance is created"。pytest-qt 的 qtbot fixture 会抢先创建 QApplication，
# 所以这里在模块级（即任何 fixture 跑之前）先 import，满足该约束。
from PyQt6.QtWebEngineCore import QWebEngineSettings  # noqa: F401,E402
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401,E402

from utils import MD_EXTENSIONS  # noqa: E402


# ─── 文本 fixtures ─────────────────────────────────────────────────────

SAMPLE_MD = ROOT / "tests" / "sample.md"


@pytest.fixture
def sample_md_text():
    """tests/sample.md 的完整内容（7.8K, 374 行，含 mermaid/echarts/表格等）。"""
    return SAMPLE_MD.read_text(encoding="utf-8")


@pytest.fixture
def tmp_md(tmp_path):
    """创建一个临时 .md 文件，返回路径。可传 contents 参数。"""
    def _make(contents="# Hello\n\nsome text\n", name="t.md", encoding="utf-8"):
        p = tmp_path / name
        p.write_text(contents, encoding=encoding)
        return str(p)
    return _make


@pytest.fixture
def large_md(tmp_path):
    """生成一个大型 markdown 文件，用于性能/benchmark 测试。
    lines 控制行数，默认 20000 行（约 1MB+）。返回路径。"""
    def _make(lines=20000, name="large.md"):
        # 模拟真实 md：标题 + 段落 + 代码块 + 表格循环
        chunk = (
            "# Heading {i}\n\n"
            "This is paragraph {i} with some **bold** and *italic* and `code`.\n\n"
            "```python\n"
            "def f(x):\n    return x * 2\n"
            "```\n\n"
            "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |\n\n"
            "- item one\n- item two\n- item three\n\n"
        )
        # 每个 chunk 占 16 行，重复 ceil(lines/16) 次
        repeat = max(1, lines // 16)
        text = "".join(chunk.format(i=i) for i in range(repeat))
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        return str(p)
    return _make


# ─── Qt / MainWindow fixtures ───────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """会话级 QApplication（pytest-qt 默认提供 qapp，但显式声明
    便于在无 pytest-qt 时也有兜底）。"""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PyQt6 not installed")
    app = QApplication.instance() or QApplication(sys.argv)
    return app


@pytest.fixture
def main_window(qtbot, monkeypatch):
    """构造 MainWindow，但用 fake webview 替换真实 QWebEngineView ——
    这样测试**根本不起 Chromium**，既快又不会在析构时 segfault。
    只验证 Python 侧状态机。返回 (window, mock_js_calls)。
    """
    import window as window_mod

    # 在 MainWindow.__init__ 触碰 webview 之前，把 window 模块里的
    # QWebEngineView 替换成一个返回假对象的工厂。假 webview 的
    # page() 返回假 page，runJavaScript/setUrl/setHtml 全是 no-op 并
    # 记录调用，setMinimumWidth/setContextMenuPolicy 也吞掉。
    js_calls = []

    class _FakePage:
        def runJavaScript(self, code, *a, **k):
            js_calls.append(code)
        def setWebChannel(self, _ch):
            pass

    # 继承 QWidget，才能被 QSplitter.addWidget 接受；但 page()/runJavaScript
    # 用假实现，避免起真实 Chromium。
    from PyQt6.QtWidgets import QWidget
    class _FakeWebview(QWidget):
        def __init__(self, *_a, **_k):
            super().__init__()
            self._page = _FakePage()
        def page(self):
            return self._page
        def setUrl(self, *_a, **_k):
            pass
        def setHtml(self, *_a, **_k):
            pass

    # QWebEngineView 在 window.py 顶层 import，替换模块属性即可
    monkeypatch.setattr(window_mod, "QWebEngineView", _FakeWebview)

    win = window_mod.MainWindow()
    qtbot.addWidget(win)

    # 模拟前端就绪，让 _send 能真正下发内容
    win._ready = True

    yield win, js_calls

    win.close()
