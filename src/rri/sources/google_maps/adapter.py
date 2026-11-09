"""Google Maps public-review workflow using only rendered browser DOM."""
import logging
import re
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright

from rri.dates import parse_review_date
from rri.deduplication import make_review_id
from rri.errors import FailureState, ScrapeError
from rri.models import Review, validate_http_url
from rri.sources.base import CollectionResult, ScrapeRequest
from rri.sources.google_maps.diagnostics import save_debug
from rri.sources.google_maps.extraction import extract_review
from rri.sources.google_maps.browser import browser_session
from rri.sources.google_maps.selectors import (
    SELECTORS, ACCEPT_CONSENT, ALL_REVIEWS_LABEL, BLOCKED_TEXT, CLOSE_LABEL, CONSENT_HEADING, END_LABEL,
    FIND_SCROLL_CONTAINER, LOGIN_LABEL, MORE_LABEL, NEWEST_LABEL,
    REJECT_CONSENT, RESTRICTED_VIEW_LABEL, REVIEW_COUNT_LABEL, REVIEWS_BUTTON_LABEL, REVIEWS_LABEL, SCROLL_CONTAINER, SORT_LABEL, UNSAFE_BROWSER_LABEL,
)

logger = logging.getLogger(__name__)
_GOOGLE_HOST = re.compile(r'^(?:(?:www|maps)\.)?google\.(?:com|[a-z]{2}|co\.uk|com\.au|co\.jp|co\.in|com\.br|com\.mx)$')


def validate_maps_url(url: str, *, allow_short: bool = True) -> str:
    validate_http_url(url)
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if parts.scheme != 'https' or parts.port not in (None, 443):
        raise ValueError('Use an HTTPS Google Maps place URL with the standard port.')
    if allow_short and ((host == 'maps.app.goo.gl' and parts.path.strip('/')) or
                        (host == 'goo.gl' and parts.path.startswith('/maps/'))):
        return url
    query = parse_qs(parts.query)
    is_place = '/maps/place/' in parts.path or any(key in query for key in ('cid', 'ftid', 'query_place_id'))
    is_place = is_place or any(value.startswith('place_id:') for value in query.get('q', []))
    if not _GOOGLE_HOST.fullmatch(host) or not is_place:
        raise ValueError('Expected a Google Maps restaurant place URL, not a search or non-Google URL.')
    return url


def canonical_place_url(url: str) -> str:
    parts = urlsplit(url)
    # Retain identity-bearing query parameters, remove tracking/language parameters.
    from urllib.parse import urlencode
    query = parse_qs(parts.query)
    identity = {key: query[key] for key in ('cid', 'ftid', 'query_place_id', 'q') if key in query}
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(identity, doseq=True), ''))


def first_visible(locator):
    for index in range(locator.count()):
        item = locator.nth(index)
        if item.is_visible():
            return item
    return None


def restaurant_heading(page):
    # A comma-separated selector returns DOM order, not selector priority. Maps
    # may render sponsored-result headings before the restaurant's own heading.
    primary = first_visible(page.locator(SELECTORS.restaurant_name))
    return primary if primary is not None else first_visible(page.locator(SELECTORS.restaurant_name_fallback))


def check_hard_block(page) -> None:
    host = urlsplit(page.url).hostname or ''
    if first_visible(page.get_by_text(UNSAFE_BROWSER_LABEL)) is not None:
        raise ScrapeError(FailureState.INACCESSIBLE_PAGE, 'Google refuses sign-in in this browser; no security or automation restriction will be bypassed.', access_kind='browser_security_block')
    if '/sorry/' in urlsplit(page.url).path or first_visible(page.locator(SELECTORS.blocked_page)) is not None:
        raise ScrapeError(FailureState.BLOCKED_CAPTCHA, 'Google displayed a blocking page or CAPTCHA; collection stopped without bypassing it.', access_kind='captcha')
    # During manual login, inspect only structural CAPTCHA signals on account
    # pages; never read credentials, account-page text, or account identifiers.
    if host.startswith('accounts.google.'):
        return
    headings = ' '.join(page.locator(SELECTORS.heading).all_inner_texts())
    # Do not mistake review text mentioning traffic or CAPTCHA for a challenge.
    if BLOCKED_TEXT.search(headings) or (not page.locator(SELECTORS.review_card).count() and
        BLOCKED_TEXT.search(page.locator(SELECTORS.body).inner_text()[:2000])):
        raise ScrapeError(FailureState.BLOCKED_CAPTCHA, 'Source access restriction or automated-traffic warning; collection cannot proceed.', access_kind='automated_access_blocked')


