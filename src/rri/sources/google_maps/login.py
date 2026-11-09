"""Manual login only. Wait for explicit user confirmation, then verify Maps access."""

import logging
import threading
import time
from dataclasses import replace
from urllib.parse import urlsplit

from playwright.sync_api import Error, TimeoutError, sync_playwright

from rri.errors import FailureState, ScrapeError
from rri.sources.google_maps.adapter import GoogleMapsAdapter, check_hard_block, validate_maps_url
from rri.sources.google_maps.browser import browser_session

logger = logging.getLogger(__name__)


def manual_login(request, *, login_timeout_ms=600_000):
    try:
        return _manual_login(request, login_timeout_ms=login_timeout_ms)
    except ScrapeError:
        raise
    except TimeoutError as exc:
        raise ScrapeError(FailureState.TIMEOUT, 'Manual-login browser navigation timed out; no login was automated.') from exc
    except Error as exc:
        raise ScrapeError(FailureState.INACCESSIBLE_PAGE,
                          'Manual-login browser could not start or navigate. Check Chromium installation and whether the isolated profile is already in use.') from exc


def _manual_login(request, *, login_timeout_ms):
    if request.profile_dir is None or not request.headed:
        raise ValueError("Manual login requires --profile-dir and a visible browser")
    if type(login_timeout_ms) is not int or login_timeout_ms <= 0:
        raise ValueError("login-timeout-ms must be positive")
    validate_maps_url(request.url)
    adapter = GoogleMapsAdapter()
    adapter.request = replace(request, collection_timeout_ms=login_timeout_ms)
    adapter.deadline = time.monotonic() + login_timeout_ms / 1000
    adapter.phase = "manual_login"
    adapter.signin_prompts = 0
    confirmed = threading.Event()
    input_closed = threading.Event()

    def wait_for_confirmation():
        try:
            input()  # Deliberately discard input. Credentials belong only in Chromium.
            confirmed.set()
        except EOFError:
            input_closed.set()

    with sync_playwright() as playwright:
        with browser_session(playwright, request, request.timeout_ms) as context:
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(request.timeout_ms)
            page.goto(request.url, wait_until="domcontentloaded", timeout=request.timeout_ms)
            print("Manual login window ready. Sign in ONLY in Chromium, return to the restaurant Maps page, "
                  "then press Enter here. No credentials are read or entered by RRI.", flush=True)
            threading.Thread(target=wait_for_confirmation, daemon=True).start()
            try:
                while not confirmed.is_set():
                    if input_closed.is_set():
                        raise ScrapeError(FailureState.INACCESSIBLE_PAGE, "Interactive input is unavailable. Run rri login in a terminal.")
                    pages = [candidate for candidate in context.pages if not candidate.is_closed()]
                    if not pages:
                        try:
                            page = context.wait_for_event('page', timeout=1000)
                        except (Error, TimeoutError) as exc:
                            raise ScrapeError(FailureState.INACCESSIBLE_PAGE, "All login windows closed before confirmation; the profile remains local.") from exc
                    else:
                        page = pages[-1]
                    try:
                        check_hard_block(page)
                        adapter._pause(page, 250)
                    except Error as exc:
                        # Sign-in links can replace a document or open a new tab.
                        # Never treat a transient destroyed JS context as denial.
                        transient = any(message in str(exc).lower() for message in (
                            'execution context was destroyed', 'cannot find context', 'navigation', 'target page, context or browser has been closed',
                        ))
                        if transient:
                            adapter._timeout()
                            continue
                        raise
                # Never snapshot or extract the account/login page.
                maps_pages = [candidate for candidate in context.pages if not candidate.is_closed()
                              and 'google.' in (urlsplit(candidate.url).hostname or '')
                              and '/maps' in urlsplit(candidate.url).path]
                if maps_pages:
                    page = maps_pages[-1]
                if page.is_closed() or (urlsplit(page.url).hostname or "").startswith("accounts.google."):
                    raise ScrapeError(FailureState.INACCESSIBLE_PAGE, "Still on the account page. Finish login and return to Maps before confirming.")
                adapter.deadline = time.monotonic() + request.collection_timeout_ms / 1000
                adapter.phase = "verifying_login"
                page.goto(request.url, wait_until='domcontentloaded', timeout=adapter._timeout())
                adapter._wait_for_place(page)
                validate_maps_url(page.url, allow_short=False)
                adapter._open_reviews(page)
                adapter.full_panel_opened = True
                return {"full_reviews_opened": True, "authentication": adapter._authentication(page),
                        "manual_login_confirmed": True, "profile_saved": True,
                        "status": "ACCESS_VERIFIED", "collected_reviews": 0}
            except ScrapeError as exc:
                exc = adapter._failure_report(exc, page)
                exc.report.update(manual_login_confirmed=confirmed.is_set(), profile_saved=True)
                raise exc
            except KeyboardInterrupt:
                logger.info('Manual login cancelled; no additional account interaction will be attempted')
                raise
            except Error as exc:
                raise ScrapeError(FailureState.INACCESSIBLE_PAGE, "Manual login browser closed or became unavailable; no login was automated.") from exc
