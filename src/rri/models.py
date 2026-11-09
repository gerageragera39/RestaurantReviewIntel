"""Provider-independent review schema; intentionally excludes reviewer identities."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from urllib.parse import urlsplit


class DateAccuracy(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


def validate_http_url(value: str) -> str:
    """Validate a supplied URL without fetching or changing its identity."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("URL must be a non-empty HTTP(S) URL")
    try:
        parts = urlsplit(value)
        valid = parts.scheme in {"http", "https"} and bool(parts.hostname)
        valid = valid and parts.username is None and parts.password is None
        _ = parts.port  # Also reject malformed ports.
    except ValueError as exc:
        raise ValueError("URL must be a valid HTTP(S) URL") from exc
    if not valid or any(char.isspace() for char in value):
        raise ValueError("URL must be an HTTP(S) URL without credentials or whitespace")
    return value


@dataclass(frozen=True, slots=True)
class Review:
    restaurant_url: str
    restaurant_name: str
    review_id: str
    text: str
    star_rating: int
    review_date_raw: str
    scraped_at: datetime
    date_estimate: date | None = None
    date_accuracy: DateAccuracy = DateAccuracy.UNKNOWN
    review_url: str | None = None

    def __post_init__(self) -> None:
        validate_http_url(self.restaurant_url)
        for field_name in ("restaurant_name", "review_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        for field_name in ("text", "review_date_raw"):
            if not isinstance(getattr(self, field_name), str):
                raise ValueError(f"{field_name} must be a string")
        # Empty text is valid for a rating-only review; an absent star rating is not.
        if type(self.star_rating) is not int or not 1 <= self.star_rating <= 5:
            raise ValueError("star_rating must be an integer from 1 to 5")
        if not isinstance(self.date_accuracy, DateAccuracy):
            raise ValueError("date_accuracy must be a DateAccuracy value")
        if self.date_estimate is not None and type(self.date_estimate) is not date:
            raise ValueError("date_estimate must be a date or None")
        if (self.date_estimate is None) != (self.date_accuracy is DateAccuracy.UNKNOWN):
            raise ValueError("unknown accuracy requires no estimate; other flags require a date")
        if not isinstance(self.scraped_at, datetime) or self.scraped_at.utcoffset() is None:
            raise ValueError("scraped_at must be a timezone-aware datetime")
        object.__setattr__(self, "scraped_at", self.scraped_at.astimezone(timezone.utc))
        if self.review_url is not None:
            validate_http_url(self.review_url)

    def to_record(self) -> dict[str, str | int | None]:
        """Stable, flat export schema shared by CSV and JSON."""
        return {
            "restaurant_url": self.restaurant_url,
            "restaurant_name": self.restaurant_name,
            "review_id": self.review_id,
            "text": self.text,
            "star_rating": self.star_rating,
            "review_date_raw": self.review_date_raw,
            "date_estimate": self.date_estimate.isoformat() if self.date_estimate else None,
            "date_accuracy": self.date_accuracy.value,
            "scraped_at": self.scraped_at.isoformat(),
            "review_url": self.review_url,
        }