def check_blocked(page) -> None:
    check_hard_block(page)
    host = urlsplit(page.url).hostname or ''
    if host.startswith('accounts.google.'):
        raise ScrapeError(FailureState.INACCESSIBLE_PAGE, 'Google requires sign-in; use rri login with an isolated profile for manual authentication.', access_kind='login_required')
    for index in range(page.get_by_text(RESTRICTED_VIEW_LABEL).count()):
        warning = page.get_by_text(RESTRICTED_VIEW_LABEL).nth(index)
        if warning.is_visible() and warning.evaluate('(node, card) => !node.closest(card)', SELECTORS.review_card):
            raise ScrapeError(FailureState.INACCESSIBLE_PAGE,
                             'Google reports a restricted Maps view in this session. Use rri login with an isolated profile to check ordinary manually authenticated access.',
                             access_kind='restricted_view', evidence=warning.inner_text())


def displayed_review_count(page):
    values = page.locator(SELECTORS.review_count).evaluate_all("nodes => nodes.map(node => node.getAttribute('aria-label') || '')")
    for value in values:
        match = REVIEW_COUNT_LABEL.fullmatch(value)
        if match:
            number = match.group(1).strip()
            if re.fullmatch(r'\d+|\d{1,3}(?:[.,\s]\d{3})+', number):
                return int(re.sub(r'\D', '', number))
    return None


def find_review_container(page):
    card = first_visible(page.locator(SELECTORS.review_card))
    if card is None:
        raise ScrapeError(FailureState.REVIEWS_NOT_FOUND, 'No visible review cards to locate a review scroll container.')
    handle = card.evaluate_handle(FIND_SCROLL_CONTAINER)
    element = handle.as_element()
    if element is not None:
        return element
    handle.dispose()
    candidates = page.locator(SELECTORS.reviews_container).filter(has=page.locator(SELECTORS.review_card))
    candidate = first_visible(candidates)
    if candidate is not None:
        return candidate.element_handle()
    raise ScrapeError(FailureState.EXTRACTION_FAILED, 'Could not identify a scrollable review container; refusing to scroll the main page.')


