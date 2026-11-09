"""Offline synthetic DOM tests. They do NOT verify live Google Maps access."""

import csv
import io
import json
from pathlib import Path

import pytest

from rri.extension_import import load_extension_json, main
from rri.models import DateAccuracy
from rri.storage import EXPORT_FIELDS

EXT = Path(__file__).resolve().parents[1] / "extension"
HTML = Path(__file__).parent / "fixtures" / "extension_reviews.html"


@pytest.fixture
def extension_page(chromium):
    context = chromium.new_context(locale="en-US", timezone_id="Europe/Berlin")
    # All network is fulfilled from a saved local fixture, never Google.
    context.route("**/*", lambda route: route.fulfill(body=HTML.read_text(encoding="utf-8"), content_type="text/html"))
    page = context.new_page()
    page.goto("https://www.google.com/maps/place/Fixture/")
    for script in ("review-parser.js", "collector.js", "exporter.js"):
        page.add_script_tag(path=EXT / script)
    page.evaluate("""() => {
      window.saved = {};
      window.store = {set: async data => { Object.assign(saved, structuredClone(data)); }};
      window.begin = async options => {
        window.collector = new RRI.Collector(store);
        return collector.start({runId:'fixture',tabId:1,waitMs:60000,...options});
      };
    }""")
    yield page
    context.close()


def rows(page):
    page.evaluate("async () => { await collector.queue; }")
    return page.evaluate("[...collector.records.values()]")


def test_extraction_expansion_missing_dates_rating_only(extension_page):
    p = extension_page
    p.evaluate("begin({})")
    data = rows(p)
    assert len(data) == 4
    en, de, rating, missing = data
    assert en["text"] == "Soup was lovely.\nFriendly service, €12 — would return!"
    assert (en["rating"], en["date_raw"], en["date_is_exact"]) == (4, "2 weeks ago", False)
    assert de["date_raw"] == "vor 2 Wochen" and de["rating"] == 5
    assert rating["text"] == "" and rating["rating"] == 3
    assert missing["date_raw"] == "" and missing["date_estimate"] is None
    assert all("reviewer" not in r and "Owner" not in r["text"] for r in data)


@pytest.mark.parametrize("raw,expected,exact", [
    ("2 weeks ago", "2026-10-26", False), ("vor 2 Wochen", "2026-10-26", False),
    ("vor einem Jahr", "2025-11-09", False), ("a month ago", "2026-10-09", False),
    ("yesterday", "2026-11-08", False), ("heute", "2026-11-09", False),
    ("9. November 2026", "2026-11-09", True), ("November 8, 2026", "2026-11-08", True),
    ("09.11.2026", "2026-11-09", True), ("2026-11-09", "2026-11-09", True),
    ("31.02.2026", None, False), ("", None, False), ("an hour ago", None, False),
    ("Bearbeitet: vor einem Jahr", None, False), ("2027-01-01", None, False),
])
def test_dates(extension_page, raw, expected, exact):
    result = extension_page.evaluate("raw => RRI.parseDate(raw, new Date(2026,10,9,12))", raw)
    assert result == {"date_estimate": expected, "date_is_exact": exact}


def test_observer_add_remove_virtualization_and_dedup(extension_page):
    p = extension_page
    p.evaluate("begin({limit:0})")
    # A card appended and removed before the observer callback must still be captured.
    p.evaluate("() => { const n=addCard('fleeting'); n.remove(); addCard('text-en', 'Short'); }")
    assert len(rows(p)) == 5
    p.evaluate("() => { document.querySelectorAll('.jftiEf').forEach(n=>n.remove()); addCard('next-page'); }")
    assert len(rows(p)) == 6
    assert len(p.evaluate("Object.keys(saved).filter(k=>k.startsWith('rri:review:'))")) == 6
    assert p.evaluate("collector.records.get('google_maps:native:text-en').text").startswith("Soup was lovely")


def test_fallback_id_dedup(extension_page):
    p = extension_page
    p.evaluate("begin({limit:0})")
    p.evaluate("() => { for(let i=0;i<2;i++) addCard('temp', 'Identical').removeAttribute('data-review-id'); }")
    data = rows(p)
    assert len(data) == 5
    assert sum(r["review_id"].startswith("google_maps:fallback:") for r in data) == 1


def test_pause_resume_stop_and_manual_scroll(extension_page):
    p = extension_page
    p.evaluate("begin({autoScroll:false,limit:0})")
    p.evaluate("collector.pause()")
    p.evaluate("addCard('during-pause')")
    assert len(rows(p)) == 4
    p.evaluate("collector.resume()")
    assert len(rows(p)) == 5
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.scrolls") == 0
    p.evaluate("collector.finish()")
    p.evaluate("addCard('after-stop')")
    assert len(rows(p)) == 5
    assert p.evaluate("collector.reason") == "user_stop"


