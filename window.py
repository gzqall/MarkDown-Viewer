"""Main window with tabs, global theme, event-filter drag-drop, bridge"""

import json, os, sys, re
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QTimer, QObject, pyqtSignal, QEvent
from PyQt6.QtGui import QAction, QIcon, QPageLayout, QPageSize, QGuiApplication
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTabBar, QFrame, QListWidget,
    QListWidgetItem, QSplitter, QFileDialog, QMessageBox, QLabel,
    QStatusBar, QSizePolicy, QToolButton, QToolBar, QMenu, QInputDialog, QLineEdit,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel
from bridge import FileBridge
from utils import MD_EXTENSIONS, detect_encoding, parse_frontmatter, count_stats

# 应用版本（集中管理，installer.nsi / About 各自同步）
APP_VERSION = "1.1.0"

# 配置目录：用 %APPDATA% 而非安装目录，避免装到 Program Files 后不可写
# 导致主题切换 / 最近文件列表重启丢失。
def _config_dir():
    base = os.getenv("APPDATA") or str(Path.home())
    d = Path(base) / "MarkdownViewer"
    d.mkdir(parents=True, exist_ok=True)
    return d

CONFIG_PATH = str(_config_dir() / "config.json")


D = { "bg0":"#0f1a24","bg1":"#16222e","bg2":"#1a2a38","bg3":"#233545",
      "hover":"#2d4258","fg0":"#eaf2fb","fg1":"#b8c8d8","fg2":"#6c8090",
      "accent":"#5b94c8","accent_bg":"rgba(91,148,200,0.15)","border":"#2d4258" }
L = { "bg0":"#ffffff","bg1":"#f0f5fa","bg2":"#ffffff","bg3":"#e3edf5",
      "hover":"#d4e3ee","fg0":"#1a2a38","fg1":"#3d5566","fg2":"#8aa0b0",
      "accent":"#3c6a9b","accent_bg":"rgba(60,106,155,0.10)","border":"#c5d5e0" }

def qss(t):
    return f"""
QMainWindow {{background:{t["bg0"]}}}
QToolBar {{background:{t["bg2"]};border-bottom:1px solid {t["border"]};padding:2px 6px;min-height:36px}}
QToolButton {{border:none;border-radius:4px;padding:4px 8px;color:{t["fg1"]};font-size:14px;min-width:28px;min-height:28px}}
QToolButton:hover {{background:{t["hover"]};color:{t["fg0"]}}}
QTabBar {{background:{t["bg1"]};border-bottom:1px solid {t["border"]}}}
QTabBar::tab {{background:{t["bg1"]};color:{t["fg1"]};border:1px solid {t["border"]};border-bottom:none;border-radius:4px 4px 0 0;padding:4px 18px 4px 12px;margin:2px 1px 0;font-size:12px;min-height:24px}}
QTabBar::tab:selected {{background:{t["bg0"]};color:{t["accent"]};border-bottom:1px solid {t["bg0"]}}}
QTabBar::tab:hover:!selected {{background:{t["bg3"]}}}
QTabBar::close-button {{subcontrol-position:right;margin-right:2px}}
QTabBar::close-button:hover {{background:rgba(243,139,168,0.3);border-radius:2px}}
#treePanel {{background:{t["bg1"]};border-right:1px solid {t["border"]}}}
#dirLabel {{padding:8px 12px;font-size:12px;font-weight:600;color:{t["fg2"]};background:{t["bg2"]};border-bottom:1px solid {t["border"]}}}
QListWidget {{background:transparent;border:none;font-size:13px;color:{t["fg1"]}}}
QListWidget::item {{padding:5px 12px}}
QListWidget::item:hover {{background:{t["bg3"]};color:{t["fg0"]}}}
QListWidget::item:selected {{background:{t["accent_bg"]};color:{t["accent"]}}}
QStatusBar {{background:{t["bg2"]};border-top:1px solid {t["border"]};color:{t["fg2"]};font-size:12px;min-height:24px}}
QMenuBar {{background:{t["bg0"]};color:{t["fg0"]};border-bottom:1px solid {t["border"]};font-size:13px}}
QMenuBar::item:selected {{background:{t["hover"]}}}
QMenu {{background:{t["bg2"]};color:{t["fg0"]};border:1px solid {t["border"]}}}
QMenu::item:selected {{background:{t["hover"]}}}
QMenu::separator {{height:1px;background:{t["border"]};margin:4px 8px}}
"""

