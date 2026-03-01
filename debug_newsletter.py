"""
Run this locally to inspect the newsletter HTML without sending email.
Output: debug_output.html — open it in a browser to see exactly what
would be emailed, including whether images load.

Usage:
  set ANTHROPIC_API_KEY=your_key
  python debug_newsletter.py
"""
import os
import sys
from newsletter.fetch_news import fetch_all_news
from newsletter.generate import generate_newsletter


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY first.")
        sys.exit(1)

    print("=== Fetching news ===")
    news = fetch_all_news()

    print("\n=== Images found per section ===")
    for section, articles in news.items():
        if articles:
            img = articles[0].get("image", "")
            print(f"  [{section}] lead article: {articles[0]['title'][:60]}")
            print(f"           image: {img if img else '*** NONE ***'}")

    print("\n=== Generating newsletter ===")
    html = generate_newsletter(news)

    out_path = os.path.join(os.path.dirname(__file__), "debug_output.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nSaved to: {out_path}")
    print("Open debug_output.html in your browser to inspect.")
    print("\n=== <img> tags in output ===")
    import re
    imgs = re.findall(r'<img[^>]+>', html)
    if imgs:
        for img in imgs:
            print(" ", img[:120])
    else:
        print("  *** NO <img> TAGS FOUND IN OUTPUT ***")


if __name__ == "__main__":
    main()
