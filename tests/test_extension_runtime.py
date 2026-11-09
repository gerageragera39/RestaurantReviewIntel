"""Real unpacked MV3 runtime, synthetic records, no network or personal profile."""

import json
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


EXT = Path(__file__).resolve().parents[1] / "extension"


@pytest.mark.parametrize("fail_to_open,fixture_name", [(False, "extension_reviews_tab.html"), (True, "extension_reviews_tab.html"), (False, "extension_colab_filter.html")])
def test_real_extension_tab_start_and_log_export_after_popup_reopen(tmp_path, fail_to_open, fixture_name):
    test_extension = tmp_path / "logging-extension"
    shutil.copytree(EXT, test_extension)
    manifest_path = test_extension / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["host_permissions"] = ["https://www.google.com/*"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    fixture = (Path(__file__).parent / "fixtures" / fixture_name).read_text(encoding="utf-8")
    filter_case = fixture_name == "extension_colab_filter.html"
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(tmp_path / "logging-profile"), channel="chromium", headless=True,
            args=[f"--disable-extensions-except={test_extension}", f"--load-extension={test_extension}"],
        )
        context.route("https://**/*", lambda route: route.fulfill(body=fixture, content_type="text/html") if route.request.url.startswith("https://www.google.com/maps/") else route.abort())
        try:
            manager = context.pages[0]
            manager.goto("chrome://extensions")
            item = manager.locator("extensions-item").filter(has_text="Restaurant Review Intelligence")
            item.wait_for()
            popup_url = f"chrome-extension://{item.get_attribute('id')}/popup.html"
            maps = context.new_page()
            maps.goto("https://www.google.com/maps/place/co:Lab/" if filter_case else "https://www.google.com/maps/place/Fixture+Restaurant/")
            if fail_to_open:
                maps.evaluate("document.querySelector('#reviews-tab').onclick=null;document.querySelector('#more-button').onclick=null")
            popup = context.new_page()
            popup.goto(popup_url)
            result = popup.evaluate("""async () => {
              const [tab]=await chrome.tabs.query({url:'https://www.google.com/maps/*'});
              await chrome.scripting.executeScript({target:{tabId:tab.id},files:['review-parser.js','collector.js','content.js']});
              return await chrome.tabs.sendMessage(tab.id,{type:'RRI',command:'start',options:{runId:'log-runtime',tabId:tab.id,limit:0,autoScroll:true,panelWaitMs:100}});
            }""")
            assert result["ok"] is not fail_to_open
            if not fail_to_open:
                assert maps.locator("#full-scroll" if filter_case else "#tab-scroll").evaluate("n=>n.scrollTop") > 0
            popup.close()
            popup = context.new_page()
            popup.goto(popup_url)
            popup.wait_for_function("() => !document.querySelector('#logs').disabled")
            if fail_to_open:
                assert popup.locator("#json").is_disabled()
            with popup.expect_download() as download_info:
                popup.locator("#logs").click()
            destination = tmp_path / "diagnostic.json"
            download_info.value.save_as(destination)
            report = json.loads(destination.read_text(encoding="utf-8"))
            assert report["type"] == "rri_diagnostic_log"
            assert report["journal"]["extension_version"] == "0.1.7"
            events = report["journal"]["events"]
            assert any(e["event"] == "open_control_clicked" for e in events)
            if filter_case:
                assert report["run"]["unique"] >= 11
                assert "Synthetic full review." not in destination.read_text(encoding="utf-8")
            if fail_to_open:
                assert report["journal"]["stopping_reason"] == "full_panel_not_ready"
                assert any(e["event"] == "start_failed" for e in events)
            else:
                assert any(e["event"] == "scroll_result" and e["details"]["moved"] for e in events)
            assert "PRIVATE_REVIEW_TEXT_NOT_FOR_LOGS" not in destination.read_text(encoding="utf-8")
            assert "PRIVATE_REVIEWER_NOT_FOR_LOGS" not in destination.read_text(encoding="utf-8")
            popup.locator("#log-details summary").click()
            popup.wait_for_function("event => document.querySelector('#log-view').textContent.includes(event)", arg="start_failed" if fail_to_open else "scroll_result")
        finally:
            context.close()


