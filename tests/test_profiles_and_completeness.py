import json
import time
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from rri.config import ScrapeConfig
from rri.errors import FailureState, ScrapeError
from rri.service import scrape_and_export
from rri.sources.base import CollectionResult, ScrapeRequest
from rri.sources.google_maps.adapter import GoogleMapsAdapter, check_blocked, displayed_review_count
from rri.sources.google_maps.browser import prepare_profile


def test_profile_is_isolated_and_git_ignored(tmp_path):
    profile = prepare_profile(tmp_path / 'profile')
    assert (profile / '.gitignore').read_text(encoding='utf-8').strip() == '*'
    assert prepare_profile(profile) == profile
    normal_profile = tmp_path / 'normal-chrome'
    normal_profile.mkdir()
    (normal_profile / 'Preferences').write_text('{}')
    with pytest.raises(ValueError, match='existing non-RRI'):
        prepare_profile(normal_profile)


def test_actual_persistent_context_retains_synthetic_session(tmp_path):
    # Synthetic test origin/session only. Never read the user's login profile.
    profile = prepare_profile(tmp_path / 'test-profile')
    with sync_playwright() as playwright:
        for run in range(2):
            context = playwright.chromium.launch_persistent_context(str(profile), headless=True)
            try:
                context.route('**/*', lambda route: route.fulfill(body='<h1>Offline profile test</h1>'))
                page = context.new_page()
                page.goto('https://rri-fixture.invalid/')
                if run == 0:
                    page.evaluate("localStorage.setItem('rri_test', 'persisted'); document.cookie='rri_fixture=synthetic;max-age=3600;secure'")
                else:
                    assert page.evaluate("localStorage.getItem('rri_test')") == 'persisted'
                    assert page.evaluate("document.cookie.includes('rri_fixture=synthetic')")
            finally:
                context.close()


def test_limit_zero_configuration_and_export(review, tmp_path):
    class Adapter:
        def scrape(self, request):
            assert request.limit == 0
            return CollectionResult([review, replace(review, review_id='second')])
    result = scrape_and_export(url=review.restaurant_url, config=ScrapeConfig(
        limit=0, export_dir=tmp_path / 'exports', report_dir=tmp_path / 'reports'), adapter=Adapter())
    assert result.review_count == 2
    assert len(json.loads(result.json_path.read_text(encoding='utf-8'))) == 2
    assert result.status == 'PARTIAL'


def test_unlimited_collects_text_and_rating_only_until_idle(load_html, adapter):
    page = load_html('workflow.html')
    adapter.request = replace(adapter.request, limit=0)
    adapter._open_reviews(page)
    adapter.full_panel_opened = True
    adapter.all_selected = True
    adapter.displayed_count_before = displayed_review_count(page)
    result = adapter._collect(page, 'Fixture Restaurant', adapter.request.url, adapter._select_newest(page))
    assert result.unique_count == 4 and len(result.reviews) == 3
    assert len(result.rating_only_reviews) == 1
    assert result.stop_reason == 'idle_limit'
    assert result.completeness == 'COMPLETE'
    assert result.summary()['with_raw_dates'] == 4
    assert result.summary()['with_normalized_dates'] == 4
    assert [r.review_id.rsplit(':', 1)[-1] for r in result.records] == ['one', 'rating', 'two', 'three']
    assert page.evaluate('window.scrollY') == 0


@pytest.mark.parametrize('changes', [
    {'displayed_count_after': 3}, {'displayed_count_before': None},
    {'displayed_count_after': None}, {'full_reviews_opened': False},
    {'all_reviews_selected': False}, {'stop_reason': 'limit'},
    {'stop_reason': 'scroll_limit'}, {'stop_reason': 'collection_timeout'},
])
def test_completeness_requires_independent_coverage(review, changes):
    batch = CollectionResult([review], stop_reason='idle_limit', full_reviews_opened=True,
                             displayed_count_before=1, displayed_count_after=1, all_reviews_selected=True)
    assert batch.completeness == 'COMPLETE'
    assert replace(batch, **changes).completeness == 'PARTIAL'


def test_fallback_id_cannot_prove_completeness(review):
    batch = CollectionResult([replace(review, review_id='google_maps:fallback:hash')],
                             stop_reason='exhausted', full_reviews_opened=True, all_reviews_selected=True,
                             displayed_count_before=1, displayed_count_after=1)
    assert batch.completeness == 'PARTIAL'


def test_login_required_detection(page):
    page.route('**/*', lambda route: route.fulfill(body='<h1>Sign in</h1><input type="password">'))
    page.goto('https://accounts.google.com/ServiceLogin')
    with pytest.raises(ScrapeError) as caught:
        check_blocked(page)
    assert caught.value.access_kind == 'login_required'


def test_restricted_view_is_not_a_captcha(load_html):
    page = load_html('restricted.html')
    with pytest.raises(ScrapeError) as caught:
        check_blocked(page)
    assert caught.value.state is FailureState.INACCESSIBLE_PAGE
    assert caught.value.access_kind == 'restricted_view'
    assert 'Die Ansicht ist beschränkt' in caught.value.evidence


@pytest.mark.parametrize('label, expected', [('1,234 reviews', 1234), ('1.234 Rezensionen', 1234),
                                           ('59 Rezensionen', 59), ('1.2K reviews', None)])
def test_displayed_total_count_is_not_guessed(page, label, expected):
    page.set_content('<div role="main"><span role="img"></span></div>')
    page.get_by_role('img').evaluate('(node, label) => node.setAttribute("aria-label", label)', label)
    assert displayed_review_count(page) == expected


