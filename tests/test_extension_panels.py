"""Saved DOM regressions for More reviews; no live Maps requests."""
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "extension"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def panel_page(chromium):
    context = chromium.new_context()
    context.route("**/*", lambda route: route.fulfill(body=(FIXTURES / "extension_preview.html").read_text(encoding="utf-8"), content_type="text/html"))
    p = context.new_page()
    p.goto("https://www.google.com/maps/place/Fixture+Restaurant/")
    for script in ("review-parser.js", "collector.js"):
        p.add_script_tag(path=EXT / script)
    p.evaluate("""() => { window.saved={}; window.collector=new RRI.Collector({set:async value=>Object.assign(saved,structuredClone(value))});
      window.begin=options=>collector.start({runId:'panels',tabId:1,waitMs:60000,limit:0,...options}); }""")
    yield p
    context.close()


def load_fixture(page, name):
    page.set_content((FIXTURES / name).read_text(encoding="utf-8"))


def collected_ids(page):
    page.evaluate("async () => {await collector.queue}")
    return page.evaluate("[...collector.records.keys()]")


def test_full_dialog_beats_earlier_preview_sidebar(panel_page):
    p = panel_page
    p.click("#more-reviews")
    assert p.evaluate("RRI.findPanel()?.id") == "full-scroll"


