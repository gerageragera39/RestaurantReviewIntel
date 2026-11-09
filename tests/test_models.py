from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone

import pytest

from rri.models import DateAccuracy, Review


def test_review_round_trips_export_schema(review, review_record):
    assert review.to_record() == review_record
    assert "reviewer_name" not in review.to_record()


@pytest.mark.parametrize("rating", [0, 6, -1, 4.5, "5", True, None])
def test_invalid_rating_is_rejected(review_kwargs, rating):
    with pytest.raises(ValueError, match="star_rating"):
        Review(**{**review_kwargs, "star_rating": rating})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("restaurant_name", " "), ("review_id", ""), ("text", None),
        ("review_date_raw", None), ("restaurant_url", "file:///tmp/review"),
        ("restaurant_url", "https://user:password@example.com"),
        ("restaurant_url", "https://example.com:bad"),
        ("review_url", "javascript:alert(1)"),
        ("scraped_at", datetime(2026, 11, 9)), ("scraped_at", None),
        ("date_estimate", datetime(2026, 10, 26, tzinfo=timezone.utc)),
        ("date_accuracy", "estimated"),
    ],
)
def test_invalid_fields_are_rejected(review_kwargs, field, value):
    with pytest.raises(ValueError):
        Review(**{**review_kwargs, field: value})


@pytest.mark.parametrize(
    ("estimate", "accuracy"),
    [(None, DateAccuracy.EXACT), (None, DateAccuracy.ESTIMATED),
     (date(2026, 10, 26), DateAccuracy.UNKNOWN)],
)
def test_date_and_accuracy_must_agree(review, estimate, accuracy):
    with pytest.raises(ValueError, match="accuracy"):
        replace(review, date_estimate=estimate, date_accuracy=accuracy)


def test_rating_only_and_unknown_date_are_supported(review):
    result = replace(
        review, text="", review_date_raw="", review_url=None,
        date_estimate=None, date_accuracy=DateAccuracy.UNKNOWN,
    )
    assert result.to_record()["date_estimate"] is None
    assert result.to_record()["review_url"] is None
    assert result.to_record()["text"] == ""


def test_timestamp_is_normalized_to_utc(review):
    result = replace(review, scraped_at=datetime(2026, 11, 9, 13, tzinfo=timezone(timedelta(hours=1))))
    assert result.scraped_at == datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    assert result.to_record()["scraped_at"] == "2026-11-09T12:00:00+00:00"


def test_review_is_immutable(review):
    with pytest.raises(FrozenInstanceError):
        review.star_rating = 1
