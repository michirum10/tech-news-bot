# tech-news-bot

AI/LLM関連のテックニュースを自動収集し、Discordに通知するBot。

## 機能

| ソース | 内容 | 頻度 |
|--------|------|------|
| arXiv | cs.AI/cs.CL分野の新着論文 | 日次 |
| Hacker News | 高スコア記事 | 日次 |
| TechCrunch / Product Hunt / Lobsters | AI関連RSS | 日次 |
| GitHub Trending | 人気リポジトリ (全言語/Python) | 日次 |
| 週次note下書き | 収集データのMarkdownまとめ | 週次(月曜) |

## アーキテクチャ

```
main.py              … メイン実行スクリプト（日次収集・Discord通知）
bot/
  github_trending.py … GitHub Trendingスクレイピング
  generate_note_draft.py … 週次note下書きMarkdown生成
config.json          … 各ソースの設定
seen.json            … 既読ID管理（重複通知防止）
output/              … 週次note下書き出力先
.github/workflows/
  watch.yml          … 日次実行ワークフロー (毎日23:00 UTC)
  weekly_note.yml    … 週次note下書き生成 (毎週月曜0:00 UTC)
```

## セットアップ

### 必要な環境変数（GitHub Secrets）

| 変数名 | 用途 |
|--------|------|
| `DISCORD_WEBHOOK_ARXIV` | arXiv通知用Webhook URL |
| `DISCORD_WEBHOOK_HN` | Hacker News通知用Webhook URL |
| `DISCORD_WEBHOOK_TECH` | TechCrunch/PH/Lobsters通知用Webhook URL |
| `DISCORD_WEBHOOK_TRENDING` | GitHub Trending通知用Webhook URL（未設定時はTECHと共用） |
| `GEMINI_API_KEY` | Gemini APIキー（要約・翻訳用） |

### ローカル実行

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_ARXIV="..."
export GEMINI_API_KEY="..."
python main.py
```

### 週次note下書き生成

```bash
python -m bot.generate_note_draft
# output/note_draft_YYYYMMDD_HHMMSS.md が生成される
```

## 設定 (config.json)

### github_trending

```json
{
  "github_trending": {
    "languages": ["", "python"],
    "since": "daily",
    "max_results": 20
  }
}
```

- `languages`: 取得対象言語。空文字列 `""` は全言語。
- `since`: 期間 (`daily` / `weekly` / `monthly`)
- `max_results`: 取得上限数

## テスト

```bash
pip install pytest
python -m pytest tests/ -v
```
