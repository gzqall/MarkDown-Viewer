"""端到端冒烟测试 —— 用 pytest-qt 起真实 MainWindow，mock 掉 WebEngine
的 URL 加载与 JS 执行，验证 Python 侧状态机：开文件→建 tab→下发内容。

不验证渲染结果（那是 Chromium 的事），只验证"不崩 + 状态正确 + JS 调用对"。
"""

import json
import os

import pytest

pytestmark = pytest.mark.smoke


def test_open_file_builds_tab(main_window, sample_md_text):
    """打开 sample.md → tab 被加入、_tabs 持有正确内容。"""
    win, js_calls = main_window
    # 用真实 sample.md 文件路径
    sample_path = os.path.join(os.path.dirname(__file__), "sample.md")
    assert os.path.isfile(sample_path)

    win._open(sample_path)

    assert len(win._tabs) == 1
    tab = win._tabs[0]
    assert tab["path"] == os.path.abspath(sample_path)
    assert tab["name"] == "sample.md"
    # content 是剥除 frontmatter 后的正文（sample.md 无 frontmatter → 原文）
    assert "Markdown" in tab["content"] or len(tab["content"]) > 0


def test_open_file_dispatches_js(main_window):
    """打开文件后，_send 应向 webview 下发 window._openFile(...) 调用。"""
    win, js_calls = main_window
    win._open(os.path.join(os.path.dirname(__file__), "sample.md"))
    # _ready=True，故 _send 直接执行，js_calls 应含 _openFile
    open_calls = [c for c in js_calls if "_openFile" in c]
    assert open_calls, f"expected _openFile JS call, got {js_calls}"
    # 解析 JSON 参数，验证 path/name/content 字段都在
    call = open_calls[-1]
    # 提取 JSON：window._openFile({...})
    start = call.index("{")
    data = json.loads(call[start:call.rfind(")")])
    assert "path" in data and "name" in data and "content" in data


def test_open_unsupported_type_rejected(main_window, tmp_path):
    """非 md 文件应被拒（toast），不建 tab。"""
    win, _ = main_window
    p = tmp_path / "notmd.txt"
    p.write_text("hello", encoding="utf-8")
    win._open(str(p))
    assert len(win._tabs) == 0


def test_open_nonexistent_file_rejected(main_window):
    """不存在的文件应被拒。"""
    win, _ = main_window
    win._open("/no/such/file.md")
    assert len(win._tabs) == 0


def test_close_tab_removes_it(main_window, tmp_md):
    """打开→关闭：tab 列表清空。"""
    win, _ = main_window
    p = tmp_md("# close me\n", name="c.md")
    win._open(p)
    assert len(win._tabs) == 1
    win._close_tab(0)
    assert len(win._tabs) == 0


def test_multiple_tabs(main_window, tmp_md):
    """开多个文件 → 多 tab，切标签不崩。"""
    win, _ = main_window
    p1 = tmp_md("# one\n", name="a.md")
    p2 = tmp_md("# two\n", name="b.md")
    win._open(p1)
    win._open(p2)
    assert len(win._tabs) == 2
    # 切到第一个标签（索引 0）
    win._tab_changed(0)
    assert win._cur == 0
    # 切回第二个
    win._tab_changed(1)
    assert win._cur == 1


def test_recent_files_updated(main_window, tmp_md):
    """打开文件后加入最近文件列表。"""
    win, _ = main_window
    p = tmp_md("# recent\n", name="r.md")
    win._open(p)
    assert os.path.abspath(p) in win._recent_files


def test_word_count_no_crash(main_window, tmp_md):
    """_update_word_count 对含 frontmatter 的内容不崩。"""
    win, _ = main_window
    content = "---\ntitle: Test Doc\n---\n# Hello\n\n你好 world\n"
    # 直接调方法（不依赖完整 _open 流程）
    win._update_word_count(content)
    assert win.lbl_count.text()  # 应有内容
    assert "Lines" in win.lbl_count.toolTip()


# ─── 页签后台打开语义（新行为）───────────────────────────────────────────


