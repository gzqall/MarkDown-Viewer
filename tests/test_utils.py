"""utils.py 纯逻辑单元测试 —— 不依赖 Qt GUI。

覆盖 detect_encoding（BOM/utf-8/gbk/utf-16 回退）、get_file_info、MD_EXTENSIONS。
"""

import os

import pytest

from utils import detect_encoding, get_file_info, MD_EXTENSIONS


# ─── detect_encoding ────────────────────────────────────────────────────

class TestDetectEncoding:
    def test_plain_utf8(self, tmp_md):
        p = tmp_md("# 你好 world\n", name="a.md")
        enc, content = detect_encoding(p)
        assert enc == "utf-8"
        assert content == "# 你好 world\n"

    def test_utf8_sig_bom(self, tmp_path):
        p = tmp_path / "bom.md"
        # 写入 UTF-8 BOM 头
        raw = b"\xef\xbb\xbf# bom title\n"
        p.write_bytes(raw)
        enc, content = detect_encoding(str(p))
        assert enc == "utf-8-sig"
        assert content == "# bom title\n"

    def test_utf16_le_bom(self, tmp_path):
        p = tmp_path / "u16.md"
        p.write_bytes(b"\xff\xfe# hi\r\n".encode("utf-16-le") if False else
                      b"\xff\xfe" + "# hi\r\n".encode("utf-16-le"))
        enc, content = detect_encoding(str(p))
        assert enc == "utf-16-le"
        assert "hi" in content

    def test_utf16_be_bom(self, tmp_path):
        p = tmp_path / "u16be.md"
        p.write_bytes(b"\xfe\xff" + "# hi\r\n".encode("utf-16-be"))
        enc, content = detect_encoding(str(p))
        assert enc == "utf-16-be"
        assert "hi" in content

    def test_gbk_fallback(self, tmp_path):
        """写一段 GBK 编码的中文内容（无 BOM，非合法 UTF-8），
        detect_encoding 应回退到 gbk。"""
        p = tmp_path / "gbk.md"
        text = "# 标题\n\n这是 GBK 编码的内容\n"
        p.write_bytes(text.encode("gbk"))
        enc, content = detect_encoding(str(p))
        assert enc == "gbk"
        assert "标题" in content
        assert "GBK" in content

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_bytes(b"")
        enc, content = detect_encoding(str(p))
        # 空文件无 BOM，utf-8 严格模式成功，返回空串
        assert content == ""

    def test_binary_garbage_falls_back(self, tmp_path):
        """纯二进制垃圾（无任何编码能解）应回退 utf-8 + replace。"""
        p = tmp_path / "bin.md"
        p.write_bytes(bytes(range(128, 256)) * 4)
        enc, content = detect_encoding(str(p))
        # 不抛异常、返回内容（含替换字符）即可
        assert isinstance(content, str)


# ─── get_file_info ──────────────────────────────────────────────────────

class TestGetFileInfo:
    def test_basic(self, tmp_md):
        p = tmp_md("# x\n", name="info.md")
        info = get_file_info(p)
        assert info["name"] == "info.md"
        assert os.path.isabs(info["path"])
        assert info["dir"] == os.path.dirname(os.path.abspath(p))
        assert info["size"] == os.path.getsize(p)
        assert "modified" in info
        # modified 是 YYYY-MM-DD HH:MM:SS 格式
        assert len(info["modified"]) == 19

    def test_size_matches(self, tmp_md):
        p = tmp_md("0123456789", name="s.md")  # 10 bytes
        assert get_file_info(p)["size"] == 10


# ─── MD_EXTENSIONS ───────────────────────────────────────────────────────

class TestMdExtensions:
    @pytest.mark.parametrize("ext", [".md", ".mdx", ".markdown", ".mdown", ".mkd", ".mkdn"])
    def test_supported(self, ext):
        assert ext in MD_EXTENSIONS

    @pytest.mark.parametrize("ext", [".txt", ".html", ".pdf", ".MD"])  # 大写不在集合
    def test_unsupported(self, ext):
        # 注意：调用方用 .lower() 处理，这里直接测集合成员
        if ext == ".MD":
            assert ext not in MD_EXTENSIONS  # 集合本身只含小写
        else:
            assert ext not in MD_EXTENSIONS
