"""Three-language saved-DOM tests. Live authenticated Chrome is not exercised."""
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "extension"
FIXTURE = Path(__file__).parent / "fixtures" / "extension_multilingual_reviews.html"


@pytest.fixture
def language_page(chromium):
    context = chromium.new_context(timezone_id="Europe/Berlin")
    context.route("**/*", lambda route: route.fulfill(body=FIXTURE.read_text(encoding="utf-8"), content_type="text/html"))
    p = context.new_page()
    p.goto("https://www.google.com/maps/place/Fixture+Restaurant/")
    for script in ("review-parser.js", "collector.js", "exporter.js"):
        p.add_script_tag(path=EXT / script)
    p.evaluate("""() => {window.saved={};window.collector=new RRI.Collector({set:async value=>Object.assign(saved,structuredClone(value))});
      window.begin=()=>collector.start({runId:'languages',tabId:1,waitMs:60000,panelWaitMs:500,limit:0});}""")
    yield p
    context.close()


@pytest.mark.parametrize("language,raw,expanded", [
    ("en", "3 weeks ago", "Complete English review."),
    ("de", "vor 3 Wochen", "Vollständige deutsche Rezension."),
    ("ru", "3 недели назад", "Полный текст отзыва."),
])
def test_three_language_preview_full_expansion_scroll_and_export(language_page, language, raw, expanded):
    p = language_page
    p.evaluate("showLocale", language)
    assert p.evaluate("RRI.inspect().mode") == "PREVIEW_MODE"
    assert p.evaluate("RRI.cards(document).length") == 3
    p.evaluate("begin()")
    assert p.evaluate("collector.panel.id") == "review-scroll"
    assert p.evaluate("RRI.restaurant()") == "Fixture Restaurant"
    assert p.evaluate("collector.records.size") == 2
    data = p.evaluate("[...collector.records.values()]")
    assert data[0]["text"] == expanded
    assert data[0]["date_raw"] == raw
    assert data[0]["date_is_exact"] is False and data[0]["date_estimate"] is not None
    assert data[1]["text"] == "" and data[1]["rating"] == 5
    p.evaluate("collector.tick()")
    p.evaluate("async()=>{await collector.queue}")
    assert p.evaluate("collector.records.size") == 3
    assert p.evaluate("window.scrollY") == 0
    exported = p.evaluate("JSON.parse(RRI.toJSON([...collector.records.values()]))")
    assert len(exported) == 3
    assert all(r["rating"] == r["star_rating"] == 5 for r in exported)
    assert exported[0]["date_raw"] == exported[0]["review_date_raw"] == raw
    assert not any("preview" in r["review_id"] for r in exported)
    assert p.evaluate("RRI.diagnostics().supported_languages") == ["en", "de", "ru"]


@pytest.mark.parametrize("label,rating", [
    ("1 star", 1), ("4 Sterne", 4), ("1 звезда", 1), ("2 звезды", 2),
    ("3 звезды", 3), ("4 звезды", 4), ("5 звезд", 5), ("5 звёзд", 5), ("4,0 из 5 звезд", 4),
    ("4,7-звездочные", None), ("4.5 stars", None), ("0 звезд", None), ("6 звезд", None),
])
def test_localized_ratings_without_provider_class(language_page, label, rating):
    p = language_page
    p.evaluate("label=>document.querySelector('[role=img]').setAttribute('aria-label',label)", label)
    snapshot = p.evaluate("RRI.snapshot(document.querySelector('.jftiEf'),{})")
    assert (snapshot["rating"] if snapshot else None) == rating


@pytest.mark.parametrize("raw,expected,exact", [
    ("3 недели назад", "2026-10-19", False), ("неделю назад", "2026-11-02", False),
    ("2 недели назад", "2026-10-26", False), ("5 недель назад", "2026-10-05", False),
    ("день назад", "2026-11-08", False), ("2 дня назад", "2026-11-07", False), ("5 дней назад", "2026-11-04", False),
    ("месяц назад", "2026-10-09", False), ("2 месяца назад", "2026-09-09", False), ("5 месяцев назад", "2026-06-09", False),
    ("год назад", "2025-11-09", False), ("2 года назад", "2024-11-09", False), ("5 лет назад", "2021-11-09", False),
    ("сегодня", "2026-11-09", False), ("вчера", "2026-11-08", False),
    ("9 ноября 2026", "2026-11-09", True), ("8 ноября 2026 г.", "2026-11-08", True),
    ("31 февраля 2026", None, False), ("10 ноября 2026", None, False),
    ("Изменено: 3 недели назад", None, False), ("час назад", None, False), ("5 минут назад", None, False),
    ("3 недели назад НОВЫЙ", None, False), ("", None, False),
    ("3 weeks ago", "2026-10-19", False), ("vor 3 Wochen", "2026-10-19", False),
])
def test_localized_dates_conserve_precision(language_page, raw, expected, exact):
    result = language_page.evaluate("raw=>RRI.parseDate(raw,new Date(2026,10,9,12))", raw)
    assert result == {"date_estimate": expected, "date_is_exact": exact}


@pytest.mark.parametrize("text,reason,dialog", [
    ("Access denied", "access_restricted", False), ("Zugriff verweigert", "access_restricted", False), ("Доступ запрещён", "access_restricted", False),
    ("Limited view of Google Maps", "restricted_view", False), ("Die Ansicht ist beschränkt", "restricted_view", False), ("Это ограниченная версия Google Карт.", "restricted_view", False),
    ("Sign in to continue", "access_dialog", True), ("Anmelden", "access_dialog", True), ("Войдите в аккаунт", "access_dialog", True),
    ("Этот браузер или приложение может быть небезопасным", "browser_security_block", False),
])
def test_localized_restrictions_are_reported(language_page, text, reason, dialog):
    p = language_page
    p.evaluate("""data=>{const n=document.createElement('div');if(data.dialog)n.setAttribute('role','dialog');n.textContent=data.text;document.body.append(n)}""", {"text": text, "dialog": dialog})
    assert p.evaluate("RRI.restriction()") == reason


@pytest.mark.parametrize("language,text", [
    ("en", "No more reviews"), ("de", "Keine weiteren Rezensionen"), ("ru", "Вы просмотрели все отзывы"),
])
def test_localized_end_marker_stops_collection(language_page, language, text):
    p = language_page
    p.evaluate("showLocale", language)
    p.evaluate("begin()")
    p.evaluate("text=>{const n=document.createElement('p');n.textContent=text;collector.panel.append(n)}", text)
    p.evaluate("collector.tick()")
    assert p.evaluate("collector.reason") == "accessible_end"
