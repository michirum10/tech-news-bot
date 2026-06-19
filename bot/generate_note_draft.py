"""週次note下書きMarkdownを生成する

直近7日分のseen.jsonログ（ArXiv/HN/GitHub Trending等）を集計し、
note記事テンプレートの下書きを生成する。
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List

log = logging.getLogger(__name__)

SEEN_PATH = "seen.json"
OUTPUT_DIR = "output"


def load_seen_data(path: str = SEEN_PATH) -> dict:
    """seen.jsonを読み込む"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_items(seen: dict) -> Dict[str, List[str]]:
    """seen.jsonから各ソースのアイテムを収集する

    seen.jsonはIDリストのみ保持するため、IDをそのまま利用する。
    """
    sources = {
        "ArXiv": seen.get("arxiv", []),
        "Hacker News": seen.get("hn", []),
        "GitHub Trending": seen.get("github_trending", []),
        "TechCrunch": seen.get("techcrunch", []),
        "Product Hunt": seen.get("producthunt", []),
        "Lobsters": seen.get("lobsters", []),
    }
    return {k: v for k, v in sources.items() if v}


def generate_markdown(items: Dict[str, List[str]], week_label: str) -> str:
    """note下書きMarkdownを生成する

    Args:
        items: ソース名 → IDリストの辞書
        week_label: 週ラベル（例: "2024-01-15〜2024-01-21"）

    Returns:
        Markdown文字列
    """
    lines = []
    lines.append(f"# 週刊テックニュースまとめ（{week_label}）")
    lines.append("")
    lines.append("## 今週のトピック一覧")
    lines.append("")

    total = sum(len(v) for v in items.values())
    lines.append(f"今週の収集数: **{total}件**")
    lines.append("")

    for source, ids in items.items():
        lines.append(f"- {source}: {len(ids)}件")
    lines.append("")

    lines.append("---")
    lines.append("")

    # 各ソースの詳細
    for source, ids in items.items():
        lines.append(f"## {source}")
        lines.append("")

        # IDからリンクを生成（可能な場合）
        for item_id in ids[-10:]:  # 直近10件に絞る
            link = _id_to_link(source, item_id)
            if link:
                lines.append(f"- [{item_id}]({link})")
            else:
                lines.append(f"- {item_id}")
        if len(ids) > 10:
            lines.append(f"- ...他{len(ids) - 10}件")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 注目ポイント")
    lines.append("")
    lines.append("<!-- Claude.aiに貼って埋めてもらう -->")
    lines.append("")
    lines.append("1. ")
    lines.append("2. ")
    lines.append("3. ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 開発への活かし方")
    lines.append("")
    lines.append("<!-- Claude.aiに貼って埋めてもらう -->")
    lines.append("")
    lines.append("1. ")
    lines.append("2. ")
    lines.append("3. ")
    lines.append("")

    return "\n".join(lines)


def _id_to_link(source: str, item_id: str) -> str:
    """IDからURLを生成する（可能な場合）"""
    if source == "ArXiv":
        return f"https://arxiv.org/abs/{item_id}"
    elif source == "Hacker News" and item_id.startswith("http"):
        return item_id
    elif source == "GitHub Trending" and "/" in item_id:
        return f"https://github.com/{item_id}"
    elif item_id.startswith("http"):
        return item_id
    return ""


def generate_note_draft(seen_path: str = SEEN_PATH, output_dir: str = OUTPUT_DIR) -> str:
    """メインの下書き生成処理

    Returns:
        生成されたファイルのパス
    """
    seen = load_seen_data(seen_path)
    items = collect_items(seen)

    now = datetime.now()
    week_label = now.strftime("%Y-%m-%d") + "週"
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"note_draft_{timestamp}.md"

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)

    markdown = generate_markdown(items, week_label)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    log.info("Note draft generated: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    path = generate_note_draft()
    print(f"Generated: {path}")
