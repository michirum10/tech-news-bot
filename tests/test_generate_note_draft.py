"""週次note下書き生成モジュールのテスト"""

import json
import os
import tempfile
import unittest

from bot.generate_note_draft import (
    collect_items,
    generate_markdown,
    generate_note_draft,
    _id_to_link,
)


class TestCollectItems(unittest.TestCase):
    def test_collect_all_sources(self):
        """全ソースからアイテムを収集"""
        seen = {
            "arxiv": ["2401.001", "2401.002"],
            "hn": ["https://news.ycombinator.com/item?id=123"],
            "github_trending": ["openai/whisper"],
            "techcrunch": ["https://techcrunch.com/?p=1"],
            "producthunt": [],
            "lobsters": ["https://lobste.rs/s/abc"],
        }
        items = collect_items(seen)

        self.assertIn("ArXiv", items)
        self.assertIn("Hacker News", items)
        self.assertIn("GitHub Trending", items)
        self.assertIn("TechCrunch", items)
        self.assertIn("Lobsters", items)
        # 空のproducthuntは含まれない
        self.assertNotIn("Product Hunt", items)

    def test_empty_seen(self):
        """空のseen.json"""
        items = collect_items({})
        self.assertEqual(items, {})


class TestGenerateMarkdown(unittest.TestCase):
    def test_basic_structure(self):
        """基本的なMarkdown構造"""
        items = {
            "ArXiv": ["2401.001", "2401.002"],
            "GitHub Trending": ["openai/whisper"],
        }
        md = generate_markdown(items, "2024-01-15週")

        self.assertIn("# 週刊テックニュースまとめ（2024-01-15週）", md)
        self.assertIn("## 今週のトピック一覧", md)
        self.assertIn("今週の収集数: **3件**", md)
        self.assertIn("- ArXiv: 2件", md)
        self.assertIn("- GitHub Trending: 1件", md)
        self.assertIn("## 注目ポイント", md)
        self.assertIn("## 開発への活かし方", md)

    def test_truncates_at_10(self):
        """10件超のソースは省略表記"""
        items = {"ArXiv": [f"2401.{i:03d}" for i in range(15)]}
        md = generate_markdown(items, "2024-01-15週")

        self.assertIn("...他5件", md)


class TestIdToLink(unittest.TestCase):
    def test_arxiv_link(self):
        self.assertEqual(
            _id_to_link("ArXiv", "2401.001"),
            "https://arxiv.org/abs/2401.001",
        )

    def test_hn_link(self):
        url = "https://news.ycombinator.com/item?id=123"
        self.assertEqual(_id_to_link("Hacker News", url), url)

    def test_github_trending_link(self):
        self.assertEqual(
            _id_to_link("GitHub Trending", "openai/whisper"),
            "https://github.com/openai/whisper",
        )

    def test_generic_url(self):
        url = "https://example.com/article"
        self.assertEqual(_id_to_link("TechCrunch", url), url)

    def test_non_url_id(self):
        self.assertEqual(_id_to_link("Unknown", "some-id"), "")


class TestGenerateNoteDraft(unittest.TestCase):
    def test_file_creation(self):
        """ファイルが正しく生成される"""
        with tempfile.TemporaryDirectory() as tmpdir:
            seen_path = os.path.join(tmpdir, "seen.json")
            output_dir = os.path.join(tmpdir, "output")

            seen = {
                "arxiv": ["2401.001"],
                "hn": ["https://news.ycombinator.com/item?id=123"],
                "github_trending": ["openai/whisper"],
            }
            with open(seen_path, "w") as f:
                json.dump(seen, f)

            result_path = generate_note_draft(seen_path, output_dir)

            self.assertTrue(os.path.exists(result_path))
            self.assertTrue(result_path.startswith(output_dir))
            self.assertTrue(result_path.endswith(".md"))

            with open(result_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("週刊テックニュースまとめ", content)
            self.assertIn("ArXiv", content)


if __name__ == "__main__":
    unittest.main()
