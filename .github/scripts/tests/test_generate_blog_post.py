from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "generate_blog_post.py"
SPEC = importlib.util.spec_from_file_location("generate_blog_post", MODULE_PATH)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


def valid_article() -> dict:
    paragraph = (
        "BrickBuilder AI provides an editable starting point for a custom brick model. "
        "Creators should review the scale, available colors, connections, and physical "
        "stability before ordering parts or beginning a real-world build."
    )
    return {
        "title": "How to prepare an image for an AI LEGO model",
        "description": (
            "Prepare clearer source images for BrickBuilder AI and learn how contrast, "
            "silhouette, scale, and detail affect an AI LEGO model."
        ),
        "keywords": ["image to LEGO", "AI brick model", "BrickBuilder AI", "source image"],
        "category": "Image preparation",
        "intro": (
            "A clear source image gives an image-to-brick workflow useful information "
            "about the subject. These practical steps help creators prepare an image "
            "before generating a LEGO-compatible model with BrickBuilder AI."
        ),
        "sections": [
            {"heading": f"Preparation step number {index}", "paragraphs": [paragraph, paragraph]}
            for index in range(1, 6)
        ],
        "faq": [
            {
                "question": f"What should a creator check in source image {index}?",
                "answer": (
                    "Use one clear subject with a strong silhouette and inspect the "
                    "generated model before treating it as ready for a physical build."
                ),
            }
            for index in range(1, 4)
        ],
    }


class GenerateBlogPostTests(unittest.TestCase):
    def test_requests_structured_content_with_github_token(self) -> None:
        response = {
            "choices": [{"message": {"content": json.dumps(valid_article())}}]
        }

        with patch.object(
            generator.urllib.request,
            "urlopen",
            return_value=io.BytesIO(json.dumps(response).encode()),
        ) as urlopen:
            result = generator.request_article("test-token", "Test topic", [])

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header("Authorization"), "Bearer " + "test-token"
        )
        self.assertEqual(result["title"], valid_article()["title"])

    def test_validates_and_adds_owned_metadata(self) -> None:
        article = generator.validate_article(valid_article(), date(2026, 9, 4), set())

        self.assertEqual(article["slug"], "how-to-prepare-an-image-for-an-ai-lego-model")
        self.assertEqual(article["date"], "2026-09-04")
        self.assertEqual(article["dateDisplay"], "September 4, 2026")
        self.assertTrue(article["image"].startswith("/assets/blog/"))

    def test_rejects_duplicate_slug(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique slug"):
            generator.validate_article(
                valid_article(),
                date(2026, 9, 4),
                {"how-to-prepare-an-image-for-an-ai-lego-model"},
            )

    def test_rejects_html_in_generated_content(self) -> None:
        article = valid_article()
        article["intro"] = "<script>alert('unsafe')</script>" + article["intro"]

        with self.assertRaisesRegex(ValueError, "must not contain HTML"):
            generator.validate_article(article, date(2026, 9, 4), set())

    def test_updates_blog_timestamp_and_adds_article_to_sitemap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sitemap = Path(directory) / "sitemap.xml"
            sitemap.write_text(
                "<urlset>\n<url><loc>https://brickbuilder.ai/blog</loc>\n"
                "<lastmod>2026-01-01T00:00:00+00:00</lastmod></url>\n</urlset>\n",
                encoding="utf-8",
            )

            generator.update_sitemap(sitemap, "new-article", date(2026, 9, 4))
            result = sitemap.read_text(encoding="utf-8")

            self.assertEqual(result.count("2026-09-04T00:00:00+00:00"), 2)
            self.assertIn("https://brickbuilder.ai/blog/new-article", result)


if __name__ == "__main__":
    unittest.main()