class FileWatcher(QObject):
    changed = pyqtSignal(str, str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = QTimer(self); self._t.timeout.connect(self._check)
        self._p = None; self._m = 0; self._s = 0
    def watch(self, p):
        self.stop()
        try: s = os.stat(p); self._p = p; self._m = s.st_mtime; self._s = s.st_size; self._t.start(800)
        except: pass
    def stop(self): self._t.stop(); self._p = None
    def _check(self):
        if not self._p: return
        try:
            s = os.stat(self._p)
            if s.st_mtime != self._m or s.st_size != self._s:
                self._m = s.st_mtime; self._s = s.st_size
                _, content = detect_encoding(self._p)
                self.changed.emit(self._p, content)
        except: pass


# Global list to keep all window references alive
_instances = []

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Enable local file access BEFORE any QWebEngineView is created
        profile = QWebEngineProfile.defaultProfile()
        s = profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        self.setWindowTitle("Markdown Viewer")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _instances.append(self)
        self.destroyed.connect(lambda: self._on_destroyed())
        self.setMinimumSize(800, 600); self.resize(1280, 860)
        # Set window icon
        icon_p = os.path.join(os.path.dirname(__file__), "build_assets", "app.ico")
        if os.path.exists(icon_p):
            self.setWindowIcon(QIcon(icon_p))
        self._tabs = []; self._cur = -1
        self._theme = "dark"; self._recent_files = []
        self._ready = False; self._pending = None
        self._ch = None; self._br = None
        self._watcher = FileWatcher(self)
        self._watcher.changed.connect(self._on_file_changed)
        self._load_config()
        self._ui(); self._menu(); self._bridge()
        self._theme_apply()
        # 系统亮暗变化时，若主题为 auto 则跟随
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(
                lambda: self._theme_apply() if self._theme == "auto" else None
            )
        except Exception:
            pass  # 旧版 Qt 无此信号
        self.statusBar().showMessage("Ready - Ctrl+O to open")

    def _toggle_theme(self):
        # 三态循环：dark → light → auto → dark
        order = ["dark", "light", "auto"]
        i = order.index(self._theme) if self._theme in order else 0
        self._theme = order[(i + 1) % len(order)]
        self._save_config(); self._theme_apply()

    def _resolved_theme(self):
        """把 'auto' 解析成实际的 dark/light。"""
        if self._theme != "auto":
            return self._theme
        try:
            cs = QGuiApplication.styleHints().colorScheme()
        except Exception:
            cs = Qt.ColorScheme.Unknown
        if cs == Qt.ColorScheme.Light:
            return "light"
        if cs == Qt.ColorScheme.Dark:
            return "dark"
        return "dark"  # 系统未知时默认暗色

    def _theme_apply(self):
        r = self._resolved_theme()
        t = D if r == "dark" else L
        self.setStyleSheet(qss(t))
        # 按钮图标：dark→☀️（切到亮），light→🌙（切到暗），auto→🖥️
        icon = {"dark": "☀️", "light": "🌙", "auto": "🖥️"}.get(self._theme, "🌙")
        self.btn_theme.setText(icon)
        self._js(f"document.documentElement.setAttribute('data-theme','{r}')")
        self._js("if(window._onThemeChanged)window._onThemeChanged()")

    def _ui(self):
        c = QWidget(); self.setCentralWidget(c)
        lo = QVBoxLayout(c); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)
        tb = QToolBar(); tb.setMovable(False)
        def b(txt, tip, fn):
            x = QToolButton(); x.setText(txt); x.setToolTip(tip); x.clicked.connect(fn); return x
        self.btn_open = b("📂","Open File (Ctrl+O)",self._on_open)
        self.btn_reload = b("🔄","Reload (Ctrl+R)",self._on_reload); self.btn_reload.setVisible(False)
        self.btn_tree = b("🌳","File Tree (Ctrl+B)",self._toggle_tree)
        self.btn_toc = b("📑","TOC (Ctrl+T)",self._toggle_toc)
        self.btn_search = b("🔍","Search (Ctrl+F)",self._toggle_search)
        self.btn_zm = b("A+","Zoom In",lambda:self._js("window._zoomIn?.()"))
        self.btn_zout = b("A-","Zoom Out",lambda:self._js("window._zoomOut?.()"))
        self.btn_theme = b("🌙","Theme",self._toggle_theme)
        self.btn_export = b("📕","Export to PDF (Ctrl+E)",self._export_pdf)
        self.btn_export_html = b("🌐","Export to HTML",self._export_html)
        self.btn_fullscreen = b("⛶","Fullscreen (F11)",self._toggle_fullscreen)
        self.btn_pintop = b("📌","置顶小窗 (Ctrl+L)",self._toggle_pintop)
        tb.addWidget(self.btn_open); tb.addWidget(self.btn_reload)
        tb.addSeparator(); tb.addWidget(self.btn_tree); tb.addSeparator()
        tb.addWidget(self.btn_search); tb.addWidget(self.btn_toc)
        tb.addSeparator(); tb.addWidget(self.btn_zout); tb.addWidget(self.btn_zm)
        tb.addSeparator()
        self.lbl_path = QLabel("No file")
        self.lbl_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(self.lbl_path); tb.addWidget(self.btn_pintop)
        tb.addWidget(self.btn_fullscreen); tb.addWidget(self.btn_export_html); tb.addWidget(self.btn_export); tb.addWidget(self.btn_theme)
        lo.addWidget(tb)
        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True); self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True); self.tab_bar.setDrawBase(False)
        self.tab_bar.tabCloseRequested.connect(self._close_tab)
        self.tab_bar.currentChanged.connect(self._tab_changed)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._tab_context_menu)
        self.tab_bar.setVisible(False)
        lo.addWidget(self.tab_bar)
        sp = QSplitter(Qt.Orientation.Horizontal); sp.setHandleWidth(1)
        self.tree_panel = QFrame(); self.tree_panel.setObjectName("treePanel")
        self.tree_panel.setMinimumWidth(0); self.tree_panel.setMaximumWidth(300)
        tl = QVBoxLayout(self.tree_panel); tl.setContentsMargins(0,0,0,0); tl.setSpacing(0)
        # Tree panel header row: dir path + refresh button
        th = QHBoxLayout(); th.setContentsMargins(8,4,4,4); th.setSpacing(4)
        self.dir_label = QLabel(); self.dir_label.setObjectName("dirLabel")
        self.dir_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_tree_refresh = QToolButton()
        self.btn_tree_refresh.setText("↻")
        self.btn_tree_refresh.setToolTip("刷新文件列表")
        self.btn_tree_refresh.clicked.connect(self._refresh_tree)
        self.btn_tree_refresh.setFixedSize(28, 28)
        th.addWidget(self.dir_label, 1)
        th.addWidget(self.btn_tree_refresh)
        tl.addLayout(th)
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self._tree_click)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._tree_context_menu)
        tl.addWidget(self.file_list)
        # Auto-refresh timer for file tree
        self._tree_dir = None
        self._tree_timer = QTimer(self)
        self._tree_timer.timeout.connect(self._auto_refresh_tree)
        self._tree_timer.start(3000)
        self.webview = QWebEngineView(); self.webview.setMinimumWidth(400)
        # Disable Chromium's default context menu so our custom image menu
        # (wired up in app.js) isn't shadowed by the built-in one.
        self.webview.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        sp.addWidget(self.tree_panel); sp.addWidget(self.webview)
        sp.setStretchFactor(0,0); sp.setStretchFactor(1,1)
        lo.addWidget(sp, 1)
        sb = QStatusBar(self)
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("font-size:11px; padding:0 8px;")
        sb.addPermanentWidget(self.lbl_count)
        lo.addWidget(sb)

    def _menu(self):
        mb = self.menuBar()
        def add(m, items):
            for i in items:
                if i is None: m.addSeparator()
                else: a = QAction(i[0],self); a.triggered.connect(i[2]); m.addAction(a)

        file_menu = mb.addMenu("&File")
        add(file_menu, [
            ("📂  &Open File...\tCtrl+O", None, self._on_open),
            ("📁  Open &Folder...", None, self._on_open_folder),
            None, ("🔄  &Reload", None, self._on_reload), None,
            ("🆕  &New Window", None, self._new_window),
            None, ("📕  Export to &PDF...\tCtrl+E", None, self._export_pdf),
            ("🌐  Export to &HTML...", None, self._export_html), None,
            ("🖨️  &Print...\tCtrl+P", None, self._print_file), None,
        ])
        # Recent Files submenu
        self._recent_menu = file_menu.addMenu("📜  Recent Files")
        self._build_recent_menu()
        file_menu.addSeparator()
        add(file_menu, [("❌  E&xit\tCtrl+Q", None, self.close)])
        add(mb.addMenu("&View"), [
            ("📁  File &Tree\tCtrl+B", None, self._toggle_tree),
            ("📑  TOC\tCtrl+T", None, self._toggle_toc), None,
            ("🔍  &Search\tCtrl+F", None, self._toggle_search), None,
            ("⛶  &Fullscreen\tF11", None, self._toggle_fullscreen),
            ("📌  置顶小窗\tCtrl+L", None, self._toggle_pintop), None,
            ("🌙  Toggle &Theme", None, self._toggle_theme),
        ])
        add(mb.addMenu("&Help"), [("&About", None, self._about)])

    def _bridge(self):
        self._br = FileBridge(window=self)
        self._ch = QWebChannel()
        self._ch.registerObject("bridge", self._br)
        self.webview.page().setWebChannel(self._ch)
        self._br.pageReady.connect(self._page_ready)
        # Resolve renderer directory: PyInstaller uses sys._MEIPASS, source uses __file__
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        renderer_dir = os.path.join(base, "renderer")
        index_path = os.path.join(renderer_dir, "index.html")
        # Qt6 WebEngine: 直接加载本地 index.html。
        # LocalContentCanAccessFileUrls=True 已在 __init__ 打开，vendor 外链脚本能正常加载；
        # 保留 index.html 内的 CSP（default-src 'self'），挡掉不可信 md 的内联脚本注入。
        try:
            self.webview.setUrl(QUrl.fromLocalFile(index_path))
        except Exception as e:
            self.webview.setHtml(f"<h1>Error loading renderer</h1><p>{e}</p>")

    def _page_ready(self):
        self._ready = True
        self._theme_apply()
        # 命令行/拖放传入的文件在页面未就绪时被暂存为 _pending，先把它下发。
        # 命令行文件已作为 tab 0 建好并 setCurrentIndex(0)（见 _open_background
        # 的 activate=True 分支），它就是前台活动页签。
        if self._pending:
            self._send(self._pending)
            self._pending = None
        # 会话恢复：上次关闭时查看的文件，作为后台页签加入（不抢命令行文件
        # 的前台焦点）。若没有命令行文件，_cur<0 → _open_background 内部会
        # 自动激活第一个恢复的文件，避免空白。
        restore = getattr(self, "_restore_tabs", None) or []
        self._restore_tabs = []
        for p in restore:
            try:
                p = os.path.abspath(p)
                if os.path.isfile(p) and os.path.splitext(p)[1].lower() in MD_EXTENSIONS:
                    self._open_background(p, activate=False)
            except Exception:
                pass

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_RECENT_FILES = 10

    def _load_config(self):
        """Load persistent config (theme + recent files) from %APPDATA%.
        Writing into the install dir fails silently when the app is installed
        under Program Files, so we keep config in the per-user appdata dir."""
        if not os.path.exists(CONFIG_PATH):
            # 首次迁移：若旧版配置（根目录 .mdt_config.json）存在，搬过来
            # 再继续用 AppData，避免升级后主题/最近文件"重置一次"。
            legacy = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mdt_config.json")
            if os.path.exists(legacy):
                try:
                    import shutil
                    shutil.copy2(legacy, CONFIG_PATH)
                except Exception:
                    pass
        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                cfg = json.load(f)
                self._theme = cfg.get("theme", "dark")
                self._recent_files = cfg.get("recent_files", [])
                self._restore_tabs = cfg.get("open_tabs", [])
        except Exception:
            self._theme = "dark"
            self._recent_files = []
            self._restore_tabs = []

    def _save_config(self):
        """Save persistent config (theme + recent files + open tabs) to %APPDATA%."""
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump({
                    "version": APP_VERSION,
                    "theme": self._theme,
                    "recent_files": self._recent_files[-self.MAX_RECENT_FILES:],
                    "open_tabs": self._tabs_to_save(),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # 不静默吞掉——打印到 stderr 方便排查，但不打扰用户
            print(f"[MarkdownViewer] config save failed: {e}", file=sys.stderr)

    def _tabs_to_save(self):
        """收集当前标签页路径列表，用于会话恢复。"""
        if not self._tabs:
            return []
        # 保存最后一个活跃标签（避免一次恢复太多窗口）
        if 0 <= self._cur < len(self._tabs):
            return [self._tabs[self._cur]["path"]]
        return [self._tabs[0]["path"]] if self._tabs else []

    def _add_recent_file(self, path):
        """Add a file to the recent files list and persist."""
        path = os.path.abspath(path)
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.append(path)
        if len(self._recent_files) > self.MAX_RECENT_FILES:
            self._recent_files = self._recent_files[-self.MAX_RECENT_FILES:]
        self._save_config()
        self._build_recent_menu()

    def _build_recent_menu(self):
        """Rebuild the Recent Files submenu."""
        self._recent_menu.clear()
        if not self._recent_files:
            a = QAction("(no recent files)", self)
            a.setEnabled(False)
            self._recent_menu.addAction(a)
            return
        for path in reversed(self._recent_files):
            name = os.path.basename(path)
            a = QAction(f"📄  {name}", self)
            a.setToolTip(path)
            a.triggered.connect(lambda checked, p=path: self._open(p))
            self._recent_menu.addAction(a)

    def _open(self, path, activate=None):
        """打开文件的统一入口，默认**后台**语义（不抢当前页签焦点），
        符合"双击/拖放/wiki 链接打开第二个文件时保持当前页"的习惯。

        activate:
          None（默认）→ 自动判断：当前无页签（_cur<0）时激活，否则后台。
          True/False → 显式覆盖。
        已存在的同路径页签：activate=True 才切过去，否则什么都不做（保持现状）。
        """
        if activate is None:
            activate = self._cur < 0
        self._open_background(path, activate=activate)

    def _open_background(self, path, activate=False):
        path = os.path.abspath(path)
        if not os.path.isfile(path): return self._toast("File not found")
        if os.path.splitext(path)[1].lower() not in MD_EXTENSIONS:
            return self._toast("Unsupported file type")

        # 已有同路径页签：按 activate 决定是否切过去（不重复加 tab）
        for i, t in enumerate(self._tabs):
            if t["path"] == path:
                if activate:
                    self.tab_bar.setCurrentIndex(i)
                return

        # 大文件保护
        file_size = os.path.getsize(path)
        if file_size > self.MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            reply = QMessageBox.question(
                self, "Large File",
                f"File size is {size_mb:.1f} MB, which may cause slowdown or crash.\n\n"
                f"Open anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            enc, content = detect_encoding(path)
            # Strip YAML frontmatter for rendering
            fm, render_content = parse_frontmatter(content) if content.startswith('---') else ({}, content)
            tab = {"path": path, "name": os.path.basename(path), "content": render_content, "raw_content": content, "frontmatter": fm}
            if enc != 'utf-8':
                self._toast(f"Detected encoding: {enc}")
        except Exception as e:
            return QMessageBox.critical(self, "Error", str(e))
        self._tabs.append(tab)
        self.tab_bar.addTab(tab["name"])
        # Show full path in tooltip
        self.tab_bar.setTabToolTip(self.tab_bar.count() - 1, tab["path"])
        self._tab_vis()
        # 新页签默认后台加入（addTab 不改变 currentIndex，已验证）。
        # 仅当 activate=True 或当前无可见页签时才切过去显示内容。
        if activate or self._cur < 0:
            self.tab_bar.setCurrentIndex(len(self._tabs) - 1)
        self.btn_reload.setVisible(True)
        self._toast(f"Opened: {tab['name']}")
        self._add_recent_file(path)

    def _open_background_batch(self, paths):
        """主实例接收第二进程转发的文件路径列表，逐个作为后台页签加入。
        单实例 IPC 的 files_received 信号回调。全部后台，不抢当前焦点。"""
        for p in paths:
            try:
                if p and os.path.isfile(p):
                    self._open_background(p, activate=False)
            except Exception:
                pass

    def _send(self, tab):
        if not self._ready: self._pending = tab; return
        info = json.dumps({
            "path": tab["path"], "name": tab["name"],
            "dir": os.path.dirname(tab["path"]),
            "content": tab["content"],
        })
        self._js(f"window._openFile({info})")
        # Update word count in status bar
        self._update_word_count(tab["content"])

    def _parse_frontmatter(self, content):
        """Parse YAML frontmatter. Delegates to utils.parse_frontmatter (kept
        as a method for backward-compat with any external callers)."""
        return parse_frontmatter(content)

    def _update_word_count(self, content):
        # Parse frontmatter first (reuse cached parse from _open if available)
        fm, body = parse_frontmatter(content)
        s = count_stats(body)
        lines, words, chars, cjk = s["lines"], s["words"], s["chars"], s["cjk"]

        parts = [f"  {lines} lines  ·  {words} words  ·  {chars} chars  "]
        if fm.get('title'):
            parts.append(f"📌 {fm['title']}")
        self.lbl_count.setText(" | ".join(parts))

        tooltip = f"Lines: {lines}\nWords: {words}\nCharacters: {chars}\nCJK: {cjk}"
        for k, v in fm.items():
            tooltip += f"\n{k}: {v}"
        self.lbl_count.setToolTip(tooltip)

    def _tab_changed(self, idx):
        if idx < 0 or idx >= len(self._tabs): return
        # Save current tab's scroll position before switching
        if self._cur >= 0 and self._cur < len(self._tabs):
            old_path = self._tabs[self._cur]["path"]
            self._js(f"window._saveScrollPos({json.dumps(old_path)})")
        self._cur = idx
        t = self._tabs[idx]
        self.lbl_path.setText(f"  {t['name']}  ")
        self.setWindowTitle(f"Markdown Viewer - {t['name']}")
        # 切回的文件目录与当前树目录相同则跳过重建（_auto_refresh_tree 会兜底
        # 检测变化），避免大目录频繁全量刷新导致列表抖动
        new_dir = os.path.dirname(t["path"])
        if os.path.normpath(self._tree_dir or "") != os.path.normpath(new_dir):
            self._populate_tree(new_dir)
        self._watcher.watch(t["path"])
        self._send(t)

    def _close_tab(self, idx):
        if idx < 0 or idx >= len(self._tabs): return
        self._tabs.pop(idx); self.tab_bar.removeTab(idx)
        self._tab_vis()
        if not self._tabs:
            self._cur = -1; self.lbl_path.setText("No file")
            self.setWindowTitle("Markdown Viewer")
            self.btn_reload.setVisible(False); self._watcher.stop()
            self._js("dom.preview.innerHTML='';dom.dropOverlay?.classList.remove('hidden');")

    def _tab_vis(self): self.tab_bar.setVisible(self.tab_bar.count() > 0)

    def _on_open(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open Markdown", "", "Markdown (*.md *.mdx *.markdown);;All (*)")
        if p: self._open(p)
    def _on_open_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Open Folder")
        if d: self._populate_tree(d)
    def _on_reload(self):
        """重新加载当前页签的文件（从磁盘重读）。
        不走 _open_background——否则已存在的同路径页签会被当成"后台不切"，
        reload 失效。直接重读 + 重发当前 tab，保持焦点不变。"""
        if self._cur < 0: return
        path = self._tabs[self._cur]["path"]
        try:
            _, content = detect_encoding(path)
            fm, render_content = parse_frontmatter(content) if content.startswith('---') else ({}, content)
            self._tabs[self._cur].update(
                content=render_content, raw_content=content, frontmatter=fm,
            )
        except Exception as e:
            return QMessageBox.critical(self, "Error", str(e))
        self._send(self._tabs[self._cur])
        self._toast(f"Reloaded: {self._tabs[self._cur]['name']}")

    def _export_pdf(self):
        """Export current document as PDF via QWebEnginePage.print() + QPrinter."""
        if self._cur < 0:
            return self._toast("No file to open")
        tab = self._tabs[self._cur]
        default_name = os.path.splitext(tab["name"])[0] + ".pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to PDF", default_name, "PDF (*.pdf)"
        )
        if not path:
            return
        self._toast("Generating PDF…")
        QTimer.singleShot(50, lambda: self._do_export_pdf(path))

    def _do_export_pdf(self, path):
        """Actual PDF export using QPrinter (runs after event loop tick).
        Keep printer & callback as instance vars to prevent GC from destroying
        C++ objects while the async print operation is in flight.
        """
        self._pdf_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self._pdf_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        self._pdf_printer.setOutputFileName(path)

        self._export_timed_out = False
        QTimer.singleShot(15000, lambda: self._pdf_timeout(path))

        def on_printed(success):
            if self._export_timed_out:
                return
            if success:
                self._toast(
                    f"PDF exported: {os.path.basename(path)}", 4000)
            else:
                self._toast("PDF export failed", 3000)
            # Release references so C++ objects can be cleaned up
            self._pdf_callback = None
            self._pdf_printer = None

        self._pdf_callback = on_printed  # keep callback alive

        try:
            self.webview.page().print(self._pdf_printer, self._pdf_callback)
        except Exception as e:
            self._toast(f"Export error: {e}", 3000)
            self._pdf_callback = None
            self._pdf_printer = None

    def _pdf_timeout(self, path):
        """Safety timeout: if PDF hasn't completed after 15s, notify user."""
        self._export_timed_out = True
        self._toast(
            f"PDF export timeout — the file may be incomplete: "
            f"{os.path.basename(path)}", 5000)

    def _populate_tree(self, d):
        self._tree_dir = d
        self.dir_label.setText(f"📁 {os.path.basename(d) or d}")
        self.dir_label.setToolTip(d)
        self.file_list.clear()
        try:
            # Add ".." parent directory entry
            parent = os.path.dirname(d)
            if parent and parent != d:
                it = QListWidgetItem("  📁  ..")
                it.setData(Qt.ItemDataRole.UserRole, parent)
                it.setToolTip(f"上级目录: {parent}")
                self.file_list.addItem(it)
            # Add subdirectories (for navigation)
            subs = []
            for e in os.scandir(d):
                if e.is_dir() and not e.name.startswith('.'):
                    subs.append(e.name)
            subs.sort(key=str.lower)
            for s in subs:
                it = QListWidgetItem(f"  📂  {s}")
                it.setData(Qt.ItemDataRole.UserRole, os.path.join(d, s))
                it.setToolTip(os.path.join(d, s))
                self.file_list.addItem(it)
            # Add markdown files
            files = []
            for e in os.scandir(d):
                if e.is_file() and os.path.splitext(e.name)[1].lower() in MD_EXTENSIONS:
                    files.append({"name": e.name, "path": os.path.abspath(e.path)})
            files.sort(key=lambda f: f["name"].lower())
            if not files and not subs:
                it = QListWidgetItem("  (no .md files)")
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.file_list.addItem(it)
            for f in files:
                it = QListWidgetItem(f"📄  {f['name']}")
                it.setData(Qt.ItemDataRole.UserRole, f["path"])
                self.file_list.addItem(it)
            if self.tree_panel.width() < 10:
                self.tree_panel.setMinimumWidth(220); self.tree_panel.setMaximumWidth(300)
        except: self.dir_label.setText("📁 (error reading directory)")

    def _refresh_tree(self):
        if self._tree_dir and os.path.isdir(self._tree_dir):
            self._populate_tree(self._tree_dir)
            self._toast("Tree refreshed")
        elif self._cur >= 0:
            self._populate_tree(os.path.dirname(self._tabs[self._cur]["path"]))

    def _auto_refresh_tree(self):
        """Periodic check: refresh tree if directory contents changed."""
        if not self._tree_dir or not os.path.isdir(self._tree_dir):
            return
        try:
            current = set()
            for e in os.scandir(self._tree_dir):
                if e.is_dir() and not e.name.startswith('.'):
                    current.add(e.name)
                elif e.is_file() and os.path.splitext(e.name)[1].lower() in MD_EXTENSIONS:
                    current.add(e.name)
            tree_items = set()
            for i in range(self.file_list.count()):
                it = self.file_list.item(i)
                p = it.data(Qt.ItemDataRole.UserRole)
                if p and os.path.exists(p):
                    tree_items.add(os.path.basename(p))
            if tree_items != current:
                self._populate_tree(self._tree_dir)
        except:
            pass

    def _tree_click(self, item):
        p = item.data(Qt.ItemDataRole.UserRole)
        if not p: return
        if os.path.isdir(p):
            self._populate_tree(p)
        else:
            self._open(p)

    def _tree_context_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = QMenu(self)
        is_dir = os.path.isdir(path)

        if not is_dir:
            open_action = menu.addAction("📂  Open")
            open_action.triggered.connect(lambda: self._open(path))
            menu.addSeparator()

        show_in_folder = menu.addAction("📁  Show in Folder")
        show_in_folder.triggered.connect(lambda: self._show_in_folder(path))

        copy_path = menu.addAction("📋  Copy Path")
        copy_path.triggered.connect(lambda: self._copy_to_clipboard(path))

        if not is_dir:
            rename_action = menu.addAction("✏️  Rename...")
            rename_action.triggered.connect(lambda: self._rename_file(item, path))

            delete_action = menu.addAction("🗑️  Delete...")
            delete_action.setIcon(QIcon())  # no icon needed
            delete_action.triggered.connect(lambda: self._delete_file(item, path))

        menu.exec(self.file_list.mapToGlobal(pos))

    def _show_in_folder(self, path):
        # os.startfile 仅 Windows 可用；加 fallback 防止非 Win 环境崩溃
        startfile = getattr(os, "startfile", None)
        if startfile:
            startfile(os.path.dirname(path))
        else:
            import subprocess
            subprocess.Popen(["xdg-open" if sys.platform.startswith("linux") else "open",
                               os.path.dirname(path)])

    # ─── Image operations (called from JS context-menu / lightbox) ────────
    # JS hands us a URL as shown in <img src>. That is either:
    #   • http(s)://  → fetch bytes via QNetworkAccessManager, cache to temp
    #   • file://     → parse to a local path
    #   • bare path   → already resolved against the .md dir by JS, treat local

    def _url_to_local_path(self, url):
        """Best-effort conversion of an <img src> URL to a local file path.
        Returns None for remote (http) URLs or anything unresolvable."""
        if not url:
            return None
        u = url.strip()
        if u.startswith('file://'):
            # QUrl handles percent-encoding and host edge cases
            path = QUrl(u).toLocalFile()
            return path or None
        if u.startswith('http://') or u.startswith('https://'):
            return None
        # Strip a leading slash — absolute Windows paths like /C:/... come from
        # Chromium normalizing file URLs; leave Windows-style C:\ alone.
        if len(u) > 2 and u[0] == '/' and u[2] == ':':
            u = u[1:]
        # Anything that exists as-is
        if os.path.isfile(u):
            return os.path.abspath(u)
        # Heuristic: looks like a Windows path but the file isn't there
        return None

    def _open_image_externally(self, url):
        """Open the image's source in the OS default viewer."""
        path = self._url_to_local_path(url)
        if path and os.path.isfile(path):
            try:
                os.startfile(path)
                return
            except Exception as e:
                self._toast(f"Open failed: {e}", 3000)
        elif url.startswith('http://') or url.startswith('https://'):
            # Remote: open the URL itself in the default browser
            try:
                os.startfile(url)
                return
            except Exception as e:
                self._toast(f"Open failed: {e}", 3000)
        self._toast("Cannot locate original image file", 3000)

    def _show_image_in_folder(self, url):
        """Reveal the source image in the system file explorer."""
        path = self._url_to_local_path(url)
        if not path or not os.path.isfile(path):
            self._toast("Cannot locate original image file", 3000)
            return
        try:
            # os.startfile on a folder opens Explorer at that folder.
            # On Windows, opening the file's parent dir usually selects
            # nothing; pass the file path so Explorer can select it.
            import subprocess
            subprocess.Popen(['explorer.exe', '/select,', os.path.normpath(path)])
        except Exception as e:
            try:
                os.startfile(os.path.dirname(path))
            except Exception as e2:
                self._toast(f"Show in folder failed: {e2}", 3000)

    def _save_image_as(self, url):
        """Save the source image to a user-chosen location. Local files are
        copied directly; remote URLs are fetched first via QNetworkAccessManager.
        """
        src_path = self._url_to_local_path(url)
        if src_path and os.path.isfile(src_path):
            self._do_save_local_image(src_path)
        elif url.startswith('http://') or url.startswith('https://'):
            self._do_save_remote_image(url)
        else:
            self._toast("Cannot locate original image file", 3000)

    def _do_save_local_image(self, src_path):
        base = os.path.splitext(os.path.basename(src_path))[0]
        ext = os.path.splitext(src_path)[1] or '.png'
        default_name = base + ext
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Image As", default_name,
            "Image files (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;All (*)"
        )
        if not dest:
            return
        try:
            import shutil
            shutil.copy2(src_path, dest)
            self._toast(f"Saved: {os.path.basename(dest)}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _do_save_remote_image(self, url):
        """Fetch a remote image and save it. Falls back to the default browser
        download if Qt networking is unavailable."""
        from urllib.parse import urlparse
        name = os.path.basename(urlparse(url).path) or 'image.png'
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Image As", name,
            "Image files (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All (*)"
        )
        if not dest:
            return
        try:
            from PyQt6.QtCore import QUrl as _QUrl
            from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        except Exception:
            # No Qt network — let the browser handle the download
            try:
                os.startfile(url)
                self._toast("Opened in browser for download", 3000)
            except Exception:
                self._toast("Cannot fetch remote image", 3000)
            return
        # network manager must outlive the request → keep on the instance
        self._net_mgr = QNetworkAccessManager(self)
        req = QNetworkRequest(_QUrl(url))
        # Stash header sniffing for extension fallback
        reply = self._net_mgr.get(req)
        self._net_reply = reply
        self._net_dest = dest

        def _on_finished():
            data = bytes(reply.readAll())
            if not data:
                self._toast("Failed to download image", 3000)
                reply.deleteLater()
                return
            # If user gave no extension, try sniffing from content-type
            try:
                mime = reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader)
            except Exception:
                mime = None
            final_dest = dest
            if not os.path.splitext(dest)[1] and mime:
                ext = self._mime_to_ext(mime)
                if ext:
                    final_dest = dest + ext
            try:
                with open(final_dest, 'wb') as f:
                    f.write(data)
                self._toast(f"Saved: {os.path.basename(final_dest)}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save failed", str(e))
            reply.deleteLater()

        reply.finished.connect(_on_finished)
        self._toast("Downloading…", 2000)

    @staticmethod
    def _mime_to_ext(mime):
        m = (mime or '').lower().split(';')[0].strip()
        return {
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/gif': '.gif',
            'image/bmp': '.bmp',
            'image/webp': '.webp',
            'image/svg+xml': '.svg',
        }.get(m)

    def _copy_to_clipboard(self, text):
        """Copy arbitrary text (URL/path) to the system clipboard."""
        from PyQt6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(text)
        self._toast("Copied to clipboard")

    def _rename_file(self, item, old_path):
        name, ok = QInputDialog.getText(
            self, "Rename", "New name:",
            QLineEdit.EchoMode.Normal, os.path.basename(old_path),
        )
        if not ok or not name:
            return
        new_path = os.path.join(os.path.dirname(old_path), name)
        try:
            os.rename(old_path, new_path)
            self._refresh_tree()
            self._toast(f"Renamed to: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Rename failed: {e}")

    def _delete_file(self, item, path):
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete {os.path.basename(path)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(path)
            self._refresh_tree()
            self._toast(f"Deleted: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Delete failed: {e}")

    def _tab_context_menu(self, pos):
        idx = self.tab_bar.tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        close_action = menu.addAction("✕  Close")
        close_action.triggered.connect(lambda: self._close_tab(idx))

        close_others = menu.addAction("✕  Close Others")
        close_others.triggered.connect(lambda: self._close_other_tabs(idx))

        close_all = menu.addAction("✕  Close All")
        close_all.triggered.connect(lambda: self._close_all_tabs())

        menu.addSeparator()
        copy_path = menu.addAction("📋  Copy Path")
        copy_path.triggered.connect(lambda: self._copy_to_clipboard(self._tabs[idx]["path"]))

        menu.exec(self.tab_bar.mapToGlobal(pos))

    def _close_other_tabs(self, keep_idx):
        keep_path = self._tabs[keep_idx]["path"]
        for i in range(len(self._tabs) - 1, -1, -1):
            if self._tabs[i]["path"] != keep_path:
                self._close_tab(i)

    def _close_all_tabs(self):
        for i in range(len(self._tabs) - 1, -1, -1):
            self._close_tab(i)

    def _new_window(self):
        """Open a new window instance."""
        w = MainWindow()
        w.show()
        self._toast("New window opened")

    def closeEvent(self, event):
        # 退出前保存会话（当前标签页），供下次恢复
        self._save_config()
        super().closeEvent(event)
        # 主动从存活列表移除（destroyed 信号来得晚，此时 _instances 仍含自己，
        # 否则 "最后窗口关闭即退出" 的判断永远为假）。Qt 默认
        # quitOnLastWindowClosed=True 本就会兜底，这里只做显式清理。
        if self in _instances:
            _instances.remove(self)
        if not _instances:
            QApplication.quit()

    def _on_destroyed(self):
        if self in _instances:
            _instances.remove(self)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.btn_fullscreen.setText("⛶")
        else:
            self.showFullScreen()
            self.btn_fullscreen.setText("🗗")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self._toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def _toggle_pintop(self):
        """置顶小窗模式：窗口置顶 + 半透明 + 隐藏文件树/标签栏，适合一边看文档一边写代码。"""
        self._pintop = not getattr(self, "_pintop", False)
        if self._pintop:
            # 进入：保存当前几何，收窄、降透明、置顶
            self._pintop_geom = self.saveGeometry()
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.setWindowOpacity(0.92)
            self.tree_panel.setFixedWidth(0)
            self.tab_bar.setVisible(False)
            # 收窄到适合阅读的窄窗
            self.resize(560, min(720, self.height()))
            self.btn_pintop.setText("📍")
            self.btn_pintop.setToolTip("退出置顶小窗 (Ctrl+L)")
            self._toast("置顶小窗模式", 1500)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.setWindowOpacity(1.0)
            self.tab_bar.setVisible(self.tab_bar.count() > 0)
            self.tree_panel.setMinimumWidth(220); self.tree_panel.setMaximumWidth(300)
            if getattr(self, "_pintop_geom", None):
                self.restoreGeometry(self._pintop_geom)
            self.btn_pintop.setText("📌")
            self.btn_pintop.setToolTip("置顶小窗 (Ctrl+L)")
        # setWindowFlag 后需要重新展示
        self.show()

    def _toggle_tree(self):
        if self.tree_panel.width() > 10: self.tree_panel.setFixedWidth(0)
        else: self.tree_panel.setMinimumWidth(220); self.tree_panel.setMaximumWidth(300)
    def _toggle_toc(self): self._js("window._toggleTOC?.()")
    def _toggle_search(self): self._js("window._toggleSearch?.()")

    def _export_html(self):
        """Export the current document as a standalone HTML file."""
        if self._cur < 0:
            return self._toast("No file to export")
        tab = self._tabs[self._cur]
        default_name = os.path.splitext(tab["name"])[0] + ".html"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to HTML", default_name, "HTML (*.html)"
        )
        if not path:
            return
        self._toast("Generating HTML…")
        self._export_html_path = path
        self._export_html_name = tab["name"]
        self._js("window._getExportHTML()", self._on_export_html_ready)

    def _on_export_html_ready(self, result):
        """Callback when JS returns rendered HTML."""
        try:
            data = json.loads(result)
            content = data.get("content", "")
            theme = data.get("theme", "dark")
            path = getattr(self, '_export_html_path', None)
            if not path:
                return
            name = getattr(self, '_export_html_name', 'document')
            # Read CSS from disk
            css_path = os.path.join(os.path.dirname(__file__), "renderer", "styles.css")
            css = ""
            if os.path.exists(css_path):
                with open(css_path, encoding='utf-8') as f:
                    css = f.read()
            # Build standalone HTML
            html = f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="{theme}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name}</title>
<style>{css}</style>
</head>
<body>
<div class="markdown-body" style="max-width:820px;margin:0 auto;padding:32px 24px">
{content}
</div>
</body>
</html>"""
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            size_kb = os.path.getsize(path) / 1024
            self._toast(f"HTML exported: {os.path.basename(path)} ({size_kb:.1f} KB)", 4000)
        except Exception as e:
            self._toast(f"Export failed: {e}", 3000)

    def _print_file(self):
        """Print the current document to a printer.
        printer 与 callback 必须挂到 self 上，防止异步打印期间被 Python GC 回收
        导致 C++ 对象提前析构（与 _do_export_pdf 同一类问题）。"""
        if self._cur < 0:
            return self._toast("No file to print")
        from PyQt6.QtPrintSupport import QPrintDialog
        self._print_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(self._print_printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            self._toast("Printing…")
            def on_printed(ok):
                self._toast("Print done" if ok else "Print failed", 3000)
                self._print_callback = None
                self._print_printer = None
            self._print_callback = on_printed  # keep alive
            self.webview.page().print(self._print_printer, self._print_callback)

    def _open_file_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open Markdown", "", "Markdown (*.md *.mdx *.markdown);;All (*)")
        if p: self._open(p); return json.dumps({"path": p})
        return "null"

    def _on_file_changed(self, path, content):
        if self._cur < 0: return
        t = self._tabs[self._cur]
        if t["path"] == path:
            t["content"] = content
            self._toast("File changed, reloaded")
            # Wrap in function call — previously sent raw JSON which was ignored
            self._js(f"window._fileChanged({json.dumps({'path': path, 'content': content, 'changed': True})})")

    def _js(self, code, callback=None):
        if callback:
            self.webview.page().runJavaScript(code, callback)
        else:
            self.webview.page().runJavaScript(code)
    def _toast(self, msg, t=2000): self.statusBar().showMessage(msg, t)
    def _about(self):
        QMessageBox.about(self, "About",
            f"<h3>Markdown Viewer</h3><p>Version {APP_VERSION}</p>"
            f"<p style='font-size:12px;color:#666'>Python {sys.version.split()[0]} · Qt 6 · PyQt6</p>")
