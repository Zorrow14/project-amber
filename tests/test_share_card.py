"""The link-preview card (Open Graph / Twitter tags in the app's index.html).

A shared link shows the project framing, word for word, so the card cannot
drift from what /meta says; and it points at a real 1200 x 630 image.
"""

from __future__ import annotations

import re
import struct
from html.parser import HTMLParser
from pathlib import Path

from amber import config

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


class _MetaTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        values = dict(attrs)
        key = values.get("property") or values.get("name")
        if key and values.get("content") is not None:
            self.tags[key] = str(values["content"])


def _tags() -> dict[str, str]:
    parser = _MetaTags()
    parser.feed((FRONTEND / "index.html").read_text(encoding="utf-8"))
    return parser.tags


def test_the_card_description_is_the_opening_of_the_project_framing() -> None:
    opening = " ".join(re.split(r"(?<=\.) ", config.PROJECT_FRAMING)[:2])
    assert opening.startswith("Amber is an analytical instrument, not an argument.")
    tags = _tags()
    assert tags["og:description"] == opening
    assert tags["twitter:description"] == opening


def test_the_card_is_a_large_image_card_with_absolute_urls() -> None:
    tags = _tags()
    assert tags["twitter:card"] == "summary_large_image"
    # Filled with the deployed origin at build time (vite.config.ts), so crawlers get absolute URLs.
    assert tags["og:image"] == tags["twitter:image"] == "%AMBER_SITE_URL%/og-image.png"
    assert tags["og:url"] == "%AMBER_SITE_URL%/"
    assert (tags["og:image:width"], tags["og:image:height"]) == ("1200", "630")
    assert tags["og:image:alt"] == tags["twitter:image:alt"]


def test_the_card_image_is_a_1200_by_630_png() -> None:
    image = (FRONTEND / "public" / "og-image.png").read_bytes()
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", image[16:24])
    assert (width, height) == (1200, 630)
