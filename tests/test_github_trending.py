"""GitHub Trendingモジュールのテスト"""

import os
import unittest
from unittest.mock import patch, MagicMock

from bot.github_trending import (
    fetch_github_trending,
    _parse_repo_article,
    format_trending_message,
)

SAMPLE_HTML = """
<article class="Box-row">
  <h2><a href="/openai/whisper">openai / whisper</a></h2>
  <p>Robust Speech Recognition via Large-Scale Weak Supervision</p>
  <span itemprop="programmingLanguage">Python</span>
  <a class="Link--muted d-inline-block mr-3" href="/openai/whisper/stargazers">65,000</a>
  <span class="d-inline-block float-sm-right">1,200 stars today</span>
</article>
<article class="Box-row">
  <h2><a href="/rust-lang/rust">rust-lang / rust</a></h2>
  <p>The Rust Programming Language</p>
  <span itemprop="programmingLanguage">Rust</span>
  <a class="Link--muted d-inline-block mr-3" href="/rust-lang/rust/stargazers">90,000</a>
  <span class="d-inline-block float-sm-right">500 stars today</span>
</article>
"""


class TestFetchGitHubTrending(unittest.TestCase):
    @patch("bot.github_trending.requests.get")
    def test_fetch_success(self, mock_get):
        """正常系：HTMLパースしてリポジトリ情報を取得"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        cfg = {"languages": [""], "since": "daily", "max_results": 10}
        results = fetch_github_trending(cfg)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "openai/whisper")
        self.assertEqual(results[0]["language"], "Python")
        self.assertEqual(results[0]["url"], "https://github.com/openai/whisper")
        self.assertEqual(results[1]["name"], "rust-lang/rust")

    @patch("bot.github_trending.requests.get")
    def test_fetch_deduplication(self, mock_get):
        """複数言語で同じリポジトリが出た場合の重複除去"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        cfg = {"languages": ["", "python"], "since": "daily", "max_results": 10}
        results = fetch_github_trending(cfg)

        # 同じHTMLを2回取得しても重複しない
        self.assertEqual(len(results), 2)

    @patch("bot.github_trending.requests.get")
    def test_fetch_max_results(self, mock_get):
        """max_results制限"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        cfg = {"languages": [""], "since": "daily", "max_results": 1}
        results = fetch_github_trending(cfg)

        self.assertEqual(len(results), 1)

    @patch("bot.github_trending.requests.get")
    def test_fetch_network_error(self, mock_get):
        """ネットワークエラー時は空リスト"""
        import requests as req
        mock_get.side_effect = req.RequestException("timeout")

        cfg = {"languages": [""], "since": "daily", "max_results": 10}
        results = fetch_github_trending(cfg)

        self.assertEqual(results, [])


class TestFormatTrendingMessage(unittest.TestCase):
    def test_full_message(self):
        """全フィールドありのメッセージフォーマット"""
        repo = {
            "id": "openai/whisper",
            "name": "openai/whisper",
            "description": "Speech recognition",
            "language": "Python",
            "stars": "65000",
            "stars_today": "1,200 stars today",
            "url": "https://github.com/openai/whisper",
        }
        msg = format_trending_message(repo)

        self.assertIn("**[GitHub Trending]**", msg)
        self.assertIn("openai/whisper", msg)
        self.assertIn("Python", msg)
        self.assertIn("65000", msg)
        self.assertIn("Speech recognition", msg)
        self.assertIn("https://github.com/openai/whisper", msg)

    def test_minimal_message(self):
        """最低限のフィールドのみ"""
        repo = {
            "id": "user/repo",
            "name": "user/repo",
            "description": "",
            "language": "",
            "stars": "",
            "stars_today": "",
            "url": "https://github.com/user/repo",
        }
        msg = format_trending_message(repo)

        self.assertIn("user/repo", msg)
        self.assertIn("https://github.com/user/repo", msg)


if __name__ == "__main__":
    unittest.main()
