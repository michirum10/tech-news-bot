"""GitHub Trendingページをスクレイピングして人気リポジトリを取得する"""

import logging
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending"


def fetch_github_trending(cfg: dict) -> List[Dict[str, str]]:
    """GitHub Trendingからリポジトリ情報を取得する

    Args:
        cfg: config.jsonのgithub_trending設定
             - languages: 取得対象の言語リスト (例: ["", "python"])
               空文字列は全言語を意味する
             - since: 期間 (daily/weekly/monthly)
             - max_results: 取得上限数

    Returns:
        リポジトリ情報の辞書リスト
    """
    languages = cfg.get("languages", ["", "python"])
    since = cfg.get("since", "daily")
    max_results = cfg.get("max_results", 20)

    results = []
    seen_repos = set()

    for lang in languages:
        url = f"{TRENDING_URL}/{lang}?since={since}"
        log.info("Fetching GitHub Trending: %s", url)

        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (compatible; tech-news-bot)"
            })
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.error("GitHub Trending fetch failed (%s): %s", lang or "all", exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.Box-row")

        for article in articles:
            repo = _parse_repo_article(article)
            if repo and repo["id"] not in seen_repos:
                seen_repos.add(repo["id"])
                results.append(repo)

    results = results[:max_results]
    log.info("GitHub Trending: %d repos found", len(results))
    return results


def _parse_repo_article(article) -> Dict[str, str] | None:
    """article要素から1リポジトリの情報をパースする"""
    # リポジトリ名（owner/name）
    h2 = article.select_one("h2")
    if not h2:
        return None
    link = h2.select_one("a")
    if not link:
        return None

    repo_path = link.get("href", "").strip("/")
    if not repo_path:
        return None

    # 説明文
    desc_tag = article.select_one("p")
    description = desc_tag.get_text(strip=True) if desc_tag else ""

    # 言語
    lang_span = article.select_one("[itemprop='programmingLanguage']")
    language = lang_span.get_text(strip=True) if lang_span else ""

    # スター数（今日/今週/今月の増加分）
    stars_today = ""
    star_spans = article.select("span.d-inline-block.float-sm-right")
    if star_spans:
        stars_today = star_spans[0].get_text(strip=True)

    # 総スター数
    total_stars = ""
    star_links = article.select("a.Link--muted.d-inline-block.mr-3")
    if star_links:
        total_stars = star_links[0].get_text(strip=True).replace(",", "")

    return {
        "id": repo_path,
        "name": repo_path,
        "description": description,
        "language": language,
        "stars": total_stars,
        "stars_today": stars_today,
        "url": f"https://github.com/{repo_path}",
    }


def format_trending_message(repo: Dict[str, str]) -> str:
    """Discord通知用のメッセージをフォーマットする"""
    parts = [f"**[GitHub Trending]** {repo['name']}"]

    meta = []
    if repo.get("language"):
        meta.append(repo["language"])
    if repo.get("stars"):
        meta.append(f"⭐ {repo['stars']}")
    if repo.get("stars_today"):
        meta.append(f"({repo['stars_today']})")
    if meta:
        parts.append(" | ".join(meta))

    if repo.get("description"):
        parts.append(repo["description"][:150])

    parts.append(repo["url"])

    return "\n".join(parts)