@pytest.mark.parametrize("options,setup,reason", [
    ({"limit": 1}, "", "text_limit"),
    ({"limit": 0, "maxIdle": 1}, "await collector.tick();", "no_progress"),
    ({"limit": 0, "maxScrolls": 0}, "", "scroll_budget"),
    ({"limit": 0, "maxMs": 0}, "", "time_budget"),
    ({"limit": 0}, "document.querySelector('#panel').remove();", "review_panel_closed"),
    ({"limit": 0}, "document.querySelector('h1').textContent='Another place';", "page_changed"),
    ({"limit": 0}, "let n=document.createElement('p'); n.textContent='No more reviews'; collector.panel.append(n);", "accessible_end"),
    ({"limit": 0}, "let n=document.createElement('p'); n.textContent='Die Ansicht ist beschränkt'; document.body.append(n);", "restricted_view"),
])
def test_stopping_conditions(extension_page, options, setup, reason):
    p = extension_page
    p.evaluate("begin", options)
    p.evaluate("async () => {" + setup + "await collector.tick();}")
    assert p.evaluate("collector.reason") == reason
    assert p.evaluate("collector.state") == "stopped"
    assert p.evaluate("window.scrollY") == 0


def test_storage_failure_is_reported(extension_page):
    p = extension_page
    p.evaluate("begin({limit:0})")
    p.evaluate("() => {store.set=async()=>{throw Error('disk full')}; addCard('failure');}")
    rows(p)
    assert p.evaluate("collector.state") == "error"
    assert "disk full" in p.evaluate("collector.reason")


def test_scroll_panel_loads_more_without_scrolling_document(extension_page):
    p = extension_page
    p.evaluate("begin({limit:0})")
    p.evaluate("collector.panel.addEventListener('scroll',()=>addCard('from-scroll'),{once:true})")
    p.evaluate("collector.tick()")
    assert len(rows(p)) == 5
    assert p.evaluate("collector.panel.scrollTop") > 0
    assert p.evaluate("window.scrollY") == 0


def test_failed_expansion_is_skipped_and_reported(extension_page):
    p = extension_page
    p.evaluate("document.querySelector('.jftiEf button').removeAttribute('onclick')")
    p.evaluate("begin({limit:0})")
    assert len(rows(p)) == 3
    assert p.evaluate("collector.status().unexpanded") == 1


@pytest.mark.parametrize("label", ["4.5 stars", "0 stars", "6 stars", "not a rating"])
def test_invalid_rating_not_collected(extension_page, label):
    p = extension_page
    p.evaluate("label=>document.querySelector('.kvMYJc').setAttribute('aria-label',label)", label)
    p.evaluate("begin({})")
    assert len(rows(p)) == 3


def test_refuses_preview_and_failed_expansion(extension_page):
    p = extension_page
    p.evaluate("() => {document.querySelector('[role=tab]').remove();document.querySelector('button[aria-label]').remove();document.querySelector('#panel').removeAttribute('aria-label');}")
    assert p.evaluate("RRI.findPanel()") is None
    p.reload()
    p.add_script_tag(path=EXT / "review-parser.js")
    p.evaluate("document.querySelector('.jftiEf button').removeAttribute('onclick')")
    assert p.evaluate("RRI.snapshot(document.querySelector('.jftiEf'), {})") is None


def test_json_csv_and_python_importer_schema(extension_page, tmp_path):
    p = extension_page
    p.evaluate("begin({})")
    rows(p)
    exported = p.evaluate("({json:RRI.toJSON([...collector.records.values()]),csv:RRI.toCSV([...collector.records.values()])})")
    json_rows = json.loads(exported["json"])
    csv_rows = list(csv.DictReader(io.StringIO(exported["csv"])))
    assert set(json_rows[0]) == set(csv_rows[0])
    assert set(EXPORT_FIELDS) <= set(json_rows[0])
    assert csv_rows[0]["text"] == json_rows[0]["text"]
    source = tmp_path / "extension.json"
    source.write_text(exported["json"], encoding="utf-8")
    imported = load_extension_json(source)
    assert len(imported) == 4 and imported[0].date_accuracy is DateAccuracy.ESTIMATED
    assert main([str(source), "--output-prefix", str(tmp_path / "converted")]) == 0
    converted = json.loads((tmp_path / "converted.json").read_text(encoding="utf-8"))
    assert set(converted[0]) == set(EXPORT_FIELDS)
    json_rows[0]["date_is_exact"] = "false"
    source.write_text(json.dumps(json_rows), encoding="utf-8")
    with pytest.raises(ValueError, match="record 1"):
        load_extension_json(source)