def test_real_message_bridge_collection_controls_and_export(tmp_path):
    # Test-only host permission substitutes for a human invoking the toolbar's
    # activeTab grant. Production manifest has no host_permissions. All JS and
    # popup files are copied unchanged. Never point this context at live Maps.
    test_extension = tmp_path / "test-extension"
    shutil.copytree(EXT, test_extension)
    manifest_path = test_extension / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["host_permissions"] = ["https://www.google.com/*"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    fixture = (Path(__file__).parent / "fixtures" / "extension_reviews.html").read_text(encoding="utf-8")
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(tmp_path / "bridge-profile"), channel="chromium", headless=True,
            args=[f"--disable-extensions-except={test_extension}", f"--load-extension={test_extension}"],
        )
        context.route("https://**/*", lambda route: route.fulfill(body=fixture, content_type="text/html") if route.request.url.startswith("https://www.google.com/maps/") else route.abort())
        try:
            manager = context.pages[0]
            manager.goto("chrome://extensions")
            item = manager.locator("extensions-item").filter(has_text="Restaurant Review Intelligence")
            item.wait_for()
            extension_id = item.get_attribute("id")
            maps = context.new_page()
            maps.goto("https://www.google.com/maps/place/Fixture/")
            popup = context.new_page()
            popup.goto(f"chrome-extension://{extension_id}/popup.html")
            result = popup.evaluate("""async () => {
              const [tab] = await chrome.tabs.query({url:'https://www.google.com/maps/*'});
              await chrome.scripting.executeScript({target:{tabId:tab.id},files:['review-parser.js','collector.js','content.js']});
              return await chrome.tabs.sendMessage(tab.id,{type:'RRI',command:'start',options:{runId:'bridge',tabId:tab.id,limit:30,autoScroll:false}});
            }""")
            assert result["ok"], result
            popup.locator("#unique").filter(has_text="4").wait_for()
            assert popup.locator("#withText").inner_text() == "3"
            popup.locator("#pause").click()
            popup.locator("#status").filter(has_text="paused").wait_for()
            popup.locator("#pause").click()
            popup.locator("#status").filter(has_text="running").wait_for()
            maps.evaluate("addCard('bridge-added')")
            popup.locator("#unique").filter(has_text="5").wait_for()
            popup.locator("#stop").click()
            popup.locator("#status").filter(has_text="user_stop").wait_for()
            with popup.expect_download() as download_info:
                popup.locator("#json").click()
            destination = tmp_path / "bridge.json"
            download_info.value.save_as(destination)
            data = json.loads(destination.read_text(encoding="utf-8"))
            assert len(data) == 5
            assert sum(bool(r["text"]) for r in data) == 4
            assert any(r["review_id"].endswith("bridge-added") for r in data)
        finally:
            context.close()


def test_real_extension_storage_popup_reopen_and_downloads(tmp_path):
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(tmp_path / "isolated-profile"), channel="chromium", headless=True,
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        )
        context.route("https://**/*", lambda route: route.abort())
        try:
            manager = context.pages[0]
            manager.goto("chrome://extensions")
            item = manager.locator("extensions-item").filter(has_text="Restaurant Review Intelligence")
            item.wait_for()
            extension_id = item.get_attribute("id")
            popup_url = f"chrome-extension://{extension_id}/popup.html"
            popup = context.new_page()
            popup.goto(popup_url)
            record = {
                "review_id": "google_maps:native:synthetic", "restaurant_name": "Fixture Restaurant",
                "restaurant_url": "https://www.google.com/maps/place/Fixture/", "rating": 5,
                "text": 'Synthetic soup, "excellent" — €12\nSecond line.', "date_raw": "vor 2 Wochen",
                "date_estimate": "2026-10-26", "date_is_exact": False, "scraped_at": "2026-11-09T10:00:00Z",
            }
            popup.evaluate("""async record => { await chrome.storage.local.set({
              'rri:review:persisted:synthetic': record,
              'rri:run:persisted': {runId:'persisted',tabId:-1,restaurant_name:record.restaurant_name,
                state:'stopped',reason:'fixture',observed:2,unique:1,withText:1,withDates:1,unexpanded:0}
            }); }""", record)
            popup.close()
            popup = context.new_page()
            popup.goto(popup_url)
            popup.locator("#unique").filter(has_text="1").wait_for()
            assert popup.locator("#withText").inner_text() == "1"
            assert popup.locator("#status").inner_text() == "stopped: fixture"
            for fmt in ("json", "csv"):
                with popup.expect_download() as download_info:
                    popup.locator(f"#{fmt}").click()
                destination = tmp_path / f"export.{fmt}"
                download_info.value.save_as(destination)
                body = destination.read_text(encoding="utf-8-sig")
                assert "vor 2 Wochen" in body and "Synthetic soup" in body
                if fmt == "json":
                    data = json.loads(body)
                    assert data[0]["rating"] == data[0]["star_rating"] == 5
            # The same production popup localizes controls/status without changing
            # review data and remembers each choice after closing/reopening it.
            for language, start_label, status_label in (
                ("de", "Sammlung starten", "gestoppt: fixture"),
                ("ru", "Начать сбор", "остановлено: fixture"),
                ("en", "Start Scraping", "stopped: fixture"),
            ):
                popup.locator("#language").select_option(language)
                popup.wait_for_function("label=>document.querySelector('#status').textContent===label", arg=status_label)
                popup.close()
                popup = context.new_page()
                popup.goto(popup_url)
                popup.locator("#start").filter(has_text=start_label).wait_for()
                assert popup.locator("html").get_attribute("lang") == language
                assert popup.locator("#unique").inner_text() == "1"
                popup.locator("body").screenshot(path=tmp_path / f"popup-{language}.png")
            # Survives an entire browser context restart, not just popup memory.
            popup.close()
        finally:
            context.close()
        context = pw.chromium.launch_persistent_context(
            str(tmp_path / "isolated-profile"), channel="chromium", headless=True,
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        )
        try:
            context.route("https://**/*", lambda route: route.abort())
            popup = context.new_page()
            popup.goto(popup_url)
            popup.locator("#unique").filter(has_text="1").wait_for()
            assert popup.locator("#withDates").inner_text() == "1"
        finally:
            context.close()
