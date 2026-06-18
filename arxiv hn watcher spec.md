# arXiv + Hacker News 監視bot 仕様書（Claude Code 用指示書）

## 目的
arXiv（キーワード絞り）と Hacker News（高ポイント絞り）の新着を1日1回取得し、
新着だけを Discord に通知する。記事ネタ・研究ネタのストックが目的。
arXivの英語abstractは Gemini 無料枠で「日本語要約」に変換して通知する。

## 制約・方針
- 実行基盤は完全無料・サーバー不要（GitHub Actions の cron）
- 言語：Python
- 要約は Gemini Flash-Lite 無料枠（翻訳APIは経由しない／翻訳＋要約を一発で実行）
  - arXivは公開論文のため無料枠の学習利用は問題なし
- 二重通知を避けるため既読IDを `seen.json` に保存しリポジトリへコミット
- 通知頻度：1日1回（日本時間の朝）

## ファイル構成
```
arxiv-hn-watcher/
├── .github/workflows/watch.yml   # cron 定期実行
├── main.py                       # 取得・差分判定・要約・Discord通知・seen更新
├── seen.json                     # 既読ID（初期は {"arxiv": [], "hn": []}）
├── config.json                   # キーワード・要約設定
└── requirements.txt              # feedparser, requests, google-genai
```

## config.json（設定値・ここを編集すれば挙動が変わる）
```json
{
  "arxiv": {
    "categories": ["cs.AI", "cs.CL"],
    "keywords": ["distillation", "LoRA", "retrieval augmented", "LLM agent"],
    "max_results": 30
  },
  "hn": {
    "min_points": 100
  },
  "summarize": {
    "enabled": true,
    "provider": "gemini",
    "model": "gemini-2.5-flash-lite",
    "lang": "ja",
    "style": "3行・専門用語は英語のまま残す",
    "translate_hn_titles": true
  }
}
```
※キーワードはOR検索。要約を切りたいときは summarize.enabled を false に。

## データソース仕様
### arXiv（公式API・Atom形式）
- エンドポイント：`http://export.arxiv.org/api/query`
- クエリ例：`search_query=(cat:cs.AI OR cat:cs.CL) AND (all:distillation OR all:LoRA)`
  ＋ `sortBy=submittedDate&sortOrder=descending&max_results=30`
- feedparser でパースし、各 entry の `id`(=arXiv ID), `title`, `authors`, `summary`(=abstract), `link` を取得

### Hacker News（hnrss.org・フィルタ付きRSS）
- URL：`https://hnrss.org/frontpage?points=100`（config の min_points を反映）
- feedparser でパースし、`id`/`link`, `title`, `comments` を取得

## 要約処理（Gemini 無料枠）
- SDK：google-genai。APIキーは環境変数 `GEMINI_API_KEY`
- モデル：config の model（既定 gemini-2.5-flash-lite）
- 重要：**新着の全arXiv論文を1リクエストにまとめて要約**してRPD/TPMを節約する
  - 入力：論文ごとに {id, title, abstract} を並べる
  - プロンプト指示：
    「各論文を日本語で3行に要約。手法と新規性を中心に。専門用語(LoRA等)は英語のまま。
     出力は JSON 配列のみ。前置き・コードフェンス禁止。要素は {id, summary_ja}。」
  - 返却JSONをパースし、id で元データに紐付け
- HNタイトルは translate_hn_titles が true のとき、同じ要領でまとめて日本語訳
- 失敗時フォールバック：要約に失敗しても通知自体は止めない（原文abstractの冒頭120字を代わりに表示）
- 429（レート超過）時は指数バックオフ（1s,2s,4s,8s）でリトライ

## 処理フロー（main.py）
1. config.json と seen.json を読み込む
2. arXiv API・HN RSS を取得
3. seen.json に無いIDだけを「新着」として抽出
4. 新着arXivがあれば Gemini でまとめて日本語要約（HNタイトルも任意で和訳）
5. Discord に整形して投稿（新着が無ければ何もしない）
6. 通知したIDを seen.json に追記し、リポジトリへコミット
7. 取得・パース失敗時はエラーログを出し非ゼロ終了（要約失敗は除く＝通知は継続）

## Discord 通知フォーマット
- arXiv：`*[arXiv]* 原題` / 日本語要約3行 / 著者(先頭3名) / リンク
- HN：`*[HN]* 原題（和訳）`（◯points） / 記事リンク / コメントリンク
チャンネル設計（拡張を見越した構成）:
  #arxiv-ai → arXiv新着  #hn-dev → HN新着  (将来: #music-events 等)
  チャンネルごとに独立したWebhook URLを発行し、Secret名も分ける:
  DISCORD_WEBHOOK_ARXIV / DISCORD_WEBHOOK_HN

payload形式: Discord は content キーでテキスト投稿
  Slack: {"text": "..."} → Discord: {"content": "..."}  呼び方は同じ
  requests.post(webhook_url, json={"content": msg})

## cron 設定（watch.yml）
- 日本時間 朝8時 = UTC 23:00 → `cron: '0 23 * * *'`
- 補足：GitHub Actions の cron は混雑時に数分〜十数分遅延しうる。1日1回なら実害なし
- `seen.json` をコミットするため workflow に `contents: write` 権限と git commit ステップが必要

## 人間が事前にやること（Claude Codeでは完結しない部分）
1. GitHub に空の private リポジトリを作成
2. Discord でサーバーとチャンネルを作成し Webhook URL を取得
3. Google AI Studio で Gemini APIキーを発行（クレカ不要・無料枠）
   - 検証用に「課金を有効化していないプロジェクト」を使う（有効化すると無料枠が消える点に注意）
4. リポジトリの Secrets（Settings → Secrets and variables → Actions）に登録：
   - `DISCORD_WEBHOOK_ARXIV`
   - `DISCORD_WEBHOOK_HN`
   - `GEMINI_API_KEY`
5. このリポジトリを Claude Code で開き、本仕様書を渡して実装させる

## 受け入れ確認
- 手動実行（workflow_dispatch）で Discord に「日本語要約付き」新着が届く
- 2回連続実行で同じ記事が再通知されない（seen.json が効く）
- summarize.enabled=false にすると原文abstractのまま通知される
- キーワードを変えると通知内容が変わる

## 将来の拡張（今はやらない）
- HN記事の本文取得→本文要約（記事ページのfetchが必要でスコープ拡大）
- 監視対象の追加（PyPI新バージョン、特定ブログのRSS 等）
- 重要度スコアリング・スレッド化
