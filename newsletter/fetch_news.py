import feedparser
import html
import re
import requests
from urllib.parse import urljoin
from config import NEWS_SOURCES, ARTICLES_PER_SOURCE

# Full browser-like headers to avoid being blocked
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _extract_rss_image(entry) -> str:
    """Pull image from RSS feed fields (no HTTP request needed)."""
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
    """Fetch article page and extract og:image or twitter:image."""
    if not article_url:
        return ""
    try:
        resp = requests.get(article_url, timeout=8, headers=_HEADERS)
        page = resp.text

        # Two-step: find any <meta> tag that contains og:image or twitter:image,
        # then pull the content= value from it. Much more robust than one regex.
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
                    # Make relative URLs absolute
                    if img_url and not img_url.startswith("http"):
                        img_url = urljoin(article_url, img_url)
                    if img_url:
                        return img_url

        print(f"  og:image not found on page: {article_url[:70]}")
    except Exception as e:
        print(f"  og:image fetch error ({article_url[:60]}): {e}")
    return ""


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
    results = {}
    for section, sources in NEWS_SOURCES.items():
        articles = []
        for src in sources:
            articles.extend(_fetch_source(src["url"], src["name"], ARTICLES_PER_SOURCE))

        # Find an image for the lead article — try up to 3 articles per section
        image_found = False
        for i, article in enumerate(articles[:3]):
            if article["image"]:
                print(f"  [{section}] RSS image found on article {i}: {article['image'][:70]}")
                # Move image-bearing article to front if it's not already there
                if i > 0:
                    articles[0]["image"] = article["image"]
                image_found = True
                break

        if not image_found:
            # Fall back to og:image scraping for first 3 articles
            for i, article in enumerate(articles[:3]):
                print(f"  [{section}] Trying og:image for article {i}: {article['title'][:55]}")
                img = _fetch_og_image(article["link"])
                if img:
                    articles[0]["image"] = img
                    print(f"  [{section}] og:image SUCCESS: {img[:70]}")
                    image_found = True
                    break

        if not image_found:
            print(f"  [{section}] WARNING: No image found for any lead article")

        results[section] = articles
    return results
