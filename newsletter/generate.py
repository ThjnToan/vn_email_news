import os
import re
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


def _inject_images(html_body: str, section_images: dict[str, str]) -> str:
    """Inject section images directly into the HTML after each section label.

    Claude is instructed NOT to include <img> tags, so Python controls image placement
    by finding each section label element and inserting the <img> tag after it.
    """
    for section, image_url in section_images.items():
        if not image_url:
            continue
        label = SECTION_LABELS.get(section, "")
        img_html = (
            f'<img src="{image_url}" alt="" '
            f'style="width:100%;border-radius:6px;margin:10px 0 16px;display:block;" />'
        )
        # Match any HTML tag that contains the section label as its text content
        pattern = r'(<[^>]+>[^<]*' + re.escape(label) + r'[^<]*</[^>]+>)'
        new_body, n = re.subn(pattern, r'\1' + img_html, html_body, count=1)
        if n:
            html_body = new_body
            print(f"  Injected image for [{section}]: {image_url[:70]}")
        else:
            print(f"  Warning: label '{label}' not found in HTML — could not inject image")
    return html_body


def _build_prompt(news: dict[str, list[dict]], date_str: str) -> str:
    articles_text = _format_articles_for_prompt(news)
    return f"""You are writing a daily email newsletter in the style of Morning Brew — smart, witty, conversational, and genuinely informative. The audience is a Vietnamese reader who wants to stay informed about Vietnam and the world without wading through USA-centric news.

Today's date: {date_str}

Here are today's news articles grouped by section:
{articles_text}

Write a complete HTML newsletter with this exact structure:

1. A short "Good morning" intro (2-3 sentences, friendly tone, reference the date or something timely)

2. Four sections. For each section use this EXACT HTML pattern for the section label:
   <p style="font-size:11px;font-weight:700;color:#1a73e8;letter-spacing:2px;text-transform:uppercase;margin:0 0 8px 0;">SECTION NAME HERE</p>
   The section names must be exactly: VIETNAM TODAY, WORLD WATCH, TECH & SCIENCE, MARKETS & BUSINESS

   Then write:
   - A bold headline (h2 or strong tag)
   - Coverage depth rules:
     * LEAD STORY (first/most important): 3-4 paragraphs with context and implications. Use bullet points for key facts. ~300 words.
     * SUPPORTING STORIES: 1-2 paragraphs each, ~100 words.
   - If multiple stories in a section are related, connect them into a cohesive narrative.

3. A "QUICK BITES" section at the end: 4-5 one-sentence bullets covering remaining notable stories.

4. A short sign-off (2 sentences max).

IMPORTANT HTML requirements:
- Use inline CSS for all styling
- Headlines: font-size:22px; font-weight:bold; color:#111; margin-bottom:10px
- Body text: font-size:15px; line-height:1.7; color:#333
- Each section in a div with border:1px solid #e8e8e8; border-radius:8px; padding:24px; margin-bottom:20px
- Quick Bites bullets: font-size:14px
- Do NOT include any <img> tags anywhere — images are added automatically by the system
- Do NOT include any ads, sponsor messages, or referral links
- Output ONLY the HTML — no markdown, no code fences, just raw HTML starting with <div>
"""


def generate_newsletter(news: dict[str, list[dict]]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    # Collect lead image per section for programmatic injection
    section_images = {
        section: (articles[0].get("image", "") if articles else "")
        for section, articles in news.items()
    }
    print("Section images found:")
    for section, img in section_images.items():
        print(f"  [{section}]: {img[:80] if img else '(none)'}")

    client = anthropic.Anthropic(api_key=api_key)

    date_str = datetime.now().strftime("%A, %B %d, %Y")
    prompt = _build_prompt(news, date_str)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    html_body = message.content[0].text.strip()

    # Inject images programmatically — don't rely on Claude for this
    print("Injecting images:")
    html_body = _inject_images(html_body, section_images)

    date_str_safe = date_str
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Daily Brew — {date_str_safe}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:#1a73e8;padding:24px 28px;">
      <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;letter-spacing:-0.5px;">&#9728;&#65039; Your Daily Brew</h1>
      <p style="margin:6px 0 0;color:#d0e4ff;font-size:13px;">{date_str_safe} &nbsp;&middot;&nbsp; Vietnam &amp; World Edition</p>
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
