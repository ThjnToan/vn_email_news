import os
import sys
import re
import requests
from datetime import datetime
from newsletter.fetch_news import fetch_all_news
from newsletter.generate import generate_newsletter
from newsletter.send_email import send_newsletter
from config import WEATHER_CITIES


def _fetch_weather() -> str:
    parts = []
    for city in WEATHER_CITIES:
        try:
            url = f"https://wttr.in/{city}?format=%C+%t+%h&lang=vi"
            r = requests.get(url, timeout=8,
                            headers={"User-Agent": "curl/8.0"})
            if r.status_code == 200:
                text = r.text.strip()
                city_name = city.replace("+", " ").replace("Ho Chi Minh City", "TP. HCM")
                parts.append(f"{city_name}: {text}")
        except Exception:
            pass
    return " | ".join(parts) if parts else ""


def main():
    print("=" * 50)
    print("  BẢN TIN HÀNG NGÀY — NEWSLETTER GENERATOR")
    print("=" * 50)

    print("\n[1/4] Fetching weather...")
    weather = _fetch_weather()
    print(f"  Weather: {weather}" if weather else "  Weather: unavailable (continuing)")

    print("\n[2/4] Fetching news...")
    try:
        news = fetch_all_news()
        total = sum(len(v) for v in news.values())
        print(f"  Fetched {total} articles across {len(news)} sections")
    except Exception as e:
        print(f"  FATAL: News fetch failed: {e}")
        sys.exit(1)

    print("\n[3/4] Generating newsletter with Claude...")
    try:
        html, text = generate_newsletter(news, weather)
        print(f"  Generated {len(html)} chars HTML, {len(text)} chars plain text")
    except Exception as e:
        print(f"  FATAL: Newsletter generation failed: {e}")
        sys.exit(1)

    print("\n[4/4] Sending email...")
    try:
        send_newsletter(html, text)
    except Exception as e:
        print(f"  FATAL: Email send failed: {e}")
        sys.exit(1)

    save_path = os.environ.get("NEWSLETTER_OUTPUT_DIR", "")
    if save_path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(save_path, exist_ok=True)
        out_file = os.path.join(save_path, f"newsletter-{date_str}.html")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html)
        # Also save latest copy
        latest = os.path.join(save_path, "latest.html")
        with open(latest, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Saved archive to {out_file}")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()