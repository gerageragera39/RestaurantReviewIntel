"""Synthetic regressions based on the user's 40-card diagnostic, not live DOM."""
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "extension"
FIXTURES = Path(__file__).parent / "fixtures"
REPORTED_URL = (FIXTURES / "extension_reported_route.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def lazy_page(chromium):
    context = chromium.new_context()
    context.route("**/*", lambda route: route.fulfill(body=(FIXTURES / "extension_lazy_reviews.html").read_text(encoding="utf-8"), content_type="text/html"))
    p = context.new_page()
    p.goto(REPORTED_URL)
    for script in ("review-parser.js", "collector.js", "exporter.js"):
        p.add_script_tag(path=EXT / script)
    p.evaluate("""() => { window.saved={}; window.collector=new RRI.Collector({set:async value=>Object.assign(saved,structuredClone(value))});
      window.begin=options=>collector.start({runId:'lazy',tabId:1,waitMs:60000,limit:0,...options}); }""")
    yield p
    context.close()


def flush(p):
    p.evaluate("async()=>{await collector.queue}")


def test_reported_layout_starts_with_current_cards_not_total(lazy_page):
    p = lazy_page
    diagnostics = p.evaluate("RRI.diagnostics()")
    assert diagnostics["mode"] == "FULL_REVIEWS_MODE"
    assert diagnostics["detected_review_cards"] == diagnostics["full_review_cards"] == 40
    assert diagnostics["scrollable_found"] is True
    assert diagnostics["panel_evidence"] == "reviews_route_scroller"
    assert diagnostics["restaurant_name"] == "Asia Imbiss Le"
    assert diagnostics["restaurant_name_source"] == "url_path"
    p.evaluate("begin({panelWaitMs:200})")
    assert p.evaluate("collector.records.size") == 40
    assert p.evaluate("nextReview") == 40


def test_lazy_scroll_loads_new_unique_reviews_and_virtualizes(lazy_page):
    p = lazy_page
    p.evaluate("begin({panelWaitMs:200})")
    p.evaluate("collector.tick()")
    flush(p)
    # Native and dispatched scroll notifications may be coalesced or delivered
    # separately; assert retained data and virtualization, not event timing.
    assert 50 <= p.evaluate("collector.records.size") <= 60
    assert p.evaluate("RRI.cards(collector.panel).length") < 40
    p.evaluate("collector.tick()")
    flush(p)
    assert p.evaluate("collector.records.size") == 60
    assert p.evaluate("window.scrollY") == 0
    data = p.evaluate("JSON.parse(RRI.toJSON([...collector.records.values()]))")
    assert len({r["review_id"] for r in data}) == 60
    assert all(r["rating"] == 5 and r["date_raw"] == "vor 2 Wochen" for r in data)
    assert all(r["restaurant_name"] == "Asia Imbiss Le" for r in data)


def test_only_active_place_ids_are_used(lazy_page):
    keys = lazy_page.evaluate("RRI.identity().keys")
    assert keys["feature"] == "0x479effaa32fa0fb5:0x199e5e091711fa48"
    assert keys["entity"] == "%2Fg%2F11h77zjjtf"


def test_old_places_review_marker_does_not_bless_current_previews(lazy_page):
    p = lazy_page
    p.evaluate("""() => {
      const url=location.href; const last=url.lastIndexOf('!9m1!1b1');
      history.replaceState({},'',url.slice(0,last)+url.slice(last+9));
    }""")
    d = p.evaluate("RRI.diagnostics()")
    assert d["review_route_hint"] is False
    assert d["mode"] == "PREVIEW_MODE"
    assert d["scrollable_found"] is False
    assert d["scroll_candidates"][0]["rejection"] == "no_active_reviews_route_hint"


def test_many_cards_alone_and_general_sidebar_are_rejected(lazy_page):
    p = lazy_page
    p.evaluate("""() => {
      const h=document.createElement('h1');h.className='DUwDvf';h.textContent='Asia Imbiss Le';
      document.querySelector('#lazy-scroll').prepend(h);
    }""")
    d = p.evaluate("RRI.diagnostics()")
    assert d["detected_review_cards"] == 40
    assert d["scrollable_found"] is False
    assert d["scroll_candidates"][0]["rejection"] == "overview_or_preview_container"


def test_same_prior_business_but_different_active_target_stops(lazy_page):
    p = lazy_page
    p.evaluate("begin({panelWaitMs:200})")
    p.evaluate("history.pushState({},'',location.href.replace('0x199e5e091711fa48','0x199e5e091711fa49'))")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.reason") == "page_changed"


def test_lazy_collection_honors_text_limit(lazy_page):
    p = lazy_page
    p.evaluate("begin({limit:45,panelWaitMs:200})")
    p.evaluate("collector.tick()")
    flush(p)
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.records.size") == 45
    assert p.evaluate("collector.reason") == "text_limit"