def test_same_place_spa_url_change_is_not_page_changed(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("begin({})")
    p.evaluate("history.pushState({},'',location.pathname+'?entry=reviews&sort=newest')")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.state") == "running"


def test_same_place_route_can_drop_one_identifier_namespace(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("history.replaceState({},'','/maps/place/Fixture+Restaurant/data=!1s0x1:0x2!16s%2Fg%2Ffixture')")
    p.evaluate("begin({})")
    p.evaluate("history.pushState({},'','/maps/place/Fixture+Restaurant/data=!16s%2Fg%2Ffixture?entry=reviews')")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.state") == "running"


def test_exactly_three_previews_are_never_full(panel_page):
    p = panel_page
    assert p.evaluate("RRI.inspect().mode") == "PREVIEW_MODE"
    assert p.evaluate("RRI.diagnostics().detected_review_cards") == 3
    assert p.evaluate("RRI.findPanel()") is None
    # A leftover selected Reviews tab must not bless a general preview sidebar.
    p.evaluate("document.querySelector('[role=tab]').textContent='Reviews'")
    assert p.evaluate("RRI.inspect().mode") == "PREVIEW_MODE"


def test_preview_feed_label_alone_does_not_override_more_reviews(panel_page):
    p = panel_page
    p.evaluate("""() => {
      const feed=document.createElement('div'); feed.setAttribute('role','feed'); feed.setAttribute('aria-label','Reviews');
      feed.style.cssText='height:100px;overflow:auto';
      document.querySelectorAll('#preview .jftiEf').forEach(n=>feed.append(n));
      document.querySelector('#preview').prepend(feed);
    }""")
    assert p.evaluate("RRI.inspect().mode") == "PREVIEW_MODE"
    assert p.evaluate("RRI.findPanel()") is None
    assert p.evaluate("RRI.diagnostics().detected_review_cards") == 3


@pytest.mark.parametrize("language", ["en", "de"])
def test_start_opens_more_reviews_and_excludes_previews(panel_page, language):
    p = panel_page
    if language == "de":
        p.evaluate("document.querySelector('#more-reviews').textContent='Weitere Rezensionen'")
    p.evaluate("begin({panelWaitMs:500})")
    ids = collected_ids(p)
    assert len(ids) == 2 and all(":full-" in key for key in ids)
    assert p.evaluate("collector.panel.id") == "full-scroll"
    assert p.evaluate("collector.status().diagnostics.mode") == "FULL_REVIEWS_MODE"
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.panel.scrollTop") > 0
    assert p.evaluate("document.querySelector('#sidebar').scrollTop") == 0


def test_delayed_open_waits_without_collecting_preview_cards(panel_page):
    p = panel_page
    p.evaluate("""() => {
      const original=window.openFull; window.openFull=()=>setTimeout(original,75);
      window.startPromise=begin({panelWaitMs:500});
    }""")
    assert p.evaluate("collector.state") == "waiting_for_reviews"
    assert collected_ids(p) == []
    p.evaluate("window.startPromise")
    assert len(collected_ids(p)) == 2


def test_german_full_interface_different_scroll_container(panel_page):
    p = panel_page
    load_fixture(p, "extension_full_de.html")
    p.evaluate("begin({})")
    assert p.evaluate("collector.panel.id") == "german-scroll"
    assert len(collected_ids(p)) == 2
    assert p.evaluate("[...collector.records.values()][0].date_raw") == "vor 2 Wochen"


@pytest.mark.parametrize("delay", [0, 75])
def test_same_place_dom_replacement_reacquires_and_observes(panel_page, delay):
    p = panel_page
    load_fixture(p, "extension_spa.html")
    p.evaluate("begin({panelWaitMs:500})")
    p.evaluate("replacePanel", delay)
    if delay:
        p.evaluate("collector.tick()")
        assert p.evaluate("collector.state") == "running"
    p.wait_for_selector("#replacement-scroll")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.panel.id") == "replacement-scroll"
    assert set(collected_ids(p)) == {"google_maps:native:spa-first", "google_maps:native:spa-next"}
    # Continued observer coverage after replacement, including removed virtual cards.
    p.evaluate("""() => {
      const n=document.querySelector('[data-review-id=spa-next]').cloneNode(true);
      n.dataset.reviewId='virtual-after-replacement'; collector.panel.append(n); n.remove();
    }""")
    assert len(collected_ids(p)) == 3
    assert p.evaluate("collector.status().diagnostics.panel_reacquisitions") == 1


@pytest.mark.parametrize("change", [
    "document.querySelector('h1').textContent='Other Restaurant';",
    "history.pushState({},'','/maps/place/Other+Restaurant/');",
    "history.pushState({},'','/maps/place/Fixture+Restaurant/data=!1s0x1:0x3');",
])
def test_other_restaurant_stops_before_observer_collects(panel_page, change):
    p = panel_page
    p.evaluate("history.replaceState({},'','/maps/place/Fixture+Restaurant/data=!1s0x1:0x2')")
    p.click("#more-reviews")
    # Restore stable native place identity in this synthetic dialog URL.
    p.evaluate("history.replaceState({},'','/maps/place/Fixture+Restaurant/data=!1s0x1:0x2')")
    p.evaluate("begin({})")
    if change.startswith("document"):
        change = "document.querySelector('#full-dialog').setAttribute('aria-label','Reviews for Other Restaurant');"
    p.evaluate("() => {" + change + "const n=collector.panel.querySelector('[data-review-id]').cloneNode(true); n.dataset.reviewId='foreign'; collector.panel.append(n);}")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.reason") == "page_changed"
    assert all("foreign" not in key for key in collected_ids(p))


def test_failed_open_reports_mode_and_detection_failure(panel_page):
    p = panel_page
    p.evaluate("document.querySelector('#more-reviews').removeAttribute('onclick')")
    result = p.evaluate("async()=>{try {await begin({panelWaitMs:30});return ''} catch(e){return e.message}}")
    assert "Full Reviews" in result
    status = p.evaluate("collector.status()")
    assert status["reason"] == "full_panel_not_ready"
    assert status["diagnostics"]["start_failed_panel_detection"] is True
    assert status["diagnostics"]["mode"] == "PREVIEW_MODE"
    assert status["diagnostics"]["scrollable_found"] is False
    assert collected_ids(p) == []


def test_missing_panel_eventually_stops_with_exact_reason(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("begin({panelWaitMs:0})")
    p.evaluate("document.querySelector('#full-dialog').remove()")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.reason") == "review_panel_closed"


def test_full_dialog_loading_does_not_fall_back_to_previews(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("document.querySelectorAll('#full-dialog [data-review-id]').forEach(n=>n.remove())")
    assert p.evaluate("RRI.findPanel()") is None
    assert p.evaluate("RRI.diagnostics().mode") == "FULL_REVIEWS_MODE"


def test_resume_reacquires_panel_replaced_while_paused(panel_page):
    p = panel_page
    load_fixture(p, "extension_spa.html")
    p.evaluate("begin({panelWaitMs:500})")
    p.evaluate("collector.pause()")
    p.evaluate("replacePanel()")
    assert len(collected_ids(p)) == 1
    p.evaluate("collector.resume()")
    assert p.evaluate("collector.state") == "running"
    assert p.evaluate("collector.panel.id") == "replacement-scroll"
    assert len(collected_ids(p)) == 2


def test_virtualized_last_card_captured_during_panel_gap(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("begin({panelWaitMs:500})")
    p.evaluate("""() => {
      window.detachedCard=collector.panel.querySelector('[data-review-id]').cloneNode(true);
      collector.panel.querySelectorAll('[data-review-id]').forEach(n=>n.remove());
    }""")
    p.evaluate("""() => {
      detachedCard.dataset.reviewId='fleeting-last'; collector.panel.append(detachedCard); detachedCard.remove();
    }""")
    assert len(collected_ids(p)) == 3
    assert p.evaluate("collector.state") == "running"


def test_review_heading_is_not_restaurant_identity(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("""() => {
      document.querySelector('#full-dialog').setAttribute('aria-label','Reviews');
      const name=document.createElement('h2'); name.textContent='Synthetic reviewer heading';
      document.querySelector('#full-scroll [data-review-id]').prepend(name);
    }""")
    assert p.evaluate("RRI.restaurant()") == "Fixture Restaurant"
    p.evaluate("begin({})")
    assert "Synthetic reviewer heading" not in str(p.evaluate("collector.status().diagnostics"))


def test_review_text_and_optional_login_are_not_access_wall(panel_page):
    p = panel_page
    p.click("#more-reviews")
    p.evaluate("""() => {
      document.querySelector('#full-scroll .wiI7pd').textContent='No need to sign in / anmelden to enjoy dinner.';
      const button=document.createElement('button'); button.textContent='Sign in'; document.querySelector('#full-dialog').append(button);
    }""")
    assert p.evaluate("RRI.restriction()") is None
    p.evaluate("begin({})")
    assert p.evaluate("collector.state") == "running"
    # A distinct blocking login modal is still reported even with reviews behind it.
    p.evaluate("""() => { const dialog=document.createElement('div'); dialog.setAttribute('role','dialog'); dialog.textContent='Sign in to continue'; document.body.append(dialog); }""")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.reason") == "access_dialog"
