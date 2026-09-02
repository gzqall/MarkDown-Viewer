"""parse_frontmatter 纯函数单元测试（从 window.py 抽出，阶段1 去重）。"""

from utils import parse_frontmatter


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        fm, body = parse_frontmatter("# Title\n\ntext\n")
        assert fm == {}
        assert body == "# Title\n\ntext\n"

    def test_simple_frontmatter(self):
        content = "---\ntitle: My Doc\nauthor: Bob\n---\n# Body\n\ntext\n"
        fm, body = parse_frontmatter(content)
        assert fm["title"] == "My Doc"
        assert fm["author"] == "Bob"
        assert body == "# Body\n\ntext\n"

    def test_quoted_values(self):
        content = '---\ntitle: "Quoted Title"\ntag: \'single\'\n---\nbody\n'
        fm, body = parse_frontmatter(content)
        assert fm["title"] == "Quoted Title"
        assert fm["tag"] == "single"
        assert body == "body\n"

    def test_keys_lowercased(self):
        content = "---\nTitle: X\nAUTHOR: Y\n---\nb\n"
        fm, _ = parse_frontmatter(content)
        assert "title" in fm and "author" in fm
        assert "Title" not in fm

    def test_value_without_colon(self):
        """无冒号的行应被忽略，不崩。"""
        content = "---\nbroken line no colon\ntitle: ok\n---\nbody\n"
        fm, body = parse_frontmatter(content)
        assert fm == {"title": "ok"}
        assert body == "body\n"

    def test_three_dashes_in_body_not_frontmatter(self):
        """正文里的 --- 不应被误判（不以 --- 开头）。"""
        content = "# Title\n\n---\n\ntext\n"
        fm, body = parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_empty_frontmatter(self):
        """空 frontmatter（--- 紧跟 ---）不匹配正则（需中间有内容行），
        原样返回 —— 记录当前实现行为。"""
        content = "---\n---\nbody only\n"
        fm, body = parse_frontmatter(content)
        assert fm == {}
        assert body == content  # 不被误剥

    def test_not_starting_with_dashes(self):
        """首行不是 ---，原样返回。"""
        content = "not frontmatter\n---\nx\n"
        fm, body = parse_frontmatter(content)
        assert fm == {}
        assert body == content
