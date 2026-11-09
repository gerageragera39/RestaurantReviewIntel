import time
import json
from pathlib import Path
from dataclasses import replace
from datetime import date

import pytest

from rri.dates import parse_review_date
from rri.errors import FailureState, ScrapeError
from rri.models import DateAccuracy
from rri.sources.google_maps.adapter import check_blocked, find_review_container, validate_maps_url
from rri.sources.google_maps.diagnostics import save_debug
from rri.sources.google_maps.extraction import extract_review
from rri.sources.google_maps.selectors import SELECTORS


@pytest.mark.parametrize(("fixture", "expected_text", "expected_rating", "raw_date"), [
    ("reviews_en.html", "Soup was lovely.\nFriendly service, €12 — would return!", 4, "2 weeks ago"),
    ("reviews_de.html", "Sehr gutes Essen — große Portionen!\nFreundlicher Service.", 5, "vor 2 Wochen"),
])
def test_expands_and_extracts_actual_dom_fields(load_html, adapter, fixture, expected_text, expected_rating, raw_date):
    page = load_html(fixture)
    card = page.locator(SELECTORS.review_card).first
    adapter._expand(card)
    review = extract_review(card, SELECTORS)
    assert review.text == expected_text
    assert review.star_rating == expected_rating
    assert review.review_date_raw == raw_date == card.locator(SELECTORS.date_text).inner_text()
    assert review.source_review_id
    assert "Owner reply" not in review.text


def test_rating_only_and_optional_native_id(load_html):
    page = load_html("reviews_en.html")
    cards = page.locator(SELECTORS.review_card)
    rating_only = extract_review(cards.nth(1), SELECTORS)
    assert rating_only.text == "" and rating_only.star_rating == 3
    assert extract_review(cards.nth(2), SELECTORS).source_review_id is None
    assert extract_review(cards.first, SELECTORS).review_url.endswith("/reviews/fixture-en")


def test_unrecognized_date_is_preserved(load_html):
    page = load_html("reviews_de.html")
    raw = extract_review(page.locator(SELECTORS.review_card).nth(1), SELECTORS)
    assert raw.star_rating == 4
    assert raw.review_date_raw == "Bearbeitet: vor einem Jahr"
    parsed = parse_review_date(raw.review_date_raw, reference_date=date(2026, 11, 9))
    assert parsed.date_estimate is None and parsed.accuracy is DateAccuracy.UNKNOWN


@pytest.mark.parametrize("label", ["0 stars", "6 stars", "4.5 stars", "not a rating"])
def test_invalid_rating_fails_explicitly(load_html, label):
    page = load_html("reviews_en.html")
    card = page.locator(SELECTORS.review_card).first
    card.locator(SELECTORS.star_rating).evaluate("(node, label) => node.setAttribute('aria-label', label)", label)
    with pytest.raises(ScrapeError) as caught:
        extract_review(card, SELECTORS)
    assert caught.value.state is FailureState.EXTRACTION_FAILED


def test_missing_date_is_extraction_failure(load_html):
    page = load_html("reviews_en.html")
    card = page.locator(SELECTORS.review_card).first
    card.locator(SELECTORS.date_text).evaluate("node => node.remove()")
    with pytest.raises(ScrapeError):
        extract_review(card, SELECTORS)


def test_failed_expansion_never_exports_truncated_text(load_html, adapter):
    page = load_html("reviews_en.html")
    card = page.locator(SELECTORS.review_card).first
    card.get_by_role("button", name="More", exact=True).evaluate("node => node.removeAttribute('onclick')")
    adapter.request = replace(adapter.request, timeout_ms=100)
    with pytest.raises(ScrapeError) as caught:
        adapter._expand(card)
    assert caught.value.state is FailureState.EXTRACTION_FAILED


def test_workflow_opens_reviews_sorts_and_scrolls_container(load_html, adapter):
    page = load_html("workflow.html")
    adapter._open_reviews(page)
    newest = adapter._select_newest(page)
    result = adapter._collect(page, "Fixture Restaurant", adapter.request.url, newest)
    assert newest and page.evaluate("window.newest")
    assert result.stop_reason == "limit"
    assert len(result.reviews) == 3
    assert result.rating_only_count == 1 and result.unique_count == 4
    assert len({review.review_id for review in result.reviews}) == 3
    assert result.reviews[-1].text == "Loaded after container scroll."
    assert page.evaluate("window.scrollY") == 0
    assert page.locator("#review-scroll").evaluate("node => node.scrollTop") > 0


def test_idle_and_scroll_bounds(load_html, adapter):
    page = load_html("reviews_en.html")
    adapter.request = replace(adapter.request, limit=50, max_idle_iterations=2)
    result = adapter._collect(page, "Fixture Restaurant", adapter.request.url, False)
    assert result.stop_reason == "idle_limit"
    assert len(result.reviews) == 2 and result.rating_only_count == 1
    adapter.request = replace(adapter.request, max_scroll_iterations=1)
    result = adapter._collect(page, "Fixture Restaurant", adapter.request.url, False)
    assert result.stop_reason == "scroll_limit"


