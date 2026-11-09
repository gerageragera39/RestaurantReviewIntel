"""Stable IDs first; deterministic content fingerprints only as a fallback."""

import hashlib
import json
import unicodedata
from collections.abc import Iterable

from rri.models import Review


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def make_review_id(
    *,
    provider: str,
    source_review_id: str | None,
    restaurant_url: str,
    text: str,
    star_rating: int,
    original_date_text: str,
) -> str:
    """Namespace native IDs; otherwise hash a canonical restaurant URL and content.

    The adapter must supply the same canonical restaurant URL between runs.
    No reviewer name, profile link, avatar, or other personal identifier is used.
    """
    if not provider.strip():
        raise ValueError("provider must be non-empty")
    if source_review_id and source_review_id.strip():
        return f"{provider}:native:{source_review_id.strip()}"
    payload = [
        restaurant_url.strip(), _normalize(text), star_rating, _normalize(original_date_text),
    ]
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{provider}:fallback:{digest}"


def deduplicate_reviews(reviews: Iterable[Review]) -> list[Review]:
    """Keep the first observation of each ID, preserving provider order."""
    seen: set[str] = set()
    unique: list[Review] = []
    for review in reviews:
        if review.review_id not in seen:
            seen.add(review.review_id)
            unique.append(review)
    return unique
