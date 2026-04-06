from __future__ import annotations

import re
import unicodedata

from models import Album


def slugify_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = t.strip("-")
    return t or "album"


def unique_slug(base: str, exclude_id: int | None = None) -> str:
    slug = slugify_text(base)
    candidate = slug
    n = 2
    while True:
        q = Album.query.filter(Album.slug == candidate)
        if exclude_id is not None:
            q = q.filter(Album.id != exclude_id)
        if not q.first():
            return candidate
        candidate = f"{slug}-{n}"
        n += 1
