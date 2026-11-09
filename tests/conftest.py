import json
from datetime import date, datetime
from pathlib import Path

import pytest

from rri.models import DateAccuracy, Review

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def review_record():
    return json.loads((FIXTURES / "review.json").read_text(encoding="utf-8"))


@pytest.fixture
def review_kwargs(review_record):
    return {
        **review_record,
        "date_estimate": date.fromisoformat(review_record["date_estimate"]),
        "date_accuracy": DateAccuracy(review_record["date_accuracy"]),
        "scraped_at": datetime.fromisoformat(review_record["scraped_at"]),
    }


@pytest.fixture
def review(review_kwargs):
    return Review(**review_kwargs)


@pytest.fixture
def chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, timeout=10_000)
        yield browser
        browser.close()


@pytest.fixture
def page(chromium):
    context = chromium.new_context(locale="en-US", timezone_id="UTC")
    # Saved-fixture tests cannot issue live requests, even by accident.
    context.route("**/*", lambda route: route.abort())
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def load_html(page):
    def load(name):
        page.set_content((FIXTURES / name).read_text(encoding="utf-8"))
        return page
    return load


@pytest.fixture
def adapter():
    import time
    from rri.sources.base import ScrapeRequest
    from rri.sources.google_maps.adapter import GoogleMapsAdapter

    adapter = GoogleMapsAdapter()
    adapter.request = ScrapeRequest(
        url="https://www.google.com/maps/place/Fixture/", limit=3,
        timeout_ms=2000, scroll_wait_ms=30, max_idle_iterations=2, max_scroll_iterations=4,
    )
    adapter.deadline = time.monotonic() + 30
    adapter.phase = "fixture"
    adapter.signin_prompts = 0
    return adapter


def pytest_addoption(parser):
    parser.addoption("--live-url", default=None, help="Explicitly authorized Google Maps URL for live integration testing")
    parser.addoption("--live-profile", type=Path, default=None, help="Optional already-authorized isolated profile for live tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--live-url"):
        skip = pytest.mark.skip(reason="Live integration requires explicit --live-url authorization")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)
