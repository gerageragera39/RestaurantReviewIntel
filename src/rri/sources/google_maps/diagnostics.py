"""Opt-in, sanitized page diagnostics. No cookies, storage state, or browser profile."""
import logging
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import Error, Page

from rri.sources.google_maps.selectors import SELECTORS

logger = logging.getLogger(__name__)


def save_debug(page: Page, directory: Path, status: str) -> None:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.warning('Could not create debug directory; preserving original scrape status')
        return
    stem = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + status
    # Serialize a scrubbed DOM clone, never page.content() with hydration scripts.
    try:
        snapshot = page.evaluate("""s => {
            const clone = document.documentElement.cloneNode(true);
            const comments = document.createTreeWalker(clone, NodeFilter.SHOW_COMMENT);
            const removeComments = [];
            while (comments.nextNode()) removeComments.push(comments.currentNode);
            for (const comment of removeComments) comment.remove();
            for (const card of clone.querySelectorAll(s.review_card)) {
                for (const node of [card, ...card.querySelectorAll('[aria-label]')]) {
                    if (!/^\\s*[1-5](?:[.,]0)?\\s*(?:stars?|sterne[n]?)\\s*$/i.test(node.getAttribute('aria-label') || ''))
                        node.removeAttribute('aria-label');
                }
            }
            for (const node of clone.querySelectorAll(s.private_nodes)) node.replaceWith(document.createTextNode('[redacted]'));
            for (const node of clone.querySelectorAll(s.snapshot_remove)) node.remove();
            for (const node of clone.querySelectorAll('*')) {
                for (const attribute of [...node.attributes]) {
                    if (!['class', 'role', 'aria-label', 'aria-expanded', 'aria-selected', 'data-review-id'].includes(attribute.name))
                        node.removeAttribute(attribute.name);
                }
                if (/profile|profil|account|konto/i.test(node.getAttribute('aria-label') || '')) node.removeAttribute('aria-label');
            }
            return '<!doctype html>\\n' + clone.outerHTML;
        }""", {'private_nodes': SELECTORS.private_nodes, 'snapshot_remove': SELECTORS.snapshot_remove,
                'review_card': SELECTORS.review_card})
        html_path = directory / f'{stem}.html'
        html_path.write_text(snapshot, encoding='utf-8')
        logger.info('Debug sanitized HTML=%s', html_path)
    except (Error, OSError) as exc:
        logger.warning('Could not save diagnostic HTML (%s)', type(exc).__name__)
    try:
        screenshot_path = directory / f'{stem}.png'
        page.screenshot(path=str(screenshot_path), full_page=False,
                        mask=[page.locator(f":is({SELECTORS.private_nodes}):visible")], timeout=5000)
        logger.info('Debug redacted screenshot=%s', screenshot_path)
    except (Error, OSError) as exc:
        logger.warning('Could not save diagnostic screenshot (%s)', type(exc).__name__)
