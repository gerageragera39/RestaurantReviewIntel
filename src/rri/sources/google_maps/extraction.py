"""Read one expanded review card from browser-rendered DOM, not network APIs."""
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from rri.errors import FailureState, ScrapeError
from rri.sources.google_maps.selectors import GoogleMapsSelectors

if TYPE_CHECKING:
    from playwright.sync_api import Locator


@dataclass(frozen=True, slots=True)
class ExtractedReview:
    source_review_id: str | None
    text: str
    star_rating: int
    review_date_raw: str
    review_url: str | None = None


def extract_review(card: "Locator", selectors: GoogleMapsSelectors) -> ExtractedReview:
    values = card.evaluate("""(card, s) => {
        const visible = node => node && node.getClientRects().length > 0;
        const text = [...card.querySelectorAll(s.review_text)].find(visible);
        const stars = [...card.querySelectorAll(s.star_rating)].find(visible);
        const date = [...card.querySelectorAll(s.date_text)].find(visible);
        const link = card.querySelector(s.review_link);
        return {
            id: card.getAttribute(s.review_id_attribute),
            text: text ? text.innerText : '',
            stars: stars ? stars.getAttribute('aria-label') : null,
            date: date ? date.innerText : null,
            link: link ? link.getAttribute('href') : null
        };
    }""", {name: getattr(selectors, name) for name in (
        "review_text", "star_rating", "date_text", "review_link", "review_id_attribute",
    )})
    label = values["stars"] or ""
    match = re.fullmatch(r"\s*([1-5])(?:[.,]0)?\s*(?:stars?|von 5 sternen|sterne[n]?)\s*", label, re.I)
    if not match:
        match = re.fullmatch(r"\s*(?:rated\s+)?([1-5])(?:[.,]0)?(?:\s+out of 5)?\s+stars?\s*", label, re.I)
    if not match or values["date"] is None:
        raise ScrapeError(FailureState.EXTRACTION_FAILED,
                          "Review card is missing a valid 1–5 star label or displayed date; DOM may have changed.")
    link = urljoin(card.page.url, values["link"]) if values["link"] else None
    if link and (urlsplit(link).scheme not in {"http", "https"} or urlsplit(link).username):
        link = None
    return ExtractedReview(values["id"] or None, values["text"], int(match.group(1)), values["date"], link)
