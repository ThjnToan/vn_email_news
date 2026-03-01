import feedparser
import html
import re
import requests
from config import NEWS_SOURCES, ARTICLES_PER_SOURCE

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0)"}


def _clean_text(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _extract_rss_image(entry) -> str:
    """Try to pull an image URL from RSS feed fields (fast, no HTTP request)."""
    # media:content
    for m in entry.get("media_content", []):
        url = m.get("url", "")
        if url:
            return url

    # media:thumbnail
    for m in entry.get("media_thumbnail", []):
        url = m.get("url", "")
        if url:
            return url

    # enclosures
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return enc.get("href", enc.get("url", ""))

    # <img> tag buried in summary/content HTML
    raw = entry.get("summary", "") or ""
    if not raw and entry.get("content"):
        raw = entry["content"][0].get("value", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw)
    if match:
        return match.group(1)

    return ""


def _fetch_og_image(url: str) -> str:
    """Fetch the article page and extract the og:image meta tag."""
    if not url:
        return ""
    try:
        resp = requests.get(url, timeout=7, headers=_HEADERS)
        # Try both attribute orderings of the meta tag
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]
        for pat in patterns:
            m = re.search(pat, resp.text)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"Warning: og:image fetch failed for {url}: {e}")
    return ""


def _fetch_source(url: str, name: str, limit: int) -> list[dict]:
    """Fetch and parse a single RSS feed, returning up to `limit` articles."""
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
                    "summary": summary[:500],
                    "link": link,
                    "source": name,
                    "image": image,
                })
        return articles
    except Exception as e:
        print(f"Warning: could not fetch {name} ({url}): {e}")
        return []


def fetch_all_news() -> dict[str, list[dict]]:
    """Return a dict keyed by section with lists of article dicts."""
    results = {}
    for section, sources in NEWS_SOURCES.items():
        articles = []
        for src in sources:
            articles.extend(_fetch_source(src["url"], src["name"], ARTICLES_PER_SOURCE))

        # Guarantee the lead article (index 0) has an image via og:image scraping
        if articles and not articles[0]["image"]:
            print(f"Fetching og:image for lead article in [{section}]: {articles[0]['title'][:60]}")
            articles[0]["image"] = _fetch_og_image(articles[0]["link"])

        results[section] = articles
    return results
