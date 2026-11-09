"""Offline stage-log and extension-triggered Reviews-tab/scroll regressions."""
import json
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "extension"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def logging_page(chromium):
    context = chromium.new_context()
    context.route("**/*", lambda route: route.fulfill(body=(FIXTURES / "extension_reviews_tab.html").read_text(encoding="utf-8"), content_type="text/html"))
    p = context.new_page()
    p.goto("https://www.google.com/maps/place/Fixture+Restaurant/")
    for script in ("review-parser.js", "collector.js", "exporter.js"):
        p.add_script_tag(path=EXT / script)
    p.evaluate("""()=>{window.saved={};window.collector=new RRI.Collector({set:async data=>Object.assign(saved,structuredClone(data))});
      window.begin=options=>collector.start({runId:'logging',tabId:1,limit:0,waitMs:60000,panelWaitMs:200,scrollOnStart:true,...options});}""")
    yield p
    context.close()


@pytest.mark.parametrize("label", ["Reviews", "Rezensionen", "Отзывы"])
def test_start_clicks_reviews_tab_then_immediately_scrolls(logging_page, label):
    p = logging_page
    p.evaluate("label=>document.querySelector('#reviews-tab').textContent=label", label)
    p.evaluate("begin({})")
    assert p.evaluate("tabClicks") == 1 and p.evaluate("moreClicks") == 0
    assert p.evaluate("collector.records.size") == 2
    assert p.evaluate("collector.panel.scrollTop") > 0
    assert p.evaluate("window.scrollY") == 0
    events = p.evaluate("collector.events")
    names = [e["event"] for e in events]
    for name in ("start_requested", "open_control_found", "open_control_clicked", "panel_ready", "initial_collection", "scroll_requested", "scroll_result"):
        assert name in names
    assert names.index("open_control_clicked") < names.index("panel_ready") < names.index("scroll_requested")
    assert next(e for e in events if e["event"] == "open_control_found")["details"]["kind"] == "reviews_tab"
    assert next(e for e in events if e["event"] == "scroll_result")["details"]["moved"] is True


def test_failed_start_persists_readable_log_without_reviews(logging_page):
    p = logging_page
    p.evaluate("document.querySelector('#reviews-tab').removeAttribute('onclick');document.querySelector('#more-button').removeAttribute('onclick')")
    p.evaluate("async()=>{try{await begin({panelWaitMs:30})}catch{}}")
    report = p.evaluate("saved['rri:log:logging']")
    assert report["stopping_reason"] == "full_panel_not_ready"
    assert report["events"][-1]["event"] == "start_failed"
    assert report["diagnostics"]["scroll_attempts"] == 0
    assert p.evaluate("collector.records.size") == 0
    encoded = json.dumps(report)
    assert "PRIVATE_REVIEW_TEXT_NOT_FOR_LOGS" not in encoded
    assert "PRIVATE_REVIEWER_NOT_FOR_LOGS" not in encoded
    assert "panel_detection" in encoded


def test_text_limit_logs_why_no_scroll_occurs(logging_page):
    p = logging_page
    p.evaluate("begin({limit:1})")
    report = p.evaluate("saved['rri:log:logging']")
    assert report["stopping_reason"] == "text_limit"
    assert "scroll_requested" not in [e["event"] for e in report["events"]]
    assert p.evaluate("collector.scrolls") == 0


def test_manual_mode_logs_and_does_not_auto_scroll(logging_page):
    p = logging_page
    p.evaluate("begin({autoScroll:false})")
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.scrolls") == 0
    assert "manual_scrolling_enabled" in p.evaluate("collector.events.map(e=>e.event)")


def test_log_retains_start_and_bounded_tail(logging_page):
    p = logging_page
    p.evaluate("begin({autoScroll:false})")
    p.evaluate("async()=>{for(let i=0;i<400;i++)collector.trace('test_pass',{pass:i});await collector.flushLog()}")
    report = p.evaluate("saved['rri:log:logging']")
    assert len(report["events"]) == 300
    assert report["events"][0]["event"] == "start_requested"
    assert report["events"][-1]["details"]["pass"] == 399
    assert report["events_dropped"] > 0


def test_access_failure_is_logged_before_any_click(logging_page):
    p = logging_page
    p.evaluate("document.body.insertAdjacentHTML('afterbegin','<p>Access denied</p>')")
    p.evaluate("async()=>{try{await begin({})}catch{}}")
    report = p.evaluate("saved['rri:log:logging']")
    assert report["stopping_reason"] == "access_restricted"
    assert p.evaluate("tabClicks") == 0


def test_detect_identifies_old_content_listener_even_with_new_parser(logging_page):
    p = logging_page
    p.evaluate("""()=>{window.chrome={runtime:{id:'fixture',onMessage:{addListener:handler=>window.messageHandler=handler}}}}""")
    p.add_script_tag(path=EXT / "content.js")
    p.evaluate("RRI.version='future-parser'")
    result = p.evaluate("() => new Promise(resolve=>messageHandler({type:'RRI',command:'detect'},{id:'fixture'},resolve))")
    assert result["data"]["extension_version"] == "future-parser"
    assert result["data"]["content_script_version"] == "0.1.7"


@pytest.mark.parametrize("label", ["23 reviews", "23 Rezensionen", "Отзывов: 23"])
def test_review_count_button_fallback(logging_page, label):
    p = logging_page
    p.evaluate("label=>{document.querySelector('#reviews-tab').remove();document.querySelector('#more-button').textContent=label}", label)
    assert p.evaluate("RRI.reviewEntry().kind") == "review_count"
    p.evaluate("begin({})")
    assert p.evaluate("collector.records.size") == 2

