# Markdown Viewer

一款基于 PyQt6 + WebEngine 的 Windows 桌面 Markdown 查看器。支持多页签、实时预览、语法高亮、Mermaid / ECharts 图表、KaTeX 数学公式、文件树、目录拖放、导出 PDF / HTML，以及 `.md` 文件关联。深色 / 浅色双主题。

> 适用场景：本地浏览 Markdown 文档，告别"用编辑器看排版"的不便。
![Uploading PixPin_2026-09-02_14-17-16.png…]()


## ✨ 功能特性

- **多页签浏览** — 同时打开多个文件，后台打开不抢焦点；双击 `.md` 时若已有窗口运行，新进程会转发文件给主实例后自动退出（单实例 IPC）。
- **实时渲染** — 基于 markdown-it，支持 GFM、表格、任务列表、脚注、上下标、高亮标记、emoji、自定义容器。
- **代码高亮** — highlight.js，自动识别语言。
- **图表** — Mermaid 流程图 / 时序图 / 甘特图，ECharts 数据图表。
- **数学公式** — KaTeX 渲染，含配套字体。
- **文件树面板** — 打开所在目录，侧边栏快速切换文件。
- **拖放打开** — 拖文件 / 文件夹到窗口即可打开。
- **导出** — 打印为 PDF，或导出为带样式的独立 HTML。
- **统计** — 字数 / 词数 / 阅读时长。
- **主题** — 深色 / 浅色一键切换，配置持久化到 `%APPDATA%`。
- **文件关联** — 安装后关联 `.md` / `.markdown` / `.mdx`，资源管理器双击即用本程序打开。

## 📦 安装

### 方式一：安装包（推荐普通用户）

到 [Releases](https://github.com/gzqall/MarkDown-Viewer/releases) 下载 `MarkdownViewer-Setup.exe`，双击安装即可。安装程序会自动关联 `.md` 等扩展名。

### 方式二：从源码运行

需要 Python ≥ 3.10。

```bash
git clone https://github.com/gzqall/MarkDown-Viewer.git
cd MarkDown-Viewer

# 安装 Python 依赖
pip install -r requirements.txt

# 下载前端第三方库（markdown-it / mermaid / echarts / katex / highlight 等）
python download_libs.py

# 运行
python main.py
```

> `download_libs.py` 会从 jsdelivr / unpkg / npmmirror 等 CDN 拉取 JS 库到 `renderer/vendor/`。国内网络若失败，可设置代理后重试。

## 🔨 构建 Windows 安装包

需要本地装有 [NSIS](https://nsis.sourceforge.io/)。

```bash
pip install pyinstaller
python build.py
```

产物在 `dist/MarkdownViewer-Setup.exe`。

## 🧪 开发与测试

```bash
pip install -e ".[dev]"
pytest                       # 单元 + 冒烟测试
pytest --benchmark           # 性能基准
```

测试覆盖见 `tests/`（PyQt 单实例逻辑、bridge、utils 等）。

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| GUI 框架 | PyQt6 / PyQt6-WebEngine |
| 渲染内核 | Chromium (WebEngine) + QWebChannel 桥接 |
| Markdown 解析 | markdown-it 14 + 插件 |
| 代码高亮 | highlight.js 11 |
| 图表 | Mermaid 11 / ECharts 5 |
| 数学公式 | KaTeX 0.16 |
| 打包 | PyInstaller (onedir) |
| 安装器 | NSIS |

## 📁 项目结构

```
.
├── main.py              # 入口：QApplication、单实例守门、命令行文件分发
├── window.py            # 主窗口：页签、工具栏、文件树、拖放、打印导出
├── bridge.py             # QWebChannel 桥：Python↔JS 互调
├── singleinstance.py    # 单实例 IPC（socket 锁 + 文件转发）
├── utils.py              # 编码探测、frontmatter 解析、统计
├── build.py              # PyInstaller + NSIS 一键打包
├── download_libs.py      # 从 CDN 拉取前端第三方库到 renderer/vendor/
├── installer.nsi         # NSIS 安装脚本
├── renderer/
│   ├── index.html        # WebEngine 页面骨架
│   ├── app.js            # 前端渲染逻辑
│   ├── pure-utils.js     # 纯函数工具
│   ├── styles.css        # 页面样式
│   └── vendor/           # 第三方 JS 库（不入仓库，由 download_libs.py 生成）
├── build_assets/         # 图标等打包资源
└── tests/                # pytest 测试套件
```

## 📄 许可证

本项目自身代码基于 **MIT License** 发布，见 [LICENSE.txt](LICENSE.txt)。

本项目分发以下第三方库，其版权归各自所有者所有，许可证清单详见
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)：

| 库 | 许可证 |
|---|---|
| markdown-it 及插件、iconv-lite | MIT |
| highlight.js | BSD-3-Clause |
| Mermaid | MIT |
| ECharts | Apache-2.0 |
| KaTeX | MIT |
| qwebchannel.js (Qt WebChannel) | LGPL-3.0 |
| PyQt6 / PyQt6-WebEngine | GPL v3（商用需另购 Riverbank 授权）|

各第三方库的完整许可证文本由 `download_libs.py` 拉取到 `renderer/vendor/LICENSES/`，
随安装包分发，满足 MIT/BSD/Apache/LGPL 的"保留版权声明"要求。

## 👤 作者

高志强（gzqall）

主页：<https://github.com/gzqall/MarkDown-Viewer>
