"""Central Google Maps selectors and English/German semantic locator labels.

Class fallbacks can change; keep all provider DOM details in this module.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleMapsSelectors:
    restaurant_name: str = "h1.DUwDvf"
    restaurant_name_fallback: str = "[role='main'] h1"
    review_card: str = "div.jftiEf, [role='article'][data-review-id]"
    review_id_attribute: str = "data-review-id"
    review_text: str = ".wiI7pd, [data-review-text]"
    expand_review: str = "button.w8nwRe, button[aria-expanded='false']"
    star_rating: str = "span.kvMYJc[aria-label], [role='img'][aria-label*='star'], [role='img'][aria-label*='Stern']"
    date_text: str = ".rsqaWe, [data-review-date]"
    review_link: str = "a[href*='reviewid='], a[href*='/reviews/'], a[href*='!1sCh']"
    reviews_container: str = "[role='feed'], .m6QErb.DxyBCb.kA9KIf.dS8AEf"
    blocked_page: str = "#captcha-form, #recaptcha, .g-recaptcha, iframe[src*='recaptcha'], iframe[src*='captcha']"
    consent_dialog: str = "[role='dialog'], form[action*='consent']"
    heading: str = "h1, h2, [role='heading']"
    body: str = "body"
    dialog: str = "[role='dialog']"
    review_count: str = "[role='main'] [aria-label], [role='tab'][aria-label]"
    authenticated_account: str = (
        "[aria-label^='Google Account:'], [aria-label^='Google-Konto:'], "
        "a[href*='accounts.google.com/SignOutOptions']"
    )
    private_nodes: str = (
        ".d4r55, .WNxzHc, .RfnDt, .NBa7we, .al6Kxe, .Tuisuc, "
        "a[href*='/maps/contrib/'], [data-href*='/maps/contrib/'], "
        "a[href*='accounts.google'], [aria-label*='Google Account'], "
        "[aria-label*='Google-Konto'], [data-email], [type='email'], input, textarea, [contenteditable='true'], img"
    )
    snapshot_remove: str = "script, noscript, template, iframe, object, embed, form, input, textarea, meta, link, style, svg"


SELECTORS = GoogleMapsSelectors()
REVIEWS_LABEL = re.compile(r"reviews|rezensionen|bewertungen", re.I)
REVIEWS_BUTTON_LABEL = re.compile(
    r"^(?:[\d.,\s]+\s+(?:reviews|rezensionen|bewertungen)|(?:all|more|see all) reviews\b|(?:alle|weitere) (?:rezensionen|bewertungen)\b)", re.I,
)
SORT_LABEL = re.compile(r"sort(?: reviews)?|sortieren|rezensionen sortieren", re.I)
NEWEST_LABEL = re.compile(r"^(?:newest|most recent|neueste|neueste zuerst|neueste rezensionen)$", re.I)
MORE_LABEL = re.compile(r"^(?:more|see more|read more|mehr|mehr anzeigen|weiterlesen)$", re.I)
LESS_LABEL = re.compile(r"^(?:less|see less|weniger|weniger anzeigen)$", re.I)
REJECT_CONSENT = re.compile(r"^(?:reject all|alle ablehnen)$", re.I)
ACCEPT_CONSENT = re.compile(r"^(?:accept all|alle akzeptieren)$", re.I)
CONSENT_HEADING = re.compile(r"before you continue to google|bevor sie zu google", re.I)
BLOCKED_TEXT = re.compile(
    r"unusual traffic|ungewöhnlichen datenverkehr|not a robot|kein roboter|access denied|zugriff verweigert|automated queries", re.I,
)
LOGIN_LABEL = re.compile(r"^(?:sign in|anmelden)$", re.I)
CLOSE_LABEL = re.compile(r"^(?:close|dismiss|not now|schließen|schliessen|jetzt nicht)$", re.I)
END_LABEL = re.compile(r"you.ve reached the end|no more reviews|keine weiteren rezensionen|ende der liste", re.I)
RESTRICTED_VIEW_LABEL = re.compile(
    r"die ansicht ist beschränkt|limited view of google maps|you(?:'re| are) (?:seeing|using) a limited view", re.I,
)
ALL_REVIEWS_LABEL = re.compile(r"^(?:all reviews|alle rezensionen|alle bewertungen)$", re.I)
REVIEW_COUNT_LABEL = re.compile(r"^\s*([\d.,\s]+)\s+(?:reviews|rezensionen|bewertungen)\s*$", re.I)
UNSAFE_BROWSER_LABEL = re.compile(r"this browser or app may not be secure|dieser browser oder diese app ist (?:möglicherweise|unter umständen) nicht sicher", re.I)

FIND_SCROLL_CONTAINER = """card => {
  for (let node = card.parentElement; node && node !== document.body; node = node.parentElement) {
    const style = getComputedStyle(node);
    if (/(auto|scroll)/.test(style.overflowY) && node.clientHeight > 0) return node;
  }
  return null;
}"""
SCROLL_CONTAINER = """node => {
  const before = node.scrollTop;
  node.scrollTop += Math.max(node.clientHeight * 0.85, 350);
  node.dispatchEvent(new Event('scroll', {bubbles: true}));
  return {before, after: node.scrollTop, height: node.scrollHeight,
          bottom: node.scrollTop + node.clientHeight >= node.scrollHeight - 3};
}"""
