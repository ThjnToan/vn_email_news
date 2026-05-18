import feedparser
import html
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from config import NEWS_SOURCES, ARTICLES_PER_SOURCE

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _extract_rss_image(entry) -> str:
    for m in entry.get("media_content", []):
        url = m.get("url", "")
        if url:
            return url
    for m in entry.get("media_thumbnail", []):
        url = m.get("url", "")
        if url:
            return url
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return enc.get("href", enc.get("url", ""))
    raw = entry.get("summary", "") or ""
    if not raw and entry.get("content"):
        raw = entry["content"][0].get("value", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw)
    if m:
        return m.group(1)
    return ""


def _fetch_og_image(article_url: str) -> str:
    if not article_url:
        return ""
    try:
        resp = requests.get(article_url, timeout=6, headers=_HEADERS)
        page = resp.text
        for tag_pattern in [
            r'<meta[^>]*og:image[^>]*/?>',
            r'<meta[^>]*twitter:image[^>]*/?>',
        ]:
            meta = re.search(tag_pattern, page, re.IGNORECASE)
            if meta:
                content = re.search(
                    r'content=["\']([^"\']+)["\']', meta.group(), re.IGNORECASE
                )
                if content:
                    img_url = content.group(1).strip()
                    if img_url and not img_url.startswith("http"):
                        img_url = urljoin(article_url, img_url)
                    if img_url:
                        return img_url
    except Exception:
        pass
    return ""


def _enrich_article_images(articles: list[dict]) -> list[dict]:
    to_fetch = [(i, a) for i, a in enumerate(articles) if a.get("link") and not a.get("image")]
    if not to_fetch:
        return articles
    with ThreadPoolExecutor(max_workers=8) as pool:
        fut = {pool.submit(_fetch_og_image, a["link"]): i for i, a in to_fetch}
        for f in as_completed(fut):
            idx = fut[f]
            img = f.result()
            if img:
                articles[idx]["image"] = img
    return articles


def _fetch_source(url: str, name: str, limit: int) -> list[dict]:
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:limit]:
            title = _clean_text(entry.get("title", ""))
            summary = _clean_text(entry.get("summary", entry.get("description", "")))
            link = entry.get("link", "")
            image = _extract_rss_image(entry)
            if title:
                articles.append({
                    "title": title,
                    "summary": summary[:400],
                    "link": link,
                    "source": name,
                    "image": image,
                })
        if articles:
            articles = _enrich_article_images(articles)
        return articles
    except Exception as e:
        print(f"Warning: could not fetch {name} ({url}): {e}")
        return []


def fetch_all_news() -> dict[str, list[dict]]:
    results = {}
    for section, sources in NEWS_SOURCES.items():
        articles = []
        for src in sources:
            articles.extend(_fetch_source(src["url"], src["name"], ARTICLES_PER_SOURCE))

        image_count = sum(1 for a in articles[:6] if a.get("image"))
        print(f"  [{section}] {len(articles)} articles, {image_count} with images")

        results[section] = articles
    return results