import os
from datetime import datetime
import anthropic
from config import CLAUDE_MODEL

SECTION_LABELS = {
    "vietnam": "VIETNAM TODAY",
    "global": "WORLD WATCH",
    "tech": "TECH & SCIENCE",
    "business": "MARKETS & BUSINESS",
}


def _format_articles_for_prompt(news: dict[str, list[dict]]) -> str:
    lines = []
    for section, articles in news.items():
        label = SECTION_LABELS.get(section, section.upper())
        lines.append(f"\n=== {label} ===")
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. [{a['source']}] {a['title']}")
            if a["summary"]:
                lines.append(f"   Summary: {a['summary']}")
    return "\n".join(lines)


def _build_prompt(news: dict[str, list[dict]], date_str: str) -> str:
    articles_text = _format_articles_for_prompt(news)
    return f"""You are writing a daily email newsletter in the style of Morning Brew — smart, witty, conversational, and genuinely informative. The audience is a Vietnamese reader who wants to stay informed about Vietnam and the world without wading through USA-centric news.

Today's date: {date_str}

Here are today's news articles grouped by section:
{articles_text}

Write a complete HTML newsletter with this exact structure:

1. A short "Good morning" intro (2-3 sentences, friendly tone, reference the date or something timely)

2. Four sections, each with:
   - A colored section label in uppercase (e.g. VIETNAM TODAY) styled as a small blue uppercase heading
   - A bold, punchy headline (not just the article title — rewrite it to be engaging)
   - 2-3 paragraphs synthesizing the most important stories from that section. Use bullet points where helpful. Keep it under 200 words per section.

3. A "QUICK BITES" section at the end: 3-4 one-sentence bullets covering any remaining notable stories.

4. A short sign-off (2 sentences max).

IMPORTANT HTML requirements:
- Use inline CSS for all styling (emails don't support external stylesheets)
- Max width 600px, centered, white background, clean font (font-family: Georgia, serif for body; Arial, sans-serif for headings)
- Section labels: small caps, color #1a73e8 (blue), font-size 12px, letter-spacing 1px
- Headlines: font-size 22px, font-weight bold, color #111, margin-bottom 8px
- Body text: font-size 15px, line-height 1.6, color #333
- Each section in a rounded card with light gray border (#e8e8e8), padding 20px, margin-bottom 20px
- Quick Bites bullets: compact, no extra spacing
- Do NOT include any ads, sponsor messages, or referral links
- Output ONLY the HTML — no markdown, no code fences, just raw HTML starting with <div>
"""


def generate_newsletter(news: dict[str, list[dict]]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    date_str = datetime.now().strftime("%A, %B %d, %Y")
    prompt = _build_prompt(news, date_str)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    html_body = message.content[0].text.strip()

    # Wrap in a full HTML document with email-friendly structure
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Daily Brew — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:#1a73e8;padding:24px 28px;">
      <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;letter-spacing:-0.5px;">&#9728;&#65039; Your Daily Brew</h1>
      <p style="margin:6px 0 0;color:#d0e4ff;font-size:13px;">{date_str} &nbsp;&middot;&nbsp; Vietnam &amp; World Edition</p>
    </div>
    <div style="padding:24px 28px;">
      {html_body}
    </div>
    <div style="background:#f5f5f5;padding:16px 28px;text-align:center;font-size:12px;color:#999;">
      Your personalized daily newsletter &nbsp;&middot;&nbsp; Vietnam &amp; Global News
    </div>
  </div>
</body>
</html>"""
