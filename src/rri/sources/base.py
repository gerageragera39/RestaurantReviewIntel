"""Minimal synchronous source contract, independent of Playwright and storage."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rri.models import Review, validate_http_url


@dataclass(frozen=True, slots=True)
class ScrapeRequest:
    url: str
    limit: int = 50
    headed: bool = True
    timeout_ms: int = 30_000
    collection_timeout_ms: int = 180_000
    max_scroll_iterations: int = 100
    max_idle_iterations: int = 5
    scroll_wait_ms: int = 1_500
    debug: bool = False
    debug_dir: Path = Path("data/debug")
    profile_dir: Path | None = None

    def __post_init__(self) -> None:
        validate_http_url(self.url)
        if type(self.limit) is not int or self.limit < 0:
            raise ValueError("limit must be a non-negative integer (0 means unlimited)")
        for name in ("timeout_ms", "collection_timeout_ms", "max_scroll_iterations", "max_idle_iterations", "scroll_wait_ms"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("headed", "debug"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if not isinstance(self.debug_dir, Path):
            raise ValueError("debug_dir must be a Path")
        if self.profile_dir is not None and not isinstance(self.profile_dir, Path):
            raise ValueError("profile_dir must be a Path or None")


@dataclass(frozen=True, slots=True)
class CollectionResult:
    reviews: list[Review]
    rating_only_count: int = 0
    stop_reason: str = "limit"
    newest_selected: bool = False
    rating_only_reviews: list[Review] = field(default_factory=list)
    full_reviews_opened: bool = False
    displayed_count_before: int | None = None
    displayed_count_after: int | None = None
    all_reviews_selected: bool = False
    authentication: str = "not_observed"
    collection_order: list[Review] = field(default_factory=list)

    @property
    def records(self) -> list[Review]:
        return self.collection_order or self.reviews + self.rating_only_reviews

    @property
    def completeness(self) -> str:
        # COMPLETE covers only the displayed, stable source snapshot, never all
        # historical/deleted/hidden reviews. Fallback hashes cannot prove coverage.
        complete = (
            self.full_reviews_opened and self.all_reviews_selected
            and self.stop_reason in {"exhausted", "idle_limit"}
            and self.displayed_count_before is not None
            and self.displayed_count_before == self.displayed_count_after == self.unique_count
            and len(self.records) == self.unique_count
            and len({review.review_id for review in self.records}) == self.unique_count
            and all(review.review_id.startswith("google_maps:native:") for review in self.records)
        )
        return "COMPLETE" if complete else "PARTIAL"

    def summary(self) -> dict:
        return {
            "status": self.completeness, "stop_reason": self.stop_reason,
            "full_reviews_opened": self.full_reviews_opened,
            "displayed_review_count": self.displayed_count_after,
            "displayed_count_before": self.displayed_count_before,
            "unique_reviews": self.unique_count, "with_full_text": len(self.reviews),
            "rating_only_reviews": self.rating_only_count,
            "with_raw_dates": sum(bool(review.review_date_raw.strip()) for review in self.records),
            "with_normalized_dates": sum(review.date_estimate is not None for review in self.records),
            "newest_selected": self.newest_selected, "all_reviews_selected": self.all_reviews_selected,
            "authentication": self.authentication,
            "completeness_scope": "displayed_snapshot_only",
        }

    @property
    def unique_count(self) -> int:
        return len(self.reviews) + self.rating_only_count


class SourceAdapter(Protocol):
    def scrape(self, request: ScrapeRequest) -> CollectionResult:
        """Return up to limit complete text reviews and collection statistics.

        Own browser cleanup and provider-specific normalization. Stop on unresolved consent
        or blocking. Never silently return partial or truncated review text.
        """
        ...
