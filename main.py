import json
import os
import sys
import time
import logging
from urllib.parse import quote

import feedparser
import requests
from google import genai

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SEEN_PATH = "seen.json"
CONFIG_PATH = "config.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_arxiv(cfg):
    cats = " OR ".join(f"cat:{c}" for c in cfg["categories"])
    kws = " OR ".join(f"all:{k}" for k in cfg["keywords"])
    query = f"({cats}) AND ({kws})"
    url = (
        f"http://export.arxiv.org/api/query?search_query={quote(query)}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={cfg['max_results']}"
    )
    log.info("Fetching arXiv: %s", url)
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"arXiv fetch failed: {feed.bozo_exception}")
    results = []
    for e in feed.entries:
        arxiv_id = e.id.split("/abs/")[-1]
        authors = [a.get("name", "") for a in e.get("authors", [])]
        results.append({
            "id": arxiv_id,
            "title": " ".join(e.title.split()),
            "abstract": " ".join(e.summary.split()),
            "authors": authors,
            "link": e.link,
        })
    return results


def fetch_hn(cfg):
    url = f"https://hnrss.org/frontpage?points={cfg['min_points']}"
    log.info("Fetching HN: %s", url)
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"HN fetch failed: {feed.bozo_exception}")
    results = []
    for e in feed.entries:
        entry_id = e.get("id") or e.get("link", "")
        comments = e.get("comments", "")
        results.append({
            "id": entry_id,
            "title": e.title,
            "link": e.link,
            "comments": comments,
        })
    return results


def filter_new(entries, seen_ids, key="id"):
    seen_set = set(seen_ids)
    return [e for e in entries if e[key] not in seen_set]


def call_gemini_with_retry(client, model, prompt, max_retries=4):
    for attempt in range(max_retries + 1):
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return resp.text
        except Exception as exc:
            if "429" in str(exc) and attempt < max_retries:
                wait = 2 ** attempt
                log.warning("Rate limited, retrying in %ds...", wait)
                time.sleep(wait)
                continue
            raise


def summarize_arxiv(papers, cfg_sum):
    if not papers:
        return {}
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.warning("GEMINI_API_KEY not set, skipping summarization")
        return {}

    client = genai.Client(api_key=api_key)
    model = cfg_sum.get("model", "gemini-2.5-flash-lite")
    style = cfg_sum.get("style", "3行")

    items = []
    for p in papers:
        items.append({"id": p["id"], "title": p["title"], "abstract": p["abstract"]})

    prompt = (
        f"以下の論文リストを日本語で要約してください。\n"
        f"スタイル: {style}\n"
        f"各論文を日本語で3行に要約。手法と新規性を中心に。専門用語(LoRA等)は英語のまま。\n"
        f"出力は JSON 配列のみ。前置き・コードフェンス禁止。要素は {{\"id\": \"...\", \"summary_ja\": \"...\"}}。\n\n"
        f"{json.dumps(items, ensure_ascii=False)}"
    )

    try:
        text = call_gemini_with_retry(client, model, prompt)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        summaries = json.loads(text)
        return {s["id"]: s["summary_ja"] for s in summaries}
    except Exception as exc:
        log.warning("Summarization failed: %s", exc)
        return {}


def translate_hn_titles(entries, cfg_sum):
    if not entries:
        return {}
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {}

    client = genai.Client(api_key=api_key)
    model = cfg_sum.get("model", "gemini-2.5-flash-lite")

    items = [{"id": e["id"], "title": e["title"]} for e in entries]
    prompt = (
        "以下のHacker Newsタイトルを日本語に翻訳してください。\n"
        "出力は JSON 配列のみ。前置き・コードフェンス禁止。要素は {\"id\": \"...\", \"title_ja\": \"...\"}。\n\n"
        f"{json.dumps(items, ensure_ascii=False)}"
    )

    try:
        text = call_gemini_with_retry(client, model, prompt)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        translations = json.loads(text)
        return {t["id"]: t["title_ja"] for t in translations}
    except Exception as exc:
        log.warning("HN title translation failed: %s", exc)
        return {}


def post_discord(webhook_url, message):
    if not webhook_url:
        log.warning("Webhook URL not set, skipping notification")
        return
    resp = requests.post(webhook_url, json={"content": message}, timeout=30)
    resp.raise_for_status()


def format_arxiv_message(paper, summary_ja):
    authors = paper["authors"][:3]
    author_str = ", ".join(authors)
    if len(paper["authors"]) > 3:
        author_str += " et al."

    if summary_ja:
        body = summary_ja
    else:
        body = paper["abstract"][:120] + "..."

    return (
        f"**[arXiv]** {paper['title']}\n"
        f"{body}\n"
        f"Authors: {author_str}\n"
        f"{paper['link']}"
    )


def format_hn_message(entry, title_ja):
    title_part = f"**[HN]** {entry['title']}"
    if title_ja:
        title_part += f"（{title_ja}）"

    lines = [title_part]
    lines.append(entry["link"])
    if entry.get("comments"):
        lines.append(f"Comments: {entry['comments']}")

    return "\n".join(lines)


def main():
    config = load_json(CONFIG_PATH)
    seen = load_json(SEEN_PATH)

    errors = []

    try:
        arxiv_entries = fetch_arxiv(config["arxiv"])
    except Exception as exc:
        log.error("arXiv fetch error: %s", exc)
        errors.append(str(exc))
        arxiv_entries = []

    try:
        hn_entries = fetch_hn(config["hn"])
    except Exception as exc:
        log.error("HN fetch error: %s", exc)
        errors.append(str(exc))
        hn_entries = []

    new_arxiv = filter_new(arxiv_entries, seen.get("arxiv", []))
    new_hn = filter_new(hn_entries, seen.get("hn", []))

    log.info("New arXiv: %d, New HN: %d", len(new_arxiv), len(new_hn))

    cfg_sum = config.get("summarize", {})
    summaries = {}
    hn_translations = {}

    if cfg_sum.get("enabled", False):
        if new_arxiv:
            summaries = summarize_arxiv(new_arxiv, cfg_sum)
        if new_hn and cfg_sum.get("translate_hn_titles", False):
            hn_translations = translate_hn_titles(new_hn, cfg_sum)

    webhook_arxiv = os.environ.get("DISCORD_WEBHOOK_ARXIV", "")
    webhook_hn = os.environ.get("DISCORD_WEBHOOK_HN", "")

    for paper in new_arxiv:
        summary_ja = summaries.get(paper["id"], "")
        msg = format_arxiv_message(paper, summary_ja)
        try:
            post_discord(webhook_arxiv, msg)
        except Exception as exc:
            log.error("Discord post failed (arXiv): %s", exc)
            errors.append(str(exc))

    for entry in new_hn:
        title_ja = hn_translations.get(entry["id"], "")
        msg = format_hn_message(entry, title_ja)
        try:
            post_discord(webhook_hn, msg)
        except Exception as exc:
            log.error("Discord post failed (HN): %s", exc)
            errors.append(str(exc))

    notified_arxiv_ids = [p["id"] for p in new_arxiv]
    notified_hn_ids = [e["id"] for e in new_hn]
    seen["arxiv"] = seen.get("arxiv", []) + notified_arxiv_ids
    seen["hn"] = seen.get("hn", []) + notified_hn_ids
    save_json(SEEN_PATH, seen)
    log.info("Updated seen.json: +%d arXiv, +%d HN", len(notified_arxiv_ids), len(notified_hn_ids))

    if errors:
        log.error("Finished with errors: %s", errors)
        sys.exit(1)


if __name__ == "__main__":
    main()
