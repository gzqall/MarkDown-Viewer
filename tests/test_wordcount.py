"""count_stats 纯函数单元测试（从 window.py._update_word_count 抽出）。"""

from utils import count_stats


class TestCountStats:
    def test_simple_english(self):
        s = count_stats("hello world foo\n")
        assert s["words"] == 3
        assert s["lines"] == 1  # 一个换行符
        assert s["chars"] == len("hello world foo\n")
        assert s["cjk"] == 0

    def test_cjk_counted(self):
        # 中文每个字算一个 CJK；split() 不以中文分词
        body = "你好世界 hello\n"
        s = count_stats(body)
        assert s["cjk"] == 4  # 你好世界
        # words: split 按空白，"你好世界" + "hello" = 2
        assert s["words"] == 2

    def test_empty_body(self):
        s = count_stats("")
        assert s == {"lines": 0, "words": 0, "chars": 0, "cjk": 0}

    def test_multiline(self):
        body = "line1\nline2\nline3\n"
        s = count_stats(body)
        assert s["lines"] == 3

    def test_multiple_spaces_collapsed_in_words(self):
        # split() 会把多空白折叠
        s = count_stats("a   b\t\tc\n")
        assert s["words"] == 3

    def test_only_whitespace(self):
        s = count_stats("   \n  \n")
        assert s["words"] == 0

    def test_fullwidth_range(self):
        """全角空格（　, U+3000）在 CJK 范围内。"""
        body = "test　test\n"  # 全角空格
        s = count_stats(body)
        # 全角空格 '　' 落在 ['　','〿'] 范围
        assert s["cjk"] >= 1

    def test_japanese_kana_in_range(self):
        """平假名 'あ' (U+3042) 在 CJK 范围 ['一','鿿'] 之外但 ['　','〿'] 之外?
        实际 'あ' U+3042 > '〿' U+303F，不计入。验证范围边界行为稳定。"""
        s = count_stats("あ")
        # 'あ' U+3042 不在 ['一','鿿'](4E00-9FFF) 也不在 ['　','〿'](3000-303F)
        # 它在 3040-309F，不计入。记录当前行为即可。
        assert s["cjk"] == 0
