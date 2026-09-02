"""
Markdown Viewer — 本地依赖库下载工具
从多个 CDN 源下载 JS 库到 renderer/vendor/ 目录
"""

import sys
import urllib.request
import urllib.error
from pathlib import Path

VENDOR_DIR = Path(__file__).parent / "renderer" / "vendor"

# 要下载的 JS 库列表
# (保存文件名, CDN 路径列表)
LIBS = [
    # markdown-it 核心 + 插件
    ("markdown-it.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js",
        "https://unpkg.com/markdown-it@14.1.0/dist/markdown-it.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it/14.1.0/files/dist/markdown-it.min.js",
    ]),
    ("markdown-it-emoji.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-emoji@3.0.0/dist/markdown-it-emoji.min.js",
        "https://unpkg.com/markdown-it-emoji@3.0.0/dist/markdown-it-emoji.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-emoji/3.0.0/files/dist/markdown-it-emoji.min.js",
    ]),
    ("markdown-it-sub.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-sub@2.0.0/dist/markdown-it-sub.min.js",
        "https://unpkg.com/markdown-it-sub@2.0.0/dist/markdown-it-sub.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-sub/2.0.0/files/dist/markdown-it-sub.min.js",
    ]),
    ("markdown-it-sup.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-sup@2.0.0/dist/markdown-it-sup.min.js",
        "https://unpkg.com/markdown-it-sup@2.0.0/dist/markdown-it-sup.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-sup/2.0.0/files/dist/markdown-it-sup.min.js",
    ]),
    ("markdown-it-mark.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-mark@4.0.0/dist/markdown-it-mark.min.js",
        "https://unpkg.com/markdown-it-mark@4.0.0/dist/markdown-it-mark.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-mark/4.0.0/files/dist/markdown-it-mark.min.js",
    ]),
    ("markdown-it-footnote.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-footnote@4.0.0/dist/markdown-it-footnote.min.js",
        "https://unpkg.com/markdown-it-footnote@4.0.0/dist/markdown-it-footnote.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-footnote/4.0.0/files/dist/markdown-it-footnote.min.js",
    ]),
    ("markdown-it-task-lists.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-task-lists@2.1.1/dist/markdown-it-task-lists.min.js",
        "https://unpkg.com/markdown-it-task-lists@2.1.1/dist/markdown-it-task-lists.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-task-lists/2.1.1/files/dist/markdown-it-task-lists.min.js",
    ]),
    ("markdown-it-container.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-container@4.0.0/dist/markdown-it-container.min.js",
        "https://unpkg.com/markdown-it-container@4.0.0/dist/markdown-it-container.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-container/4.0.0/files/dist/markdown-it-container.min.js",
    ]),
    # 代码高亮 (cdnjs 在国内可用)
    ("highlight.min.js", [
        "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.0/highlight.min.js",
        "https://cdn.jsdelivr.net/npm/highlight.js@11.11.0/build/highlight.min.js",
        "https://unpkg.com/highlight.js@11.11.0/build/highlight.min.js",
    ]),
    # Mermaid 图表
    ("mermaid.min.js", [
        "https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.min.js",
        "https://unpkg.com/mermaid@11.6.0/dist/mermaid.min.js",
        "https://cdn.npmmirror.com/packages/mermaid/11.6.0/files/dist/mermaid.min.js",
    ]),
    # ECharts 图表
    ("echarts.min.js", [
        "https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js",
        "https://unpkg.com/echarts@5.6.0/dist/echarts.min.js",
        "https://cdn.npmmirror.com/packages/echarts/5.6.0/files/dist/echarts.min.js",
    ]),
    # QWebChannel bridge (PyQt6 不自带, 需单独下载)
    ("qwebchannel.js", [
        "https://raw.githubusercontent.com/qt/qtwebchannel/6.7.0/src/webchannel/qwebchannel.js",
        "https://code.qt.io/cgit/qt/qtwebchannel.git/plain/src/webchannel/qwebchannel.js",
    ]),
    # KaTeX 数学公式渲染 (CSS + JS)
    ("katex.min.css", [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css",
        "https://unpkg.com/katex@0.16.21/dist/katex.min.css",
    ]),
    ("katex.min.js", [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js",
        "https://unpkg.com/katex@0.16.21/dist/katex.min.js",
    ]),
    ("katex-auto-render.min.js", [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/contrib/auto-render.min.js",
        "https://unpkg.com/katex@0.16.21/dist/contrib/auto-render.min.js",
    ]),
]