def test_timeout_preserves_only_previously_validated_records(load_html, adapter, monkeypatch):
    page = load_html('reviews_en.html')
    adapter.request = replace(adapter.request, limit=0)
    def expire_after_first_scroll(page, milliseconds):
        adapter.deadline = time.monotonic() - 1
        adapter._timeout()
    monkeypatch.setattr(adapter, '_pause', expire_after_first_scroll)
    result = adapter._collect(page, 'Fixture Restaurant', adapter.request.url, False)
    assert result.stop_reason == 'collection_timeout' and result.completeness == 'PARTIAL'
    assert result.unique_count == 3


def test_profile_option_flows_to_source(review, tmp_path):
    class Adapter:
        def scrape(self, request):
            assert request.profile_dir == tmp_path / 'profile'
            return CollectionResult([review])
    result = scrape_and_export(url=review.restaurant_url, config=ScrapeConfig(
        profile_dir=tmp_path / 'profile', export_dir=tmp_path / 'exports', report_dir=tmp_path / 'reports'), adapter=Adapter())
    report = json.loads(result.report_path.read_text(encoding='utf-8'))
    assert report['session_mode'] == 'persistent_profile'


@pytest.mark.parametrize('message', [
    'Dieser Browser oder diese App ist unter Umständen nicht sicher.',
    'Dieser Browser oder diese App ist möglicherweise nicht sicher.',
    'This browser or app may not be secure.',
])
def test_security_rejection_stops_without_inspecting_form(page, message):
    from rri.sources.google_maps.adapter import check_hard_block
    page.set_content('<h1></h1><input type="email" value="synthetic@example.invalid">')
    page.locator('h1').evaluate('(node, text) => node.innerText=text', message)
    with pytest.raises(ScrapeError) as caught:
        check_hard_block(page)
    assert caught.value.access_kind == 'browser_security_block'
    assert 'synthetic@example.invalid' not in str(caught.value)


def test_persistent_adapter_and_manual_login_navigation(tmp_path, monkeypatch):
    from playwright.sync_api import BrowserType, Error
    from rri.sources.google_maps import login

    markup = (Path(__file__).parent / 'fixtures/workflow.html').read_text(encoding='utf-8')
    markup += '<a aria-label="Google Account: Synthetic fixture account"></a>'
    original = BrowserType.launch_persistent_context
    launches = []

    def intercepted_launch(browser_type, **kwargs):
        context = original(browser_type, **kwargs)
        context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=markup))
        launches.append(kwargs)
        return context

    monkeypatch.setattr(BrowserType, 'launch_persistent_context', intercepted_launch)
    calls = []
    original_check = login.check_hard_block

    def transient_navigation(page):
        calls.append(True)
        if len(calls) == 1:
            raise Error('Execution context was destroyed, most likely because of a navigation')
        original_check(page)

    def manual_confirmation():
        time.sleep(0.15)
        return ''

    monkeypatch.setattr(login, 'check_hard_block', transient_navigation)
    monkeypatch.setattr('builtins.input', manual_confirmation)
    request = ScrapeRequest(url='https://www.google.com/maps/place/Fixture/',
                            profile_dir=tmp_path / 'isolated-profile', headed=True,
                            timeout_ms=2000, scroll_wait_ms=30, max_idle_iterations=2)
    # Actual headed browser is not needed for a fixture test; retain the login
    # contract but launch the test browser headless at the interception boundary.
    def fixture_launch(browser_type, **kwargs):
        return intercepted_launch(browser_type, **{**kwargs, 'headless': True})
    monkeypatch.setattr(BrowserType, 'launch_persistent_context', fixture_launch)
    result = login.manual_login(request, login_timeout_ms=10000)
    assert result['full_reviews_opened'] and result['manual_login_confirmed']
    assert len(calls) >= 2
    assert launches[0]['user_data_dir'] == str(request.profile_dir.resolve())
    batch = GoogleMapsAdapter().scrape(replace(request, headed=False, limit=0))
    assert batch.full_reviews_opened and batch.unique_count == 4
    assert batch.completeness == 'COMPLETE'


def test_busy_profile_is_an_explicit_startup_failure(tmp_path, monkeypatch):
    from playwright.sync_api import BrowserType, Error
    def fail(*args, **kwargs):
        raise Error('Profile is already in use')
    monkeypatch.setattr(BrowserType, 'launch_persistent_context', fail)
    with pytest.raises(ScrapeError) as caught:
        GoogleMapsAdapter().scrape(ScrapeRequest(
            url='https://www.google.com/maps/place/Fixture/', profile_dir=tmp_path / 'profile', headed=False))
    assert caught.value.state is FailureState.INACCESSIBLE_PAGE
    assert caught.value.report['phase'] == 'browser_startup'


def test_report_disk_error_does_not_hide_access_denial(tmp_path):
    report_path = tmp_path / 'not-a-directory'
    report_path.write_text('fixture')
    class Adapter:
        def scrape(self, request):
            raise ScrapeError(FailureState.INACCESSIBLE_PAGE, 'Fixture restricted view')
    with pytest.raises(ScrapeError) as caught:
        scrape_and_export(url='https://www.google.com/maps/place/Fixture/',
                          config=ScrapeConfig(export_dir=tmp_path / 'exports', report_dir=report_path), adapter=Adapter())
    assert caught.value.state is FailureState.INACCESSIBLE_PAGE
