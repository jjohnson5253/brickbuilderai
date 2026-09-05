#!/usr/bin/env python3
"""Generate and publish a validated BrickBuilder AI blog content entry."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).parents[2]
CONTENT_PATH = REPOSITORY_ROOT / "frontend/src/content/blog-posts.json"
SITEMAP_PATH = REPOSITORY_ROOT / "frontend/public/sitemap.xml"
API_URL = "https://models.github.ai/inference/chat/completions"
MODEL = "openai/gpt-4.1-mini"
TOPICS = (
    "How to create custom LEGO building instructions from an image",
    "Image to LEGO converter: source image tips for better brick models",
    "How AI turns a 3D GLB file into a LEGO-compatible model",
    "AI LEGO generators compared with traditional brick design workflows",
    "How to plan a custom LEGO model before buying bricks",
    "Text to LEGO design: turning a prompt into a brick model",
)


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def _text(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = " ".join(value.split())
    if not minimum <= len(value) <= maximum:
        raise ValueError(f"{field} must contain {minimum}-{maximum} characters")
    if "<" in value or ">" in value:
        raise ValueError(f"{field} must not contain HTML")
    return value


def validate_article(raw: Any, published: date, existing_slugs: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("article must be a JSON object")

    title = _text(raw.get("title"), "title", 30, 90)
    slug = slugify(title)
    if not slug or slug in existing_slugs:
        raise ValueError("article title must produce a unique slug")

    keywords = raw.get("keywords")
    if not isinstance(keywords, list) or not 4 <= len(keywords) <= 8:
        raise ValueError("keywords must contain 4-8 items")
    clean_keywords = [_text(item, "keyword", 2, 50) for item in keywords]
    if not any(keyword.casefold() == "brickbuilder ai" for keyword in clean_keywords):
        raise ValueError('keywords must include "BrickBuilder AI"')

    sections = raw.get("sections")
    if not isinstance(sections, list) or not 5 <= len(sections) <= 8:
        raise ValueError("sections must contain 5-8 items")
    clean_sections = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError(f"section {index} must be an object")
        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list) or not 2 <= len(paragraphs) <= 3:
            raise ValueError(f"section {index} must contain 2-3 paragraphs")
        clean_sections.append(
            {
                "heading": _text(section.get("heading"), "section heading", 8, 90),
                "paragraphs": [
                    _text(paragraph, "paragraph", 120, 700) for paragraph in paragraphs
                ],
            }
        )

    faq = raw.get("faq")
    if not isinstance(faq, list) or not 3 <= len(faq) <= 5:
        raise ValueError("faq must contain 3-5 items")
    clean_faq = []
    for index, item in enumerate(faq):
        if not isinstance(item, dict):
            raise ValueError(f"FAQ {index} must be an object")
        clean_faq.append(
            {
                "question": _text(item.get("question"), "FAQ question", 10, 120),
                "answer": _text(item.get("answer"), "FAQ answer", 60, 400),
            }
        )

    return {
        "slug": slug,
        "title": title,
        "description": _text(raw.get("description"), "description", 120, 160),
        "date": published.isoformat(),
        "dateDisplay": published.strftime("%B %-d, %Y"),
        "keywords": clean_keywords,
        "category": _text(raw.get("category"), "category", 5, 40),
        "intro": _text(raw.get("intro"), "intro", 140, 450),
        "image": "/assets/blog/brickworld26/brickbuilderai-models.jpg",
        "imageAlt": "LEGO-compatible brick models created with BrickBuilder AI",
        "sections": clean_sections,
        "faq": clean_faq,
    }


def request_article(token: str, topic: str, existing_titles: list[str]) -> Any:
    prompt = f"""
Write an accurate, evergreen educational article about: {topic}

The article is for BrickBuilder AI (https://brickbuilder.ai), a browser-based tool
that turns images, text prompts, and GLB 3D files into editable LEGO-compatible
brick models. Never claim affiliation with or endorsement by the LEGO Group.
Do not invent prices, performance figures, customer claims, product features, or
external citations. Explain limitations and recommend checking connections,
stability, colors, scale, and part availability before a physical build.

Optimize for people and machine answer engines: answer the topic directly, use
descriptive headings, define BrickBuilder AI clearly, mention it naturally, and
include concise FAQs. Do not repeat these existing titles: {existing_titles}.

Return only a JSON object with: title, description (120-160 characters), keywords
(4-8 strings including "BrickBuilder AI"), category, intro, sections (5-8 objects,
each with heading and 2-3 substantial paragraphs), and faq (3-5 question/answer
objects). Do not return Markdown or HTML.
""".strip()
    payload = json.dumps(
        {
            "model": MODEL,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": "You are a careful technical editor."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
    ).encode()
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "brickbuilderai-blog-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    content = result["choices"][0]["message"]["content"]
    return json.loads(content)


def update_sitemap(path: Path, slug: str, published: date) -> None:
    sitemap = path.read_text(encoding="utf-8")
    location = f"https://brickbuilder.ai/blog/{slug}"
    if location in sitemap:
        raise ValueError("sitemap already contains generated article")

    timestamp = f"{published.isoformat()}T00:00:00+00:00"
    blog_pattern = re.compile(
        r"(<loc>https://brickbuilder\.ai/blog</loc>\s*<lastmod>)[^<]+(</lastmod>)"
    )
    sitemap, replacements = blog_pattern.subn(rf"\g<1>{timestamp}\g<2>", sitemap, count=1)
    if replacements != 1:
        raise ValueError("blog sitemap entry was not found")

    entry = (
        "<url>\n"
        f"  <loc>{location}</loc>\n"
        f"  <lastmod>{timestamp}</lastmod>\n"
        "</url>\n\n"
    )
    path.write_text(sitemap.replace("</urlset>", f"{entry}</urlset>"), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    posts = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    topic = TOPICS[len(posts) % len(TOPICS)]
    raw_article = request_article(token, topic, [post["title"] for post in posts])
    article = validate_article(raw_article, args.date, {post["slug"] for post in posts})
    posts.insert(0, article)
    CONTENT_PATH.write_text(f"{json.dumps(posts, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    update_sitemap(SITEMAP_PATH, article["slug"], args.date)
    print(f"Generated {article['title']} at /blog/{article['slug']}")


if __name__ == "__main__":
    main()