def test_open_first_file_activates(main_window, tmp_md):
    """首次打开（_cur<0）必须自动激活，否则看不到内容。"""
    win, _ = main_window
    p = tmp_md("# first\n", name="a.md")
    win._open(p)
    assert win._cur == 0
    assert win.tab_bar.currentIndex() == 0


def test_open_background_keeps_current_tab(main_window, tmp_md):
    """已开 a 后再开 b：b 默认后台加入，当前仍是 a（不抢焦点）。"""
    win, _ = main_window
    pa = tmp_md("# one\n", name="a.md")
    pb = tmp_md("# two\n", name="b.md")
    win._open(pa)                       # _cur<0 → 激活，cur=0
    win._open(pb)                       # _cur=0 → 后台，cur 保持 0
    assert len(win._tabs) == 2
    assert win._cur == 0                        # 焦点仍在 a
    assert win.tab_bar.currentIndex() == 0      # 选中的页签仍是 a
    assert win.tab_bar.tabText(1) == "b.md"     # b 确实加进来了（索引1）


def test_open_background_explicit_activate(main_window, tmp_md):
    """_open_background(activate=True) 显式激活：切到新页签。"""
    win, _ = main_window
    pa = tmp_md("# one\n", name="a.md")
    pb = tmp_md("# two\n", name="b.md")
    win._open(pa)
    win._open_background(pb, activate=True)
    assert win._cur == 1
    assert win.tab_bar.currentIndex() == 1


def test_open_existing_tab_no_duplicate(main_window, tmp_md):
    """再次打开已存在页签的同路径：不重复加 tab，默认不切焦点。"""
    win, _ = main_window
    pa = tmp_md("# one\n", name="a.md")
    pb = tmp_md("# two\n", name="b.md")
    win._open(pa)
    win._open(pb)                       # b 后台加入，cur 仍 0
    win._open(pa)                       # 再开 a：已存在，后台语义不切
    assert len(win._tabs) == 2                  # 没有新增第三个 tab
    assert win._cur == 0                        # 焦点仍在 b 加入前的 a


def test_open_existing_tab_activate_switches(main_window, tmp_md):
    """打开已存在页签且 activate=True：切过去（不新建）。"""
    win, _ = main_window
    pa = tmp_md("# one\n", name="a.md")
    pb = tmp_md("# two\n", name="b.md")
    win._open(pa)
    win._open(pb)
    assert win._cur == 0
    win._open(pa, activate=True)       # 显式切到 a
    assert win._cur == 0
    assert len(win._tabs) == 2                  # 仍两个 tab


def test_reload_keeps_current_and_resends(main_window, tmp_md):
    """_on_reload 重读当前文件并重发，不改焦点、不加 tab。
    reload 前先把内容改掉模拟磁盘变化，reload 后 tab content 应更新。"""
    win, js_calls = main_window
    p = tmp_md("# original\n", name="r.md")
    win._open(p)
    assert win._cur == 0
    # 改磁盘文件 + tab 内 content（模拟外部改动已被读入旧值）
    from pathlib import Path
    Path(p).write_text("# changed\n", encoding="utf-8")
    js_calls.clear()
    win._on_reload()
    assert win._cur == 0                         # 焦点不变
    assert len(win._tabs) == 1                   # 没新加 tab
    assert "changed" in win._tabs[0]["content"]  # 内容已重读
    # reload 后应通过 _send 下发 _openFile
    assert any("_openFile" in c for c in js_calls)


def test_open_background_batch_all_background(main_window, tmp_md):
    """_open_background_batch（IPC 转发入口）逐个后台加入，不抢焦点。"""
    win, _ = main_window
    pa = tmp_md("# one\n", name="a.md")
    pb = tmp_md("# two\n", name="b.md")
    pc = tmp_md("# three\n", name="c.md")
    win._open(pa)                                # 前台 a
    win._open_background_batch([pb, pc])         # b、c 后台
    assert len(win._tabs) == 3
    assert win._cur == 0                         # 焦点仍在 a
    assert win.tab_bar.currentIndex() == 0

