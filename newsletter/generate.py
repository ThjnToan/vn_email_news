import json
import os
import re
import time
from datetime import datetime
import anthropic
from config import CLAUDE_MODEL

_FONT = "font-family:Arial,'Helvetica Neue',Helvetica,sans-serif"
_FONT_SERIF = "font-family:Georgia,'Times New Roman',Times,serif"

SECTIONS = [
    ("vietnam",  "VIỆT NAM", "#dc2626", "🇻🇳"),
    ("global",   "THẾ GIỚI", "#2563eb", "🌍"),
    ("tech",     "CÔNG NGHỆ", "#7c3aed", "🚀"),
    ("business", "KINH DOANH", "#059669", "📈"),
]

_MAX_RETRIES = 3
_RETRY_DELAY = 5


def _vietnamese_date(dt: datetime) -> str:
    days_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    return f"{days_vi[dt.weekday()]}, {dt.day} tháng {dt.month}"


def _format_articles_for_prompt(news: dict[str, list[dict]]) -> str:
    lines = []
    for key, label, _, _ in SECTIONS:
        articles = news.get(key, [])
        lines.append(f"\n=== {label} ===")
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. [{a['source']}] {a['title']}")
            if a["summary"]:
                lines.append(f"   Summary: {a['summary']}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """Aggressively extract a JSON object from Claude's output."""
    text = text.strip()

    # Remove markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.IGNORECASE)
    text = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find outermost braces and parse
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    pass

    # Strategy 3: regex grab
    m = re.search(r"\{[\s\S]*?\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    return {}


def _header(date_str: str) -> str:
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);border-radius:0 0 16px 16px;">
  <tr><td style="padding:32px 24px 28px;text-align:center;">
    <div style="font-size:36px;margin-bottom:8px;">☀️</div>
    <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;letter-spacing:-0.5px;{_FONT};">Bản Tin Hàng Ngày</h1>
    <p style="margin:8px 0 0;color:#94a3b8;font-size:14px;{_FONT};">{date_str} · Phiên bản Việt Nam &amp; Thế giới</p>
  </td></tr>
</table>"""


def _weather_bar(weather_text: str) -> str:
    if not weather_text:
        return ""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:16px 0;">
  <tr><td style="background:#f0f9ff;border-radius:12px;padding:14px 20px;text-align:center;">
    <p style="margin:0;color:#0369a1;font-size:13px;{_FONT};">🌤️ <strong>Thời tiết hôm nay:</strong> {weather_text}</p>
  </td></tr>
</table>"""


def _opener_card(opener: dict) -> str:
    emoji = opener.get("emoji", "🌿")
    label = opener.get("label", "ĐIỀU THÚ VỊ")
    text = opener.get("text", "")
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 20px;">
  <tr><td style="background:#fffbeb;border-left:4px solid #f59e0b;border-radius:12px;padding:20px 24px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="40" valign="top" style="font-size:32px;line-height:1;">{emoji}</td>
      <td valign="top">
        <p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#b45309;letter-spacing:1.5px;text-transform:uppercase;{_FONT};">{label}</p>
        <p style="margin:0;font-size:15px;line-height:1.7;color:#78350f;{_FONT_SERIF};">{text}</p>
      </td>
    </tr></table>
  </td></tr>
</table>"""


def _intro_block(intro: str) -> str:
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;">
  <tr><td style="padding:0 4px;">
    <div style="font-size:16px;line-height:1.8;color:#334155;{_FONT_SERIF};">{intro}</div>
  </td></tr>
</table>"""


def _section_card(key: str, label: str, accent: str, icon: str, image_url: str, headline: str, body: str) -> str:
    img_block = ""
    if image_url:
        img_block = f"""<tr><td style="padding:0 0 16px;">
      <img src="{image_url}" alt="{headline[:80]}" style="max-width:100%;height:auto;border-radius:8px;display:block;" />
    </td></tr>"""

    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;background:#ffffff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
  <tr><td style="padding:20px 24px 16px;border-top:4px solid {accent};border-radius:12px 12px 0 0;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="font-size:20px;padding-right:8px;">{icon}</td>
      <td>
        <p style="margin:0;font-size:11px;font-weight:700;color:{accent};letter-spacing:1.5px;text-transform:uppercase;{_FONT};">{label}</p>
      </td>
    </tr></table>
  </td></tr>
  {img_block}
  <tr><td style="padding:0 24px 20px;">
    <h2 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#0f172a;{_FONT};letter-spacing:-0.3px;">{headline}</h2>
    <div style="font-size:15px;line-height:1.75;color:#475569;{_FONT_SERIF};">{body}</div>
  </td></tr>
</table>"""


def _numbers_card(items: list[str]) -> str:
    if not items:
        return ""
    cards = ""
    for item in items:
        cards += f"""<td style="padding:4px;">
          <div style="background:linear-gradient(135deg,#eff6ff 0%,#dbeafe 100%);border-radius:10px;padding:16px 12px;text-align:center;border:1px solid #bfdbfe;">
            <p style="margin:0;font-size:13px;line-height:1.5;color:#1e40af;{_FONT};font-weight:600;">{item}</p>
          </div>
        </td>"""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;">
  <tr><td style="padding:0 0 12px;">
    <p style="margin:0;font-size:11px;font-weight:700;color:#475569;letter-spacing:1.5px;text-transform:uppercase;{_FONT};">📊 CON SỐ ĐÁNG CHÚ Ý</p>
  </td></tr>
  <tr><td>
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>{cards}</tr></table>
  </td></tr>
</table>"""


def _quick_bites_card(items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(
        f"""<tr><td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
            <td width="24" valign="top" style="color:#f59e0b;font-size:14px;">⚡</td>
            <td valign="top" style="font-size:14px;line-height:1.6;color:#475569;{_FONT};">{item}</td>
          </tr></table>
        </td></tr>"""
        for item in items
    )
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;background:#ffffff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
  <tr><td style="padding:20px 24px 16px;border-bottom:1px solid #e2e8f0;">
    <p style="margin:0;font-size:11px;font-weight:700;color:#475569;letter-spacing:1.5px;text-transform:uppercase;{_FONT};">⚡ TIN NHANH</p>
  </td></tr>
  <tr><td style="padding:0 24px 12px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">{lis}</table>
  </td></tr>
</table>"""


def _signoff_block(signoff: str) -> str:
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 24px;">
  <tr><td style="border-top:1px solid #e2e8f0;padding:20px 0 0;">
    <p style="margin:0;font-size:15px;line-height:1.7;color:#64748b;{_FONT_SERIF};font-style:italic;text-align:center;">{signoff}</p>
  </td></tr>
</table>"""


def _footer() -> str:
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f1f5f9;border-radius:12px 12px 0 0;margin-top:8px;">
  <tr><td style="padding:24px;text-align:center;">
    <p style="margin:0 0 8px;font-size:13px;color:#64748b;{_FONT};">Bản tin cá nhân hàng ngày · Tin tức Việt Nam &amp; Thế giới</p>
    <p style="margin:0;font-size:12px;color:#94a3b8;{_FONT};">Gửi từ 🤖 với 💙</p>
  </td></tr>
</table>"""


def _build_prompt(articles_text: str, date_str: str, weather_text: str) -> str:
    weather_block = f"Thời tiết hôm nay: {weather_text}\n" if weather_text else ""
    return f"""Bạn là biên tập viên bản tin sáng cho độc giả Việt Nam. Nhiệm vụ của bạn là viết một bản tin ngắn gọn, thân thiện, dí dỏm — giống cách kể chuyện cho bạn thân. Giọng văn tự nhiên, không dịch máy. Tập trung vào Việt Nam và tin tức thế giới, bỏ qua nội dung quá Mỹ-centric.

Hôm nay: {date_str}
{weather_block}
Dưới đây là các bài báo mới nhất. Dựa vào đây, hãy viết bản tin:
{articles_text}

---
QUAN TRỌNG: Chỉ trả về một đối tượng JSON duy nhất. KHÔNG thêm văn bản giải thích, KHÔNG dùng markdown code fence, KHÔNG thêm comment.

Cấu trúc JSON (các key phải nằm trong dấu nháy kép):

{{
  "opener": {{
    "emoji": "🌿",
    "label": "ĐIỀU THÚ VỊ",
    "text": "Một câu mở đầu ngày nhẹ nhàng, hóm hỉnh."
  }},
  "intro": "<p>Lời chào sáng 2-3 câu, thân thiện và tự nhiên.</p>",
  "sections": {{
    "vietnam":  {{
      "headline": "Tiêu đề hấp dẫn, ngắn gọn",
      "body": "<p>Đoạn tin chính 3-4 câu, nêu rõ điểm chính. Dùng bullet points &lt;ul&gt;&lt;li&gt;...&lt;/li&gt;&lt;/ul&gt; cho sự kiện quan trọng.</p><p>Nếu có tin phụ liên quan, thêm 1-2 đoạn nữa.</p>"
    }},
    "global":   {{"headline": "...", "body": "<p>...</p>"}},
    "tech":     {{"headline": "...", "body": "<p>...</p>"}},
    "business": {{"headline": "...", "body": "<p>...</p>"}}
  }},
  "numbers": ["Số liệu 1", "Số liệu 2", "Số liệu 3"],
  "quick_bites": ["Tin 1 dòng.", "Tin 1 dòng.", "Tin 1 dòng.", "Tin 1 dòng."],
  "signoff": "Lời tạm biệt 2 câu, tự nhiên."
}}

Quy tắc:
- Viết toàn bộ bằng tiếng Việt tự nhiên
- Mỗi tiêu đề section: súc tích, thu hút, gợi tò mò
- Mỗi đoạn tin: bắt đầu bằng câu nóng nhất, sau đó giải thích
- body chỉ cần đoạn văn + bullet points, KHÔNG nhúng ảnh
- "numbers": 3-4 con số ấn tượng nhất từ bài báo, mỗi cái 1 dòng ngắn
- "quick_bites": 4-5 tin ngắn, mỗi tin 1 câu
- Chỉ gửi JSON thuần, không có markdown hay giải thích
"""


def _call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except anthropic.APIStatusError as e:
            if e.status_code in (429, 500, 502, 503):
                last_error = e
                wait = _RETRY_DELAY * (attempt + 1)
                print(f"  Claude API error (attempt {attempt+1}/{_MAX_RETRIES}): {e.status_code}, retrying in {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Claude API failed after {_MAX_RETRIES} attempts: {last_error}")


def _render_body(data: dict, section_images: dict, weather_text: str) -> str:
    opener = data.get("opener", {})
    intro = data.get("intro", "")
    sections_data = data.get("sections", {})
    numbers = data.get("numbers", [])
    quick_bites = data.get("quick_bites", [])
    signoff = data.get("signoff", "")

    sections_html = ""
    for key, label, accent, icon in SECTIONS:
        sec = sections_data.get(key, {})
        headline = sec.get("headline", "")
        body = sec.get("body", "")
        image_url = section_images.get(key, "")
        sections_html += _section_card(key, label, accent, icon, image_url, headline, body)

    return (
        _weather_bar(weather_text)
        + _opener_card(opener)
        + _intro_block(intro)
        + sections_html
        + _numbers_card(numbers)
        + _quick_bites_card(quick_bites)
        + _signoff_block(signoff)
    )


def _fallback_body(news: dict[str, list[dict]], weather_text: str) -> str:
    """Fallback that looks like the real newsletter using raw article data."""
    body_parts = [_weather_bar(weather_text)]

    # Opener
    body_parts.append(_opener_card({
        "emoji": "📰",
        "label": "CHÀO BUỔI SÁNG",
        "text": "Hôm nay có nhiều tin tức đáng chú ý. Dưới đây là tổng hợp nhanh từ các nguồn uy tín."
    }))

    # Intro
    body_parts.append(_intro_block(
        "<p>Chào buổi sáng! Đây là bản tin hàng ngày với những thông tin nóng hổi từ Việt Nam và thế giới.</p>"
    ))

    # Sections with raw articles
    for key, label, accent, icon in SECTIONS:
        articles = news.get(key, [])
        if not articles:
            continue

        # Get lead image
        image_url = ""
        for a in articles:
            if a.get("image"):
                image_url = a["image"]
                break

        # Build a simple body from article summaries
        body_parts_list = []
        for i, a in enumerate(articles[:3]):
            body_parts_list.append(f"<p><strong>{a['title']}</strong> — {a['summary'][:250]}</p>")
            if i == 0 and a.get("link"):
                body_parts_list.append(f'<p><a href="{a["link"]}" style="color:{accent};font-weight:600;">Đọc tiếp →</a></p>')

        body_html = "".join(body_parts_list)
        headline = f"Tin tức {label.lower()} nổi bật"
        body_parts.append(_section_card(key, label, accent, icon, image_url, headline, body_html))

    body_parts.append(
        _signoff_block("Chúc bạn một ngày tốt lành và đừng quên theo dõi bản tin ngày mai nhé!")
    )

    return "".join(body_parts)


def _plain_text(news: dict[str, list[dict]], data: dict, date_str: str, weather_text: str) -> str:
    lines = [f"BẢN TIN HÀNG NGÀY — {date_str}", ""]
    if weather_text:
        lines.append(f"Thời tiết: {weather_text}")
        lines.append("")

    opener = data.get("opener", {})
    if opener:
        lines.append(f"{opener.get('emoji', '')} {opener.get('label', '')}: {opener.get('text', '')}")
        lines.append("")

    intro = data.get("intro", "")
    if intro:
        lines.append(re.sub(r"<[^>]+>", "", intro))
        lines.append("")

    sections = data.get("sections", {})
    if sections:
        for key, label, _, _ in SECTIONS:
            sec = sections.get(key, {})
            h = sec.get("headline", "")
            b = re.sub(r"<[^>]+>", "", sec.get("body", ""))
            if h:
                lines.append(f"▶ {label}")
                lines.append(f"  {h}")
                lines.append(f"  {b[:350]}")
                lines.append("")
    else:
        # Raw fallback plain text
        for key, label, _, _ in SECTIONS:
            articles = news.get(key, [])
            if articles:
                lines.append(f"▶ {label}")
                for a in articles[:3]:
                    lines.append(f"  • {a['title']}")
                lines.append("")

    quick_bites = data.get("quick_bites", [])
    if quick_bites:
        lines.append("TIN NHANH:")
        for q in quick_bites:
            lines.append(f"  • {q}")
        lines.append("")

    numbers = data.get("numbers", [])
    if numbers:
        lines.append("CON SỐ ĐÁNG CHÚ Ý:")
        for n in numbers:
            lines.append(f"  • {n}")
        lines.append("")

    signoff = data.get("signoff", "")
    if signoff:
        lines.append(re.sub(r"<[^>]+>", "", signoff))
        lines.append("")

    lines.append("—")
    lines.append("Bản tin cá nhân hàng ngày — Tin tức Việt Nam & Quốc tế")
    return "\n".join(lines)


def generate_newsletter(news: dict[str, list[dict]], weather_text: str = "") -> tuple[str, str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    section_images = {}
    for key, _, _, _ in SECTIONS:
        articles = news.get(key, [])
        section_images[key] = ""
        for a in articles:
            if a.get("image"):
                section_images[key] = a["image"]
                break
    print("Lead images per section:")
    for key, img in section_images.items():
        print(f"  [{key}]: {img[:80] if img else '(none)'}")

    client = anthropic.Anthropic(api_key=api_key)
    date_str = _vietnamese_date(datetime.now())
    articles_text = _format_articles_for_prompt(news)
    prompt = _build_prompt(articles_text, date_str, weather_text)

    raw = ""
    data = {}
    claude_failed = False

    try:
        raw = _call_claude(client, prompt)
        data = _extract_json(raw)
        if not data:
            print(f"WARNING: Could not parse JSON from Claude. Raw length={len(raw)}. Using fallback.")
            claude_failed = True
        else:
            # Validate required keys
            required = ["opener", "intro", "sections", "quick_bites", "signoff"]
            missing = [k for k in required if k not in data]
            if missing:
                print(f"WARNING: Claude JSON missing keys {missing}. Using fallback.")
                claude_failed = True
    except Exception as e:
        print(f"WARNING: Claude generation failed ({e}). Using fallback.")
        claude_failed = True

    if claude_failed:
        body_html = _fallback_body(news, weather_text)
        # Still try to parse whatever we got for plain text
        if not data:
            data = {}
    else:
        body_html = _render_body(data, section_images, weather_text)

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bản Tin Hàng Ngày — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;{_FONT};">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;">
    {_header(date_str)}
    <div style="padding:24px;">
      {body_html}
    </div>
    {_footer()}
  </div>
</body>
</html>"""

    text = _plain_text(news, data, date_str, weather_text)

    return html, text