import json
import os
import re
from datetime import datetime
import anthropic
from config import CLAUDE_MODEL

SECTIONS = [
    ("vietnam",  "VIỆT NAM HÔM NAY"),
    ("global",   "THẾ GIỚI XUNG QUANH"),
    ("tech",     "CÔNG NGHỆ & KHOA HỌC"),
    ("business", "THỊ TRƯỜNG & KINH DOANH"),
]


def _vietnamese_date(dt: datetime) -> str:
    days_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    return f"{days_vi[dt.weekday()]}, ngày {dt.day} tháng {dt.month} năm {dt.year}"


def _format_articles_for_prompt(news: dict[str, list[dict]]) -> str:
    lines = []
    for key, label in SECTIONS:
        articles = news.get(key, [])
        lines.append(f"\n=== {label} ===")
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. [{a['source']}] {a['title']}")
            if a["summary"]:
                lines.append(f"   Summary: {a['summary']}")
    return "\n".join(lines)


def _parse_response(text: str) -> dict:
    """Parse Claude's JSON, stripping markdown fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last-resort: find the outermost {...}
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}


def _section_card(label: str, image_url: str, headline: str, body: str) -> str:
    img_tag = ""
    if image_url:
        img_tag = (
            f'<img src="{image_url}" alt="" '
            f'style="width:100%;border-radius:6px;margin:10px 0 16px 0;display:block;" />'
        )
    return f"""<div style="border:1px solid #e8e8e8;border-radius:8px;padding:24px;margin-bottom:20px;">
  <p style="font-size:11px;font-weight:700;color:#1a73e8;letter-spacing:2px;text-transform:uppercase;margin:0 0 8px 0;">{label}</p>
  {img_tag}
  <h2 style="font-size:22px;font-weight:bold;color:#111;font-family:Arial,sans-serif;margin:0 0 12px 0;">{headline}</h2>
  <div style="font-size:15px;line-height:1.7;color:#333;font-family:Georgia,serif;">{body}</div>
</div>"""


def _opener_card(opener: dict) -> str:
    emoji = opener.get("emoji", "☀️")
    label = opener.get("label", "CHÀO BUỔI SÁNG")
    text = opener.get("text", "")
    return f"""<div style="background:#FFFBEA;border-left:4px solid #F5A623;border-radius:8px;padding:20px 24px;margin-bottom:20px;display:flex;align-items:flex-start;gap:14px;">
  <span style="font-size:36px;line-height:1;flex-shrink:0;">{emoji}</span>
  <div>
    <p style="font-size:10px;font-weight:700;color:#B87800;letter-spacing:2px;text-transform:uppercase;margin:0 0 6px 0;">{label}</p>
    <p style="font-size:15px;line-height:1.7;color:#5C4300;margin:0;">{text}</p>
  </div>
</div>"""


def _quick_bites_card(items: list[str]) -> str:
    lis = "".join(
        f'<li style="margin-bottom:8px;">{item}</li>' for item in items
    )
    return f"""<div style="border:1px solid #e8e8e8;border-radius:8px;padding:24px;margin-bottom:20px;">
  <p style="font-size:11px;font-weight:700;color:#1a73e8;letter-spacing:2px;text-transform:uppercase;margin:0 0 12px 0;">TIN NHANH</p>
  <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.6;color:#333;font-family:Georgia,serif;">{lis}</ul>
</div>"""


def _build_prompt(articles_text: str, date_str: str) -> str:
    return f"""Viết một bản tin sáng thật tự nhiên và sinh động cho độc giả Việt Nam. Giọng văn nên thân thiện, dí dỏm, hẹp gọn nhưng đầy đủ thông tin — giống cách bạn kể chuyện cho bạn thân. Tránh ngôn từ quá cứng nhắc hay dịch máy. Tập trung vào Việt Nam và tin tức thế giới, bỏ qua những nội dung quá Mỹ-centric.

Hôm nay: {date_str}

Các bài viết mới:
{articles_text}

Trả về JSON với cấu trúc này (nhớ dùng dấu nháy đơn cho HTML attributes):

