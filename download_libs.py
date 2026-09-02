"""
Markdown Viewer — 本地依赖库下载工具
从多个 CDN 源下载 JS 库到 renderer/vendor/ 目录，
并下载各库 LICENSE 文本到 renderer/vendor/LICENSES/，
确保分发包满足 MIT/BSD/Apache 等许可证"保留版权声明"的要求。
"""

import sys
import re
import urllib.request
import urllib.error
from pathlib import Path

VENDOR_DIR = Path(__file__).parent / "renderer" / "vendor"
LICENSES_DIR = VENDOR_DIR / "LICENSES"

# 要下载的 JS 库列表
# 每项 = (保存文件名, [JS 的 CDN 路径], [LICENSE 的 CDN 路径])
# LICENSE 路径为空 → 该库许可证在 THIRD_PARTY_LICENSES.md 静态声明，不从 CDN 拉。
LIBS = [
    # markdown-it 核心 + 插件
    ("markdown-it.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js",
        "https://unpkg.com/markdown-it@14.1.0/dist/markdown-it.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it/14.1.0/files/dist/markdown-it.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/LICENSE",
        "https://unpkg.com/markdown-it@14.1.0/LICENSE",
    ]),
    ("markdown-it-emoji.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-emoji@3.0.0/dist/markdown-it-emoji.min.js",
        "https://unpkg.com/markdown-it-emoji@3.0.0/dist/markdown-it-emoji.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-emoji/3.0.0/files/dist/markdown-it-emoji.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-emoji@3.0.0/LICENSE",
        "https://unpkg.com/markdown-it-emoji@3.0.0/LICENSE",
    ]),
    ("markdown-it-sub.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-sub@2.0.0/dist/markdown-it-sub.min.js",
        "https://unpkg.com/markdown-it-sub@2.0.0/dist/markdown-it-sub.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-sub@2.0.0/files/dist/markdown-it-sub.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-sub@2.0.0/LICENSE",
        "https://unpkg.com/markdown-it-sub@2.0.0/LICENSE",
    ]),
    ("markdown-it-sup.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-sup@2.0.0/dist/markdown-it-sup.min.js",
        "https://unpkg.com/markdown-it-sup@2.0.0/dist/markdown-it-sup.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-sup@2.0.0/files/dist/markdown-it-sup.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-sup@2.0.0/LICENSE",
        "https://unpkg.com/markdown-it-sup@2.0.0/LICENSE",
    ]),
    ("markdown-it-mark.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-mark@4.0.0/dist/markdown-it-mark.min.js",
        "https://unpkg.com/markdown-it-mark@4.0.0/dist/markdown-it-mark.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-mark/4.0.0/files/dist/markdown-it-mark.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-mark@4.0.0/LICENSE",
        "https://unpkg.com/markdown-it-mark@4.0.0/LICENSE",
    ]),
    ("markdown-it-footnote.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-footnote@4.0.0/dist/markdown-it-footnote.min.js",
        "https://unpkg.com/markdown-it-footnote@4.0.0/dist/markdown-it-footnote.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-footnote@4.0.0/files/dist/markdown-it-footnote.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-footnote@4.0.0/LICENSE",
        "https://unpkg.com/markdown-it-footnote@4.0.0/LICENSE",
    ]),
    ("markdown-it-task-lists.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-task-lists@2.1.1/dist/markdown-it-task-lists.min.js",
        "https://unpkg.com/markdown-it-task-lists@2.1.1/dist/markdown-it-task-lists.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-task-lists/2.1.1/files/dist/markdown-it-task-lists.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-task-lists@2.1.1/LICENSE",
        "https://unpkg.com/markdown-it-task-lists@2.1.1/LICENSE",
    ]),
    ("markdown-it-container.min.js", [
        "https://cdn.jsdelivr.net/npm/markdown-it-container@4.0.0/dist/markdown-it-container.min.js",
        "https://unpkg.com/markdown-it-container@4.0.0/dist/markdown-it-container.min.js",
        "https://cdn.npmmirror.com/packages/markdown-it-container/4.0.0/files/dist/markdown-it-container.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/markdown-it-container@4.0.0/LICENSE",
        "https://unpkg.com/markdown-it-container@4.0.0/LICENSE",
    ]),
    # 代码高亮 (cdnjs 在国内可用)
    ("highlight.min.js", [
        "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.0/highlight.min.js",
        "https://cdn.jsdelivr.net/npm/highlight.js@11.11.0/build/highlight.min.js",
        "https://unpkg.com/highlight.js@11.11.0/build/highlight.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/highlight.js@11.11.0/LICENSE",
        "https://unpkg.com/highlight.js@11.11.0/LICENSE",
    ]),
    # Mermaid 图表
    ("mermaid.min.js", [
        "https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.min.js",
        "https://unpkg.com/mermaid@11.6.0/dist/mermaid.min.js",
        "https://cdn.npmmirror.com/packages/mermaid/11.6.0/files/dist/mermaid.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/mermaid@11.6.0/LICENSE",
        "https://unpkg.com/mermaid@11.6.0/LICENSE",
    ]),
    # ECharts 图表
    ("echarts.min.js", [
        "https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js",
        "https://unpkg.com/echarts@5.6.0/dist/echarts.min.js",
        "https://cdn.npmmirror.com/packages/echarts/5.6.0/files/dist/echarts.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/echarts@5.6.0/LICENSE",
        "https://unpkg.com/echarts@5.6.0/LICENSE",
    ]),
    # QWebChannel bridge (PyQt6 不自带, 需单独下载；Qt WebChannel 适用 LGPL-3.0-only)
    ("qwebchannel.js", [
        "https://raw.githubusercontent.com/qt/qtwebchannel/6.7.0/src/webchannel/qwebchannel.js",
        "https://code.qt.io/cgit/qt/qtwebchannel.git/plain/src/webchannel/qwebchannel.js",
    ], [
        "https://raw.githubusercontent.com/qt/qtwebchannel/6.7.0/LICENSES/LGPL-3.0-only.txt",
    ]),
    # KaTeX 数学公式渲染 (CSS + JS)
    ("katex.min.css", [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css",
        "https://unpkg.com/katex@0.16.21/dist/katex.min.css",
    ], [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/LICENSE",
        "https://unpkg.com/katex@0.16.21/LICENSE",
    ]),
    ("katex.min.js", [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js",
        "https://unpkg.com/katex@0.16.21/dist/katex.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/LICENSE",
        "https://unpkg.com/katex@0.16.21/LICENSE",
    ]),
    ("katex-auto-render.min.js", [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/contrib/auto-render.min.js",
        "https://unpkg.com/katex@0.16.21/dist/contrib/auto-render.min.js",
    ], [
        "https://cdn.jsdelivr.net/npm/katex@0.16.21/LICENSE",
        "https://unpkg.com/katex@0.16.21/LICENSE",
    ]),
]

