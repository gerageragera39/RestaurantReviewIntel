"""Regression for the reported overview_or_preview_container false rejection."""
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "extension"
FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.google.com/maps/place/Pizzastar+Ingolstadt/data=!1s0x479effc97d36ab31:0x167417b48342910e!9m1!1b1!16s%2Fg%2F1vxcvdk4"


@pytest.fixture
def shared_page(chromium):
    context = chromium.new_context()
    context.route("**/*", lambda route: route.fulfill(body=(FIXTURES / "extension_shared_wrapper_reviews.html").read_text(encoding="utf-8"), content_type="text/html"))
    p = context.new_page()
    p.goto(URL)
    for script in ("review-parser.js", "collector.js", "exporter.js"):
        p.add_script_tag(path=EXT / script)
    p.evaluate("""() => {window.saved={};window.collector=new RRI.Collector({set:async value=>Object.assign(saved,structuredClone(value))});
      window.begin=options=>collector.start({runId:'shared',tabId:1,waitMs:60000,limit:0,panelWaitMs:100,...options});}""")
    yield p
    context.close()


def test_shared_main_does_not_reject_the_actual_review_scroller(shared_page):
    p = shared_page
    d = p.evaluate("RRI.diagnostics()")
    assert d["detected_review_cards"] == 10
    assert d["scroll_candidates"][0]["client_height"] == 1092
    assert d["scrollable_found"] is True
    assert d["extension_version"] == "0.1.6"
    assert d["scroll_candidates"][0]["opener_in_shared_main"] is True
    assert d["scroll_candidates"][0]["opener_inside"] is False
    assert d["scroll_candidates"][0]["rejection"] is None
    assert p.evaluate("RRI.findPanel()?.id") == "actual-reviews"


@pytest.mark.parametrize("header", [
    '<h1 class="DUwDvf">Pizzastar Ingolstadt</h1>',
    '<button role="tab" aria-selected="true">Overview</button>',
    '<div hidden><button data-item-id="address">Hidden business address control</button></div>',
])
def test_retained_headers_tabs_and_hidden_controls_do_not_veto_full_route(shared_page, header):
    p = shared_page
    p.evaluate("html=>document.querySelector('#actual-reviews').insertAdjacentHTML('afterbegin',html)", header)
    assert p.evaluate("RRI.findPanel()?.id") == "actual-reviews"


def test_start_scrolls_only_verified_panel_and_loads_additional_reviews(shared_page):
    p = shared_page
    p.evaluate("begin({})")
    assert p.evaluate("collector.records.size") == 10
    assert p.evaluate("moreClicks") == 0
    p.evaluate("collector.tick()")
    p.evaluate("async()=>{await collector.queue}")
    assert p.evaluate("collector.records.size") == 20
    assert p.evaluate("document.querySelector('#actual-reviews').scrollTop") > 0
    assert p.evaluate("window.scrollY") == 0
    scrolling = p.evaluate("collector.status().diagnostics.last_scroll")
    assert scrolling["moved"] is True and scrolling["after"] > scrolling["before"]


def test_actual_preview_opener_inside_list_is_still_rejected(shared_page):
    p = shared_page
    p.evaluate("document.querySelector('#actual-reviews').prepend(document.querySelector('#outside-opener'))")
    assert p.evaluate("RRI.findPanel()") is None


def test_visible_business_details_inside_scroller_still_reject_general_sidebar(shared_page):
    p = shared_page
    p.evaluate("""() => {const n=document.createElement('button');n.dataset.itemId='address';n.textContent='Business address control';document.querySelector('#actual-reviews').prepend(n)}""")
    assert p.evaluate("RRI.findPanel()") is None
