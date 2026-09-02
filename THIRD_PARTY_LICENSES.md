# 第三方许可证声明

Markdown Viewer 在分发时包含以下第三方库。各库的版权归各自所有者所有，
完整许可证文本随安装包的 `renderer/vendor/LICENSES/` 目录分发
（由 `download_libs.py` 从 CDN 自动拉取）。

## 前端库（renderer/vendor/）

| 库 | 版本 | 许可证 (SPDX) |
|---|---|---|
| markdown-it | 14.1.0 | MIT |
| markdown-it-emoji | 3.0.0 | MIT |
| markdown-it-sub | 2.0.0 | MIT |
| markdown-it-sup | 2.0.0 | MIT |
| markdown-it-mark | 4.0.0 | MIT |
| markdown-it-footnote | 4.0.0 | MIT |
| markdown-it-task-lists | 2.1.1 | MIT |
| markdown-it-container | 4.0.0 | MIT |
| highlight.js | 11.11.0 | BSD-3-Clause |
| Mermaid | 11.6.0 | MIT |
| ECharts | 5.6.0 | Apache-2.0 |
| KaTeX | 0.16.21 | MIT |
| qwebchannel.js (Qt WebChannel) | 6.7.0 | LGPL-3.0-only |

## Python 依赖（PyInstaller 打包进运行时）

| 库 | 许可证 | 商用说明 |
|---|---|---|
| PyQt6 / PyQt6-WebEngine | GPL v3 | 闭源商业分发需购买 [Riverbank 商业授权](https://www.riverbankcomputing.com/commercial/license-faq)；开源分发无限制 |
| Python | PSF-2.0 | — |

> **PyQt6 GPL 注意**：若以开源形式分发 Markdown Viewer（本项目自身为 MIT），PyQt6 的 GPL v3 允许随开源安装包分发。如需闭源商业分发，请先获取 Riverbank 商业授权。

## 本项目自身

Markdown Viewer 自身代码基于 MIT License，见 [LICENSE.txt](LICENSE.txt)。
