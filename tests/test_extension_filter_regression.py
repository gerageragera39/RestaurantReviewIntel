"""Regression based on the co:Lab diagnostic log: active tab plus local opener."""
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "extension"
FIXTURE = Path(__file__).parent / "fixtures" / "extension_colab_filter.html"


@pytest.fixture
def filter_page(chromium):
    context = chromium.new_context()
    context.route("**/*", lambda route: route.fulfill(body=FIXTURE.read_text(encoding="utf-8"), content_type="text/html"))
    p = context.new_page()
    p.goto("https://www.google.com/maps/place/co:Lab/data=!1s0x479efe56ab268415:0x784ef5717abe206!16s%2Fg%2F11c1wxyy_s")
    for script in ("review-parser.js", "collector.js"):
        p.add_script_tag(path=EXT / script)
    p.evaluate("""()=>{window.saved={};window.collector=new RRI.Collector({set:async value=>Object.assign(saved,structuredClone(value))});
      window.begin=()=>collector.start({runId:'filter-regression',tabId:1,limit:0,waitMs:60000,panelWaitMs:200,scrollOnStart:true});}""")
    yield p
    context.close()


@pytest.mark.parametrize("label", ["All reviews", "Alle Rezensionen", "Все отзывы"])
def test_all_reviews_filter_does_not_reject_open_full_list(filter_page, label):
    p = filter_page
    p.evaluate("openFullReviews()")
    p.evaluate("label=>document.querySelector('#filter').textContent=label", label)
    d = p.evaluate("RRI.diagnostics()")
    assert d["detected_review_cards"] == 10
    assert d["review_route_hint"] is True
    assert d["scroll_candidates"][0]["confirmed_reviews_tab"] is True
    assert d["scrollable_found"] is True
    assert d["scroll_candidates"][0]["ignored_all_reviews_filters"] == 1
    assert d["scroll_candidates"][0]["blocker"] == ""


def test_start_completes_the_recorded_transition_and_scrolls(filter_page):
    p = filter_page
    assert p.evaluate("RRI.cards(document).length") == 3
    p.evaluate("begin()")
    assert p.evaluate("collector.state") == "running"
    assert p.evaluate("collector.panel.id") == "full-scroll"
    assert p.evaluate("collector.records.size") == 11
    assert p.evaluate("collector.lastScroll.moved") is True
    assert p.evaluate("window.scrollY") == 0


def test_residual_more_button_cannot_veto_confirmed_dedicated_list(filter_page):
    p = filter_page
    p.evaluate("openFullReviews()")
    p.evaluate("document.querySelector('#filter').textContent='More reviews'")
    d = p.evaluate("RRI.diagnostics()")
    assert d["scrollable_found"] is True
    assert d["scroll_candidates"][0]["opener_inside"] is True
    assert d["scroll_candidates"][0]["opener_ignored_in_verified_list"] is True
    p.evaluate("begin()")
    assert p.evaluate("collector.lastScroll.moved") is True


def test_local_more_without_confirmed_tab_stays_blocked(filter_page):
    p = filter_page
    p.evaluate("openFullReviews()")
    p.evaluate("document.querySelector('#filter').textContent='More reviews';document.querySelector('#reviews-tab').setAttribute('aria-selected','false')")
    d = p.evaluate("RRI.diagnostics()")
    assert d["scrollable_found"] is False
    assert d["scroll_candidates"][0]["rejection"] == "preview_opener_in_scroller"


def test_all_reviews_entry_still_opens_from_overview(filter_page):
    p = filter_page
    p.evaluate("document.querySelector('#reviews-tab').remove();document.querySelector('#preview button:not([data-item-id])').textContent='All reviews'")
    assert p.evaluate("RRI.reviewOpener()?.textContent") == "All reviews"
    assert p.evaluate("RRI.inspect().mode") == "PREVIEW_MODE"


def test_selected_tab_during_transition_does_not_bless_three_overview_previews(filter_page):
    p = filter_page
    p.evaluate("""() => {
      document.querySelector('#reviews-tab').setAttribute('aria-selected','true');
      document.querySelector('main').style.cssText='height:600px;overflow:auto';
      document.querySelector('#preview button:not([data-item-id])').textContent='All reviews';
    }""")
    assert p.evaluate("RRI.cards(document).length") == 3
    assert p.evaluate("RRI.findPanel()") is None
    assert p.evaluate("RRI.inspect().mode") == "PREVIEW_MODE"


def test_active_tab_with_filter_does_not_require_url_marker(filter_page):
    p = filter_page
    p.evaluate("openFullReviews()")
    p.evaluate("history.replaceState({},'','/maps/place/co:Lab/')")
    assert p.evaluate("RRI.findPanel()?.id") == "full-scroll"