# KaTeX 版本（用于拼接字体 CDN 路径）
KATEX_VERSION = "0.16.21"
# KaTeX 字体来源（CSS 里 @font-face 引用 fonts/KaTeX_*.woff2 等）
KATEX_FONT_URLS = [
    "https://cdn.jsdelivr.net/npm/katex@{ver}/dist/fonts/{name}",
    "https://unpkg.com/katex@{ver}/dist/fonts/{name}",
]


def lib_slug(name):
    """从保存文件名提取库短名，用作 LICENSE 文件名。
    markdown-it.min.js → markdown-it；highlight.min.js → highlight；
    katex.min.css → katex；qwebchannel.js → qwebchannel。"""
    return re.sub(r"\.(min\.)?(js|css)$", "", name)


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

            # 保存文件（LICENSES 子目录需先创建）
            dest.parent.mkdir(parents=True, exist_ok=True)
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

    # 创建目录
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    LICENSES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Target] {VENDOR_DIR}")
    print(f"[Licenses] {LICENSES_DIR}")
    print()

    # 下载每个库 + 对应 LICENSE
    total = len(LIBS)
    success = 0
    failed = []
    lic_ok = 0
    lic_total = 0

    for name, urls, license_urls in LIBS:
        # 1) JS 库本体
        dest = VENDOR_DIR / name
        if download_file(name, urls, dest):
            success += 1
        else:
            failed.append(name)
        print()

        # 2) LICENSE 文本（失败不阻断构建，只提示）
        if license_urls:
            lic_total += 1
            slug = lib_slug(name)
            lic_dest = LICENSES_DIR / f"{slug}.txt"
            if download_file(f"{slug} LICENSE", license_urls, lic_dest):
                lic_ok += 1
            else:
                print(f"  [Note] {slug} 的 LICENSE 未能下载，请在 THIRD_PARTY_LICENSES.md 查看声明")
            print()

    # 报告结果
    print("=" * 50)
    print(f"[Result] 库: {success}/{total} 成功")
    print(f"[Licenses] 许可证: {lic_ok}/{lic_total} 成功")
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