{{
  "opener": {{
    "emoji": "🌿",
    "label": "ĐIỀU THÚ VỊ",
    "text": "Một câu nhẹ nhàng mở đầu ngày. Có thể là sự kiện lịch sử ngày hôm nay, sự thật thế giới bất ngờ, hoặc chỉ một nhận xét hóm hỉnh về thứ trong tuần. Mục tiêu là làm độc giả mỉm cười."
  }},
  "intro": "<p style='font-size:16px;line-height:1.7;color:#333;'>Lời chào sáng 2-3 câu, thân thiện và tự nhiên.</p>",
  "sections": {{
    "vietnam":  {{"headline": "Tiêu đề hấp dẫn, ngắn gọn", "body": "<p>Đoạn tin chính có 3-4 câu, khoảng 300 từ, nêu rõ những điểm chính. Dùng bullet points cho các sự kiện quan trọng.</p><p>Nếu có tin phụ khác liên quan, thêm 1-2 đoạn nữa.</p>"}},
    "global":   {{"headline": "Tiêu đề ngắn gọn", "body": "<p>...</p>"}},
    "tech":     {{"headline": "Tiêu đề hấp dẫn", "body": "<p>...</p>"}},
    "business": {{"headline": "Tiêu đề thu hút", "body": "<p>...</p>"}}
  }},
  "quick_bites": ["Tin 1 dòng.", "Tin 1 dòng.", "Tin 1 dòng.", "Tin 1 dòng."],
  "signoff": "Lời tạm biệt 2 câu, tự nhiên."
}}

Hướng dẫn:
- Viết tất cả bằng tiếng Việt tự nhiên, không dịch máy
- Mỗi tiêu đề: súc tích, thu hút, gợi tò mò
- Mỗi đoạn tin: bắt đầu bằng câu nóng nhất, sau đó giải thích chi tiết
- Quick bites: các sự kiện nhỏ gọn, 1 câu mỗi cái
- Chỉ gửi JSON, không có markdown hay giải thích thêm
"""


def generate_newsletter(news: dict[str, list[dict]]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    section_images = {
        key: (articles[0].get("image", "") if articles else "")
        for key, _ in SECTIONS
        for articles in [news.get(key, [])]
    }
    print("Images per section:")
    for key, img in section_images.items():
        print(f"  [{key}]: {img[:80] if img else '(none)'}")

    client = anthropic.Anthropic(api_key=api_key)
    date_str = _vietnamese_date(datetime.now())
    articles_text = _format_articles_for_prompt(news)
    prompt = _build_prompt(articles_text, date_str)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text
    data = _parse_response(raw)

    if not data:
        raise ValueError(f"Failed to parse JSON from Claude response. Raw output:\n{raw[:500]}")

    # Build HTML — Python controls the card structure and image placement
    opener_html = _opener_card(data.get("opener", {}))
    intro_html = data.get("intro", "")
    signoff_html = f'<p style="font-size:15px;line-height:1.7;color:#666;margin-top:8px;">{data.get("signoff", "")}</p>'

    sections_html = ""
    for key, label in SECTIONS:
        sec = data.get("sections", {}).get(key, {})
        headline = sec.get("headline", "")
        body = sec.get("body", "")
        image_url = section_images.get(key, "")
        sections_html += _section_card(label, image_url, headline, body)
        print(f"  Built card [{key}], image={'yes' if image_url else 'no'}")

    quick_bites = data.get("quick_bites", [])
    quick_html = _quick_bites_card(quick_bites) if quick_bites else ""

    body_html = opener_html + intro_html + sections_html + quick_html + signoff_html

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bản Tin Hàng Ngày — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <div style="max-width:600px;margin:30px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:#1a73e8;padding:24px 28px;">
      <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;letter-spacing:-0.5px;">&#9728;&#65039; Bản Tin Hàng Ngày</h1>
      <p style="margin:6px 0 0;color:#d0e4ff;font-size:13px;">{date_str} &nbsp;&middot;&nbsp; Phiên bản Việt Nam &amp; Thế giới</p>
    </div>
    <div style="padding:24px 28px;">
      {body_html}
    </div>
    <div style="background:#f5f5f5;padding:16px 28px;text-align:center;font-size:12px;color:#999;">
      Bản tin cá nhân hàng ngày &nbsp;&middot;&nbsp; Tin tức Việt Nam &amp; Quốc tế
    </div>
  </div>
</body>
</html>"""
