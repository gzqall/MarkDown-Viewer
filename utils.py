"""
Markdown Viewer — 公共工具模块
"""

import os
import re
import time

# 支持的 Markdown 扩展名
MD_EXTENSIONS = {'.md', '.mdx', '.markdown', '.mdown', '.mkd', '.mkdn'}

# frontmatter 起止标记正则（模块级编译一次，避免每次调用重编译）
_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

# 编码检测优先级列表
_ENCODINGS = ['utf-8', 'gbk', 'gb18030', 'utf-16-le', 'utf-16-be', 'utf-8-sig']


def detect_encoding(path):
    """尝试检测文件编码，返回 (encoding, content)

    1. 先检测 BOM 头
    2. 尝试 UTF-8 严格模式（最常用，优先）
    3. 尝试其他编码
    4. 最后回退到 UTF-8 带替换字符
    """
    # 检测 BOM
    with open(path, 'rb') as f:
        raw = f.read(4)
    if raw[:3] == b'\xef\xbb\xbf':
        return 'utf-8-sig', _read_with(path, 'utf-8-sig')
    if raw[:2] == b'\xff\xfe':
        return 'utf-16-le', _read_with(path, 'utf-16-le')
    if raw[:2] == b'\xfe\xff':
        return 'utf-16-be', _read_with(path, 'utf-16-be')

    # 尝试 UTF-8 严格模式（最常用）
    try:
        with open(path, 'r', encoding='utf-8') as f:
            c = f.read()
        return 'utf-8', c
    except UnicodeDecodeError:
        pass

    # 尝试其他编码
    for enc in _ENCODINGS:
        if enc == 'utf-8':
            continue
        try:
            return enc, _read_with(path, enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # 最后回退：UTF-8 带替换字符
    return 'utf-8', _read_with(path, 'utf-8', errors='replace')


def _read_with(path, encoding, errors='strict'):
    with open(path, 'r', encoding=encoding, errors=errors) as f:
        return f.read()


def get_file_info(path):
    """获取文件的基本信息"""
    stat = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "name": os.path.basename(path),
        "dir": os.path.dirname(os.path.abspath(path)),
        "size": stat.st_size,
        "modified": time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
        ),
    }


def parse_frontmatter(content):
    """解析 YAML frontmatter，返回 (frontmatter_dict, body)。

    纯函数（从 window.py.MainWindow._parse_frontmatter 抽出，便于单测/复用）。
    仅做最简 key: value 解析；值去首尾引号。无 frontmatter 时返回 ({}, content)。
    """
    fm = {}
    body = content
    if content.startswith('---'):
        match = _FRONTMATTER_RE.match(content)
        if match:
            fm_text = match.group(1)
            body = content[match.end():]
            for line in fm_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, _, val = line.partition(':')
                    key = key.strip().lower()
                    val = val.strip().strip('"').strip("'")
                    fm[key] = val
    return fm, body


def count_stats(body):
    """统计正文字数/行数/字符数/CJK 字数。纯函数。

    参数 body 应是已剥除 frontmatter 的正文。返回 dict:
      {lines, words, chars, cjk}
    """
    lines = body.count('\n')
    chars = len(body)
    words = len(body.split())
    cjk = sum(1 for c in body if '一' <= c <= '鿿' or '　' <= c <= '〿')
    return {"lines": lines, "words": words, "chars": chars, "cjk": cjk}