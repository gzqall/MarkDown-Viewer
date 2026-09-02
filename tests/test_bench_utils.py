"""pytest-benchmark 基线测试 —— 量化 utils 性能。

运行基准：python -m pytest tests/test_bench_utils.py --benchmark-only
对比基线：加 --benchmark-compare 会和上次保存的结果比（默认 .benchmarks/）。
"""

import pytest

from utils import detect_encoding, parse_frontmatter, count_stats


# ─── detect_encoding 基线（不同文件大小）──────────────────────────────

def test_bench_detect_encoding_small(benchmark, tmp_md):
    """小文件（~100B）：基线参考，主要测固定开销。"""
    p = tmp_md("# hi\n" * 5, name="s.md")
    benchmark(detect_encoding, p)


def test_bench_detect_encoding_medium(benchmark, tmp_path):
    """中等文件（~50KB）。"""
    p = tmp_path / "m.md"
    p.write_text("# title\n\nparagraph here.\n" * 1000, encoding="utf-8")
    benchmark(detect_encoding, str(p))


def test_bench_detect_encoding_large(benchmark, large_md):
    """大文件（~1MB+）：阶段1 异步化的对照基线。"""
    p = large_md(lines=20000)
    benchmark(detect_encoding, p)


# ─── parse_frontmatter / count_stats 基线 ───────────────────────────────

def test_bench_parse_frontmatter(benchmark):
    """frontmatter 解析：万行级正文。"""
    content = "---\ntitle: X\nauthor: Y\n---\n" + "line\n" * 10000
    benchmark(parse_frontmatter, content)


def test_bench_count_stats(benchmark):
    """字数统计：万行级正文（含 CJK）。"""
    body = "你好 world\n" * 5000
    benchmark(count_stats, body)
