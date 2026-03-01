RECIPIENT_EMAIL = "thtoan39@gmail.com"

NEWS_SOURCES = {
    "vietnam": [
        {"name": "VnExpress International", "url": "https://e.vnexpress.net/rss/news.rss"},
        {"name": "Tuoi Tre News", "url": "https://tuoitrenews.vn/rss/news.rss"},
    ],
    "global": [
        {"name": "BBC World News", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    ],
    "tech": [
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    ],
    "business": [
        {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
    ],
}

ARTICLES_PER_SOURCE = 4
GEMINI_MODEL = "gemini-2.0-flash"
