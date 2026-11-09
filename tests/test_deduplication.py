from dataclasses import replace

from rri.deduplication import deduplicate_reviews, make_review_id


def test_source_id_is_stable_when_review_is_edited(review):
    fields = dict(
        provider="google_maps", source_review_id=" native-123 ", restaurant_url=review.restaurant_url,
        text=review.text, star_rating=review.star_rating, original_date_text=review.review_date_raw,
    )
    assert make_review_id(**fields) == make_review_id(**{**fields, "text": "Edited text"})
    assert make_review_id(**fields) == "google_maps:native:native-123"


def test_fallback_is_deterministic_and_restaurant_specific(review):
    fields = dict(
        provider="google_maps", source_review_id=None, restaurant_url=review.restaurant_url,
        text="Café  soup\n", star_rating=4, original_date_text="a week ago",
    )
    identity = make_review_id(**fields)
    assert identity.startswith("google_maps:fallback:")
    assert identity == make_review_id(**{**fields, "text": "Cafe\u0301 soup"})
    assert identity != make_review_id(**{**fields, "restaurant_url": "https://example.com/other"})


def test_duplicates_keep_first_observation_in_order(review):
    edited = replace(review, text="Edited observation of same ID")
    other = replace(review, review_id="google_maps:native:other")
    assert deduplicate_reviews([review, edited, other, review]) == [review, other]