def test_overall_deadline(load_html, adapter):
    page = load_html("reviews_en.html")
    adapter.deadline = time.monotonic() - 1
    with pytest.raises(ScrapeError) as caught:
        adapter._collect(page, "Fixture Restaurant", adapter.request.url, False)
    assert caught.value.state is FailureState.TIMEOUT


@pytest.mark.parametrize(("fixture", "state"), [
    ("blocked.html", FailureState.BLOCKED_CAPTCHA),
    ("restricted.html", FailureState.INACCESSIBLE_PAGE),
])
def test_source_restrictions_are_explicit(load_html, fixture, state):
    page = load_html(fixture)
    with pytest.raises(ScrapeError) as caught:
        check_blocked(page)
    assert caught.value.state is state


def test_review_text_does_not_trigger_false_block(load_html):
    page = load_html("reviews_en.html")
    page.locator(SELECTORS.review_text).first.evaluate("node => node.innerText='Unusual traffic outside; nice food.'")
    check_blocked(page)


def test_standard_german_consent_prefers_reject(load_html, adapter):
    page = load_html("consent_de.html")
    assert adapter._consent(page)
    assert page.get_by_role("dialog").count() == 0


def test_unknown_consent_fails(load_html, adapter):
    page = load_html("consent_de.html")
    page.get_by_role("button").evaluate_all("nodes => nodes.forEach(node => node.remove())")
    with pytest.raises(ScrapeError) as caught:
        adapter._consent(page)
    assert caught.value.state is FailureState.CONSENT_REQUIRED


def test_debug_redacts_secrets_and_reviewer_identity(load_html, tmp_path):
    page = load_html("reviews_en.html")
    save_debug(page, tmp_path, "fixture")
    snapshot = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")
    assert "never-save-this-token" not in snapshot
    assert "never-save-this-password" not in snapshot
    assert "Synthetic Reviewer Name" not in snapshot
    assert "onclick" not in snapshot and "href=" not in snapshot
    assert "Soup was lovely" in snapshot
    assert next(tmp_path.glob("*.png")).stat().st_size > 0


def test_refuses_to_scroll_main_document(page):
    page.set_content('<div class="jftiEf"><span class="wiI7pd">Not inside a review panel.</span></div>')
    with pytest.raises(ScrapeError) as caught:
        find_review_container(page)
    assert caught.value.state is FailureState.EXTRACTION_FAILED


@pytest.mark.parametrize("url", [
    "https://example.com/maps/place/Test/", "https://www.google.com/maps/search/restaurants",
    "https://www.google.com.evil.test/maps/place/Test/", "http://www.google.com/maps/place/Test/",
    "https://www.google.com:444/maps/place/Test/",
])
def test_rejects_non_place_urls(url):
    with pytest.raises(ValueError):
        validate_maps_url(url)


@pytest.mark.parametrize("url", [
    "https://www.google.com/maps/place/Test/", "https://www.google.de/maps/place/Test/",
    "https://maps.app.goo.gl/test", "https://goo.gl/maps/test", "https://maps.google.com/?cid=123",
])
def test_accepts_google_place_urls(url):
    assert validate_maps_url(url) == url


@pytest.mark.parametrize(("fixture", "failure"), [
    ("workflow.html", None), ("blocked.html", FailureState.BLOCKED_CAPTCHA),
])
def test_real_browser_lifecycle_at_intercepted_navigation_boundary(monkeypatch, tmp_path, fixture, failure):
    """Real Chromium; test-only routing fulfills saved HTML, never a live request."""
    from playwright.sync_api import Browser
    from rri.config import ScrapeConfig
    from rri.service import scrape_and_export
    from rri.sources.google_maps.adapter import GoogleMapsAdapter

    markup = (Path(__file__).parent / "fixtures" / fixture).read_text(encoding="utf-8")
    original = Browser.new_context
    contexts = []
    browsers = []

    def intercepted_context(browser, **kwargs):
        context = original(browser, **kwargs)
        context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=markup))
        contexts.append(context)
        browsers.append(browser)
        return context

    monkeypatch.setattr(Browser, "new_context", intercepted_context)
    config = ScrapeConfig(limit=3, headed=False, timeout_ms=2000, scroll_wait_ms=30,
                          max_scroll_iterations=4, max_idle_iterations=2,
                          export_dir=tmp_path / "exports", report_dir=tmp_path / "reports", debug=True, debug_dir=tmp_path / "debug")
    if failure:
        with pytest.raises(ScrapeError) as caught:
            scrape_and_export(url="https://www.google.com/maps/place/Fixture/", config=config, adapter=GoogleMapsAdapter())
        assert caught.value.state is failure
        assert not config.export_dir.exists()
    else:
        result = scrape_and_export(url="https://www.google.com/maps/place/Fixture/", config=config, adapter=GoogleMapsAdapter())
        assert result.review_count == 3 and result.rating_only_count == 1 and result.newest_selected
        records = json.loads(result.json_path.read_text(encoding="utf-8"))
        assert len(records) == 3
        assert all(record["restaurant_name"] == "Fixture Restaurant" for record in records)
    assert contexts and all(not browser.is_connected() for browser in browsers)
    assert list(config.debug_dir.glob("*.html")) and list(config.debug_dir.glob("*.png"))
