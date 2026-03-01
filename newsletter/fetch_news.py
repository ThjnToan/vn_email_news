import feedparser
import html
import re
from config import NEWS_SOURCES, ARTICLES_PER_SOURCE


def _clean_text(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _fetch_source(url: str, name: str, limit: int) -> list[dict]:
    """Fetch and parse a single RSS feed, returning up to `limit` articles."""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:limit]:
            title = _clean_text(entry.get("title", ""))
            summary = _clean_text(entry.get("summary", entry.get("description", "")))
            link = entry.get("link", "")
            if title:
                articles.append({"title": title, "summary": summary[:400], "link": link, "source": name})
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
