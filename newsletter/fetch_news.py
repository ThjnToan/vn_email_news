import feedparser
import html
import re
from config import NEWS_SOURCES, ARTICLES_PER_SOURCE


def _clean_text(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _extract_image(entry) -> str:
    """Try to pull an image URL from various RSS image fields."""
    # media:content (most common)
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            url = m.get("url", "")
            if url and any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                return url
        # accept any url if no extension match
        url = entry.media_content[0].get("url", "")
        if url:
            return url

    # media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get("url", "")
        if url:
            return url

    # enclosures (podcasts / image enclosures)
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/"):
                return enc.get("href", enc.get("url", ""))

    # <img> tag buried inside summary / content HTML
    raw = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw)
    if match:
        return match.group(1)

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
            image = _extract_image(entry)
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
        results[section] = articles
    return results
