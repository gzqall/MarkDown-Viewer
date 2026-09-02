; Markdown Viewer - NSIS Installer Script
; Creates a proper Windows installer for the packaged app

Unicode True

; Output
OutFile "dist\MarkdownViewer-Setup.exe"

; ─── App Info ──────────────────────────────────────────────────────────────
!define PRODUCT_NAME "Markdown Viewer"
!define PRODUCT_VERSION "1.1.0"
!define PRODUCT_PUBLISHER "高志强"
!define PRODUCT_WEB_SITE "https://github.com/gzqall/MarkDown-Viewer"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\MarkdownViewer.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"
Name "${PRODUCT_NAME}"

; ─── Compiler Settings ────────────────────────────────────────────────────
SetCompressor lzma
SetCompressorDictSize 64
RequestExecutionLevel admin

; ─── Default Install Path ─────────────────────────────────────────────────
; 用 $PROGRAMFILES32 自动定位系统盘的 Program Files (x86)，避免硬编码 D 盘
InstallDir "$PROGRAMFILES32\md-viewer\"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""

; ─── Includes ─────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "nsDialogs.nsh"

; ─── Interface ────────────────────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_ICON "build_assets\app.ico"
!define MUI_UNICON "build_assets\app.ico"
!define MUI_WELCOMEPAGE_TITLE_3LINES
!define MUI_WELCOMEPAGE_TITLE "欢迎使用由高志强制作的 Markdown Viewer"
!define MUI_WELCOMEPAGE_TEXT "本安装程序将引导您完成 Markdown Viewer 的安装过程。$\r$\n$\r$\nMarkdown Viewer 是一款功能强大的 Markdown 文档查看器，支持实时预览、语法高亮、Mermaid 图表、ECharts 图表等功能。$\r$\n$\r$\n单击$\"下一步$\"继续。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\MarkdownViewer.exe"
!define MUI_FINISHPAGE_RUN_TEXT "启动 Markdown Viewer"
!define MUI_FINISHPAGE_LINK "项目主页"
!define MUI_FINISHPAGE_LINK_LOCATION "${PRODUCT_WEB_SITE}"

; ─── Pages ────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE_NSIS.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ─── Languages ────────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ─── Variables ────────────────────────────────────────────────────────────
Var StartMenuFolder

; ─── Install Section ──────────────────────────────────────────────────────
Section "Install" SecMain
  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; 复制所有应用文件
  File /r "dist\MarkdownViewer\*.*"

  ; 创建卸载程序
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; 注册表 - 应用路径
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\MarkdownViewer.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\MarkdownViewer.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoRepair" 1

  ; 文件关联 - .md 文件用 Markdown Viewer 打开
  WriteRegStr HKCR ".md" "" "MarkdownViewer.md"
  WriteRegStr HKCR "MarkdownViewer.md" "" "Markdown File"
  WriteRegStr HKCR "MarkdownViewer.md\DefaultIcon" "" "$INSTDIR\MarkdownViewer.exe,0"
  WriteRegStr HKCR "MarkdownViewer.md\shell\open\command" "" '"$INSTDIR\MarkdownViewer.exe" "%1"'

  ; 也关联 .markdown 和 .mdx 扩展名
  WriteRegStr HKCR ".markdown" "" "MarkdownViewer.md"
  WriteRegStr HKCR ".mdx" "" "MarkdownViewer.md"

  ; 开始菜单
  CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
  CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Markdown Viewer.lnk" "$INSTDIR\MarkdownViewer.exe" "" "$INSTDIR\MarkdownViewer.exe" 0
  CreateShortCut "$SMPROGRAMS\$StartMenuFolder\卸载 Markdown Viewer.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0

  ; 桌面快捷方式（可选）
  CreateShortCut "$DESKTOP\Markdown Viewer.lnk" "$INSTDIR\MarkdownViewer.exe" "" "$INSTDIR\MarkdownViewer.exe" 0

  ; 刷新图标缓存
  System::Call 'shell32.dll::SHChangeNotify(i 0x08000000, i 0, i 0, i 0)'
SectionEnd

; ─── Uninstall Section ────────────────────────────────────────────────────
Section "Uninstall"
  ; 删除应用文件
  RMDir /r "$INSTDIR\*.*"
  RMDir "$INSTDIR"

  ; 删除开始菜单
  RMDir /r "$SMPROGRAMS\$StartMenuFolder"

  ; 删除桌面快捷方式
  Delete "$DESKTOP\Markdown Viewer.lnk"

  ; 删除注册表项
  DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"

  ; 删除文件关联——只在扩展名当前仍指向我们的 ProgID 时才清空，
  ; 避免抹掉用户安装前用其他编辑器建立的 .md 关联。
  ReadRegStr $0 HKCR ".md" ""
  StrCmp $0 "MarkdownViewer.md" 0 +2
    DeleteRegValue HKCR ".md" ""
  ReadRegStr $0 HKCR ".markdown" ""
  StrCmp $0 "MarkdownViewer.md" 0 +2
    DeleteRegValue HKCR ".markdown" ""
  ReadRegStr $0 HKCR ".mdx" ""
  StrCmp $0 "MarkdownViewer.md" 0 +2
    DeleteRegValue HKCR ".mdx" ""
  ; 删除我们自己的 ProgID（整棵子树）
  DeleteRegKey HKCR "MarkdownViewer.md"

  ; 刷新图标缓存
  System::Call 'shell32.dll::SHChangeNotify(i 0x08000000, i 0, i 0, i 0)'
SectionEnd

; ─── Functions ────────────────────────────────────────────────────────────
Function .onInit
  ; 读取开始菜单文件夹
  StrCpy $StartMenuFolder "Markdown Viewer"
FunctionEnd
