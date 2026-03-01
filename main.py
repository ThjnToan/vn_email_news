from newsletter.fetch_news import fetch_all_news
from newsletter.generate import generate_newsletter
from newsletter.send_email import send_newsletter


def main():
    print("Fetching news...")
    news = fetch_all_news()
    total = sum(len(v) for v in news.values())
    print(f"Fetched {total} articles across {len(news)} sections")

    print("Generating newsletter with Claude...")
    html = generate_newsletter(news)
    print(f"Generated {len(html)} characters of HTML")

    print("Sending email...")
    send_newsletter(html)
    print("Done.")


if __name__ == "__main__":
    main()