class GoogleMapsAdapter:
    def scrape(self, request: ScrapeRequest) -> CollectionResult:
        validate_maps_url(request.url)
        self.request = request
        self.deadline = time.monotonic() + request.collection_timeout_ms / 1000
        self.phase = 'browser_startup'
        self.signin_prompts = 0
        self.full_panel_opened = False
        self.displayed_count_before = None
        self.collected = []
        self.newest = False
        self.all_selected = False
        with sync_playwright() as playwright, ExitStack() as stack:
            context = None
            page = None
            status = 'failed'
            try:
                context = stack.enter_context(browser_session(playwright, request, self._timeout()))
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(request.timeout_ms)
                page.set_default_navigation_timeout(request.timeout_ms)
                self.phase = 'navigation'
                logger.info('Navigation to Google Maps restaurant (headed=%s)', request.headed)
                response = page.goto(request.url, wait_until='domcontentloaded', timeout=self._timeout())
                if response is not None and response.status in (401, 403, 429):
                    raise ScrapeError(FailureState.BLOCKED_CAPTCHA, f'Source denied navigation (HTTP {response.status}).')
                if response is not None and response.status >= 400:
                    raise ScrapeError(FailureState.INACCESSIBLE_PAGE, f'Restaurant navigation returned HTTP {response.status}.')
                self._wait_for_place(page)
                name = restaurant_heading(page).inner_text().strip()
                validate_maps_url(page.url, allow_short=False)
                canonical_url = canonical_place_url(page.url)
                self.displayed_count_before = displayed_review_count(page)
                self.phase = 'opening_reviews'
                self._open_reviews(page)
                self.full_panel_opened = True
                all_reviews = first_visible(page.get_by_role('radio', name=ALL_REVIEWS_LABEL))
                if all_reviews is not None:
                    all_reviews.click(timeout=self._timeout())
                    self.all_selected = all_reviews.get_attribute('aria-checked') == 'true'
                self.phase = 'sorting_reviews'
                newest = self._select_newest(page)
                self.newest = newest
                self.phase = 'collecting_reviews'
                result = self._collect(page, name, canonical_url, newest)
                status = result.stop_reason
                return result
            except ScrapeError as exc:
                status = exc.state.value
                raise self._failure_report(exc, page)
            except PlaywrightTimeout as exc:
                status = FailureState.TIMEOUT.value
                raise self._failure_report(ScrapeError(FailureState.TIMEOUT, f'Timed out during {self.phase}; increase the timeout only if the page is accessible.'), page) from exc
            except PlaywrightError as exc:
                state = FailureState.INACCESSIBLE_PAGE if self.phase in {'browser_startup', 'navigation'} else FailureState.EXTRACTION_FAILED
                status = state.value
                raise self._failure_report(ScrapeError(state, f'Playwright failed during {self.phase}. Check Chromium installation, profile locks, and source access.'), page) from exc
            except ValueError as exc:
                if self.phase == 'browser_startup':
                    raise
                status = FailureState.EXTRACTION_FAILED.value
                raise self._failure_report(ScrapeError(FailureState.EXTRACTION_FAILED, f'Invalid extracted page/review data during {self.phase}: {exc}'), page) from exc
            except OSError as exc:
                status = FailureState.INACCESSIBLE_PAGE.value
                raise self._failure_report(ScrapeError(FailureState.INACCESSIBLE_PAGE, 'Browser profile directory is unavailable or not writable.'), page) from exc
            finally:
                if page is not None and request.debug and not (urlsplit(page.url).hostname or '').startswith('accounts.google.'):
                    save_debug(page, request.debug_dir, status)

    def _authentication(self, page):
        return 'authenticated_ui' if first_visible(page.locator(SELECTORS.authenticated_account)) is not None else 'not_observed'

    def _failure_report(self, error, page):
        records = getattr(self, 'collected', [])
        report = CollectionResult(
            [r for r in records if r.text.strip()], sum(not r.text.strip() for r in records),
            error.access_kind or error.state.value, getattr(self, 'newest', False),
            rating_only_reviews=[r for r in records if not r.text.strip()],
            full_reviews_opened=getattr(self, 'full_panel_opened', False),
        ).summary()
        report.update(status='BLOCKED' if error.state in {FailureState.INACCESSIBLE_PAGE, FailureState.BLOCKED_CAPTCHA, FailureState.CONSENT_REQUIRED} else 'PARTIAL',
                      failure_state=error.state.value, restriction_kind=error.access_kind,
                      restriction_evidence=error.evidence, failure_message=str(error),
                      phase=self.phase, session_mode='persistent_profile' if self.request.profile_dir else 'anonymous',
                      preview_cards_visible=None)
        if page is not None and not page.is_closed() and not (urlsplit(page.url).hostname or '').startswith('accounts.google.'):
            try:
                report.update(displayed_review_count=displayed_review_count(page),
                              authentication=self._authentication(page),
                              preview_cards_visible=page.locator(SELECTORS.review_card).count() if not report['full_reviews_opened'] else 0)
            except PlaywrightError:
                pass
        error.report = report
        return error

    def _timeout(self):
        remaining = int((self.deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise ScrapeError(FailureState.TIMEOUT, f'Overall collection deadline exceeded during {self.phase}; no partial review export was written.')
        return max(1, min(self.request.timeout_ms, remaining))

    def _pause(self, page, milliseconds):
        # Pump browser events while checking the overall collection deadline.
        page.wait_for_timeout(min(milliseconds, self._timeout()))
        self._timeout()

    def _consent(self, page):
        headings = ' '.join(page.locator(SELECTORS.heading).all_inner_texts())
        if not ((urlsplit(page.url).hostname or '').startswith('consent.google.') or CONSENT_HEADING.search(headings)):
            return False
        check_blocked(page)
        for label in (REJECT_CONSENT, ACCEPT_CONSENT):
            button = first_visible(page.get_by_role('button', name=label))
            if button is not None:
                logger.info('Handling standard cookie consent: %s', button.inner_text().strip())
                button.click(timeout=self._timeout())
                return True
        raise ScrapeError(FailureState.CONSENT_REQUIRED, 'Cookie consent is present, but no supported English/German consent choice is available.')

    def _wait_for_place(self, page):
        until = time.monotonic() + self._timeout() / 1000
        consent_clicked = False
        while time.monotonic() < until:
            check_blocked(page)
            consent_present = (urlsplit(page.url).hostname or '').startswith('consent.google.') or CONSENT_HEADING.search(' '.join(page.locator(SELECTORS.heading).all_inner_texts()))
            if consent_present:
                if not consent_clicked:
                    consent_clicked = self._consent(page)
            elif restaurant_heading(page) is not None:
                return
            self._pause(page, 250)
        if consent_clicked or consent_present:
            raise ScrapeError(FailureState.CONSENT_REQUIRED, 'Consent did not resolve within the operation timeout.')
        raise ScrapeError(FailureState.TIMEOUT, 'Restaurant heading did not become visible before the navigation timeout.')

    def _check_access(self, page):
        self._timeout()
        check_blocked(page)
        if (urlsplit(page.url).hostname or '').startswith('consent.google.') or CONSENT_HEADING.search(' '.join(page.locator(SELECTORS.heading).all_inner_texts())):
            raise ScrapeError(FailureState.CONSENT_REQUIRED, 'Cookie consent interrupted review collection.')
        for index in range(page.locator(SELECTORS.dialog).count()):
            dialog = page.locator(SELECTORS.dialog).nth(index)
            if dialog.is_visible() and first_visible(dialog.get_by_role('button', name=LOGIN_LABEL)) is not None:
                close = first_visible(dialog.get_by_role('button', name=CLOSE_LABEL))
                if close is not None and self.signin_prompts == 0:
                    logger.info('Dismissing optional sign-in suggestion using its Close button')
                    close.click(timeout=self._timeout())
                    self.signin_prompts += 1
                    return
                raise ScrapeError(FailureState.INACCESSIBLE_PAGE, 'The source requires sign-in to continue; use rri login for manual authentication.', access_kind='login_required')

    def _open_reviews(self, page):
        logger.info('Opening restaurant reviews section')
        until = time.monotonic() + self._timeout() / 1000
        clicked = False
        review_tab = None
        retried_after_prompt = False
        while time.monotonic() < until:
            self._check_access(page)
            if not clicked:
                tab = first_visible(page.get_by_role('tab', name=REVIEWS_LABEL))
                button = first_visible(page.get_by_role('button', name=REVIEWS_BUTTON_LABEL)) if tab is None else None
                target = tab if tab is not None else button
                if target is not None:
                    review_tab = tab
                    target.click(timeout=self._timeout())
                    clicked = True
                    self._pause(page, 400)
            self._check_access(page)
            tab_selected = review_tab is None or review_tab.get_attribute('aria-selected') == 'true'
            if not tab_selected and self.signin_prompts and not retried_after_prompt:
                clicked = False
                retried_after_prompt = True
            if clicked and tab_selected and first_visible(page.locator(SELECTORS.review_card)) is not None:
                # Only proceed when cards are in a review scroll panel.
                container = find_review_container(page)
                container.dispose()
                return
            self._pause(page, 250)
        if self.signin_prompts:
            raise ScrapeError(FailureState.INACCESSIBLE_PAGE, 'The reviews panel remained unavailable after dismissing a sign-in suggestion; source access may require sign-in.', access_kind='login_required')
        raise ScrapeError(FailureState.REVIEWS_NOT_FOUND, 'Could not open a reviews panel containing public review cards (English/German selectors).')

    def _select_newest(self, page):
        self._check_access(page)
        sort_button = first_visible(page.get_by_role('button', name=SORT_LABEL))
        if sort_button is None:
            logger.warning('Newest sorting is unavailable; retaining displayed source order')
            return False
        sort_button.click(timeout=self._timeout())
        until = time.monotonic() + min(3000, self._timeout()) / 1000
        while time.monotonic() < until:
            self._check_access(page)
            for role in ('menuitemradio', 'menuitem', 'option'):
                target = first_visible(page.get_by_role(role, name=NEWEST_LABEL))
                if target is not None:
                    target.click(timeout=self._timeout())
                    self._pause(page, self.request.scroll_wait_ms)
                    logger.info('Selected Newest review sorting')
                    return True
            target = first_visible(page.get_by_text(NEWEST_LABEL))
            if target is not None:
                target.click(timeout=self._timeout())
                self._pause(page, self.request.scroll_wait_ms)
                logger.info('Selected Newest review sorting')
                return True
            self._pause(page, 100)
        page.keyboard.press('Escape')
        logger.warning('Sort menu has no supported Newest option; retaining displayed source order')
        return False

    def _expand(self, card):
        button = first_visible(card.get_by_role('button', name=MORE_LABEL))
        if button is None:
            button = first_visible(card.locator(SELECTORS.expand_review).filter(has_text=MORE_LABEL))
        if button is not None:
            button.click(timeout=self._timeout())
            try:
                button.wait_for(state='hidden', timeout=self._timeout())
            except PlaywrightTimeout as exc:
                raise ScrapeError(FailureState.EXTRACTION_FAILED, 'A truncated review could not be expanded; refusing to export incomplete text.') from exc

    def _collect(self, page, restaurant_name, canonical_url, newest):
        try:
            return self._collect_bounded(page, restaurant_name, canonical_url, newest)
        except (ScrapeError, PlaywrightTimeout) as exc:
            if isinstance(exc, ScrapeError) and exc.state is not FailureState.TIMEOUT:
                raise
            records = getattr(self, 'collected', [])
            if not records:
                raise
            check_blocked(page)
            logger.warning('Collection timeout: preserving %d validated reviews as PARTIAL', len(records))
            return self._collection_result(page, [r for r in records if r.text.strip()],
                                           [r for r in records if not r.text.strip()], 'collection_timeout', newest)

    def _collect_bounded(self, page, restaurant_name, canonical_url, newest):
        reviews = []
        rating_only_reviews = []
        self.collected = []
        seen = set()
        rating_only_count = 0
        idle = 0
        stop = 'scroll_limit'
        for iteration in range(self.request.max_scroll_iterations + 1):
            self._check_access(page)
            before = len(seen)
            cards = page.locator(SELECTORS.review_card)
            for index in range(cards.count()):
                self._check_access(page)
                card = cards.nth(index)
                if not card.is_visible():
                    continue
                native_id = card.get_attribute(SELECTORS.review_id_attribute)
                if native_id and f'google_maps:native:{native_id.strip()}' in seen:
                    continue
                self._expand(card)
                raw = extract_review(card, SELECTORS)
                identity = make_review_id(
                    provider='google_maps', source_review_id=raw.source_review_id,
                    restaurant_url=canonical_url, text=raw.text, star_rating=raw.star_rating,
                    original_date_text=raw.review_date_raw,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                now = datetime.now(timezone.utc)
                parsed = parse_review_date(raw.review_date_raw, reference_date=now.date())
                review = Review(
                    restaurant_url=self.request.url, restaurant_name=restaurant_name,
                    review_id=identity, text=raw.text, star_rating=raw.star_rating,
                    review_date_raw=raw.review_date_raw, scraped_at=now,
                    date_estimate=parsed.date_estimate, date_accuracy=parsed.accuracy,
                    review_url=raw.review_url,
                )
                self.collected.append(review)
                if not raw.text.strip():
                    rating_only_count += 1
                    rating_only_reviews.append(review)
                    continue
                reviews.append(review)
                if self.request.limit and len(reviews) >= self.request.limit:
                    logger.info('Unique text reviews=%d rating-only=%d total=%d', len(reviews), rating_only_count, len(seen))
                    return self._collection_result(page, reviews, rating_only_reviews, 'limit', newest)
            idle = idle + 1 if len(seen) == before else 0
            logger.info('Scroll iteration=%d text_unique=%d rating_only=%d total_unique=%d idle=%d',
                        iteration, len(reviews), rating_only_count, len(seen), idle)
            end_marker = first_visible(page.get_by_text(END_LABEL))
            if end_marker is not None and end_marker.evaluate('(node, card) => !node.closest(card)', SELECTORS.review_card):
                stop = 'exhausted'
                break
            if idle >= self.request.max_idle_iterations:
                stop = 'idle_limit'
                break
            if iteration == self.request.max_scroll_iterations:
                break
            container = find_review_container(page)
            try:
                container.evaluate(SCROLL_CONTAINER)
            finally:
                container.dispose()
            self._pause(page, self.request.scroll_wait_ms)
        self._check_access(page)
        if not seen:
            raise ScrapeError(FailureState.REVIEWS_NOT_FOUND, 'No public review records were extracted.')
        logger.warning('Collection stopped: %s; text_unique=%d rating_only=%d (requested=%d)',
                       stop, len(reviews), rating_only_count, self.request.limit)
        return self._collection_result(page, reviews, rating_only_reviews, stop, newest)

    def _collection_result(self, page, reviews, rating_only_reviews, stop, newest):
        return CollectionResult(
            reviews, len(rating_only_reviews), stop, newest,
            rating_only_reviews=rating_only_reviews,
            full_reviews_opened=getattr(self, 'full_panel_opened', False),
            displayed_count_before=getattr(self, 'displayed_count_before', None),
            displayed_count_after=displayed_review_count(page),
            all_reviews_selected=getattr(self, 'all_selected', False),
            authentication=self._authentication(page),
            collection_order=list(getattr(self, 'collected', [])),
        )