# KaTeX 版本（用于拼接字体 CDN 路径）
KATEX_VERSION = "0.16.21"
# KaTeX 字体来源（CSS 里 @font-face 引用 fonts/KaTeX_*.woff2 等）
KATEX_FONT_URLS = [
    "https://cdn.jsdelivr.net/npm/katex@{ver}/dist/fonts/{name}",
    "https://unpkg.com/katex@{ver}/dist/fonts/{name}",
]


def download_file(name, urls, dest):
    """从多个 URL 尝试下载文件，返回是否成功"""
    last_error = None
    for url in urls:
        try:
            print(f"  [Downloading] {name}")
            print(f"      from: {url}")

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()

            if not data or len(data) < 100:
                print(f"  [Warning] file too small ({len(data)} bytes), try next source")
                continue

            # 保存文件
            with open(dest, "wb") as f:
                f.write(data)

            size_kb = len(data) / 1024
            print(f"  [OK] {name} ({size_kb:.1f} KB)")
            return True

        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            print(f"  [Failed] HTTP {e.code}, try next source")
        except urllib.error.URLError as e:
            last_error = f"URL Error: {e.reason}"
            print(f"  [Failed] {e.reason}, try next source")
        except Exception as e:
            last_error = str(e)
            print(f"  [Failed] {e}, try next source")

    print(f"  [Failed] {name} - all CDN sources failed! Last error: {last_error}")
    return False


def download_katex_fonts():
    """扫描已下载的 katex.min.css，下载其中 @font-face 引用的字体文件
    到 vendor/fonts/。CSS 引用相对路径 fonts/xxx.woff2，必须配套否则
    数学公式会掉字/符号错位。自动解析 CSS 而非硬编码清单，
    这样升级 KaTeX 版本后字体自动跟随。"""
    import re
    css_path = VENDOR_DIR / "katex.min.css"
    if not css_path.exists():
        print("[KaTeX fonts] katex.min.css not found, skipping font download")
        return 0, 0

    css = css_path.read_text(encoding="utf-8", errors="replace")
    names = sorted(set(re.findall(r"url\((?:fonts/)?(KaTeX_[A-Za-z0-9_-]+\.(?:woff2|woff|ttf))\)", css)))
    if not names:
        print("[KaTeX fonts] no @font-face references found in CSS")
        return 0, 0

    fonts_dir = VENDOR_DIR / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    print(f"[KaTeX fonts] {len(names)} font files referenced, downloading to {fonts_dir}")
    success = 0
    for name in names:
        dest = fonts_dir / name
        if dest.exists() and dest.stat().st_size > 100:
            # 已存在且非空，跳过
            success += 1
            continue
        urls = [tpl.format(ver=KATEX_VERSION, name=name) for tpl in KATEX_FONT_URLS]
        if download_file(name, urls, dest):
            success += 1
    return success, len(names)


def main():
    print("=== Markdown Viewer - 依赖库下载工具 ===")
    print()

    # 创建 vendor 目录
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Target] {VENDOR_DIR}")
    print()

    # 下载每个库
    total = len(LIBS)
    success = 0
    failed = []

    for name, urls in LIBS:
        dest = VENDOR_DIR / name
        if download_file(name, urls, dest):
            success += 1
        else:
            failed.append(name)
        print()

    # 报告结果
    print("=" * 50)
    print(f"[Result] {success}/{total} libraries succeeded")
    if failed:
        print(f"[Failed]")
        for f in failed:
            print(f"   - {f}")
        print()
        print("[Tip] Try using a proxy or VPN, then re-run")
        sys.exit(1)

    # 下载 KaTeX 字体（katex.min.css 引用的 @font-face 文件）
    print()
    print("=== KaTeX fonts ===")
    f_ok, f_total = download_katex_fonts()
    if f_total and f_ok < f_total:
        print(f"[Warning] only {f_ok}/{f_total} fonts downloaded; math may render with fallback fonts")

    print()
    print("All libraries downloaded successfully!")
    print("Run: python main.py")
    print()


if __name__ == "__main__":
    main()
