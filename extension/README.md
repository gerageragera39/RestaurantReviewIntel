# Local Chrome extension proof of concept

This Manifest V3 extension reads the rendered review DOM in normal Chrome. It
uses no Places API, backend review endpoint, external service, login automation,
cookies API, or Playwright at runtime. The existing Python application is preserved.

**Live Google Maps verification is pending.** The unpacked extension passed offline
tests in an isolated Chromium profile. It has not been installed/tested in the
user's personal Chrome session. No real reviews were collected in this milestone.
See [VERIFICATION.md](VERIFICATION.md).

## Install and collect on Windows

1. Use your normal Google Chrome profile (Chrome 130 or newer). Open
   `chrome://extensions` in the address bar.
2. Turn on **Developer mode** in the upper right.
3. Click **Load unpacked**.
4. Select the folder
   `C:\Users\SED\Documents\RestaurantReviewIntel\extension` itself, which contains
   `manifest.json`. No ZIP, Web Store publication, Python server, or build is needed.
5. Open the supplied Piccolo Mondo URL from `examples\piccolo-mondo.url.txt` in this
   same normal Chrome profile. Confirm the restaurant is Piccolo Mondo at the
   intended location (the supplied URL points to the Ingolstadt area). Open the
   full **Reviews / Rezensionen** panel yourself. Choose All reviews and the desired
   sort order yourself; filters affect the accessible scope.
6. Use Chrome's puzzle-piece menu to open **Restaurant Review Intelligence**.
   Pin it if convenient. Confirm the detected restaurant. Leave the text-review
   limit at **30**, then click **Start Scraping**. The limit counts unique reviews
   with text; rating-only reviews are retained too. **0** removes the text-count
   limit, but other bounds remain.
7. Keep the Maps tab open. The popup can close and reopen while collection
   continues. Use **Pause**, **Resume**, or **Stop**. For manual scrolling, uncheck
   automatic scrolling before Start, then scroll the review panel while collection
   is running. Paused collection does not capture new cards; Resume rescans cards
   still present. The popup shows saved collections even on another tab.
8. Click **Export JSON** and **Export CSV**. An export pauses an active collection
   and waits for queued writes so the file is a consistent saved snapshot. Chrome
   downloads the files normally. Exporting never reads profile/cookie files.
9. Import the actual downloaded JSON into the existing Python model:

   ```powershell
   Set-Location C:\Users\SED\Documents\RestaurantReviewIntel
   # If the existing environment is not already installed:
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\.venv\Scripts\python.exe -m rri.extension_import "$env:USERPROFILE\Downloads\reviews-REPLACE-WITH-ACTUAL-FILENAME.json" --output-prefix data/exports/piccolo-mondo-extension
   ```

   This writes Python-schema JSON and CSV without opening a browser. A malformed
   record produces a numbered validation error; it is not silently dropped.

After editing extension files, reload the extension at `chrome://extensions` and
refresh the Maps tab before another run. Existing saved reviews remain. Reloading
the Maps tab, closing it, navigating, or restarting Chrome interrupts collection;
saved datasets can still be exported. Start creates a new dataset, preserving
earlier runs in the Saved collection selector. Uninstalling the extension removes
its local data. Export before uninstalling. No automatic resume across navigation
or browser restart is attempted.

## Behavior and limits

The popup injects local scripts into the selected HTTPS Google Maps tab using
`activeTab` and `scripting`. Supported host spellings are listed in `mapsURL` in
`popup.js` (including google.com and google.de). It asks for no persistent website
host permissions. `storage` plus `unlimitedStorage` keeps one committed record per
key in extension-owned `chrome.storage.local`, avoiding the normal 10 MB quota.
This storage is separate from page storage and isn't synced to Google's cloud.
Disk and browser resources remain finite. The popup reads metadata separately
from review bodies; only export loads the selected dataset's bodies. See Chrome's
[content-script documentation](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)
and [storage reference](https://developer.chrome.com/docs/extensions/reference/api/storage).

The parser requires evidence of the full Reviews interface and locates the nearest
scrollable ancestor of a review card. It never scrolls the map or document. DOM
selectors live in `review-parser.js` and may require changes as Maps changes. It
clicks recognized More / Mehr controls, excluding owner replies. If expansion
does not succeed, the card is skipped and shown under Unexpanded / skipped; an
incomplete string isn't exported as full text. Empty text is valid for rating-only
reviews. Missing dates remain empty strings, with unknown date precision.

A MutationObserver synchronously snapshots added, changed, and removed review
cards; asynchronous hashing/storage happens afterward. Thus a detached virtualized
card can still be saved. A card never rendered, or whose content is overwritten
before any observer can inspect it, cannot be reconstructed. Explicitly Stop or
Pause before navigating to let pending writes finish; an abrupt crash can lose
writes that have not committed.

Native IDs are preferred. Fallback IDs are SHA-256 over source URL, rating,
normalized text, and original date. Identical anonymous rating-only entries can
collide; edits/relative-date changes/source URL changes can create new fallback
IDs. Fallback IDs cannot establish complete coverage. Longer text replaces shorter
text for a repeated native ID, retaining the initial scrape time. Reviewer names,
avatars, profile URLs, contribution counts, and owner responses aren't collected.
Review text can contain details supplied by its author.

Collected card versions counts distinct parsed versions seen on DOM nodes; Unique
reviews is the deduplicated persisted total. Re-rendering can increase the former.
With dates means a nonempty original displayed date, including unparsed labels.

Default collection bounds: 1.5 seconds between scroll passes, 8 passes without a
new unique ID, 1,000 scrolls, and 30 minutes of wall time including pauses. In
manual mode, supply more cards before the no-progress timeout or start a new run.
The collector also stops on an accessible end marker, source/page change, closed
panel, detected CAPTCHA/restriction/sign-in dialog, storage error, or user Stop.
Background-tab timer throttling can slow collection. Keep the tab visible for the
proof of concept. No-progress/end markers describe accessible DOM exhaustion,
**never guaranteed completeness**. No CAPTCHA solving or access-control evasion is
implemented. A detected restriction stops the run and retains committed records.

## Schema

JSON is an array and CSV has the same fields, including rating-only records.
JSON is UTF-8; CSV is UTF-8 with a BOM for Windows Excel, CRLF rows, and quoted
Unicode/multiline cells. Treat scraped review text as untrusted content; use a
text import when opening CSV in spreadsheets so formulas aren't executed.

| Extension field | Existing Python field / meaning |
| --- | --- |
| review_id | review_id |
| restaurant_name | restaurant_name |
| restaurant_url | restaurant_url (source URL at Start) |
| rating | star_rating, integer 1–5 |
| text | text, expanded review body or empty |
| date_raw | review_date_raw, original displayed label preserved |
| date_estimate | date_estimate, ISO date or null |
| date_is_exact | true only for a valid explicit calendar date |
| scraped_at | scraped_at, UTC ISO timestamp |

Exports also contain `star_rating`, `review_date_raw`, `date_accuracy`, and
`review_url` (null) as Python compatibility aliases. The importer validates aliases
and removes extension-only fields when using the existing atomic Python exporters.
It deduplicates by source URL and ID. Relative dates (German/English) are estimated
against the browser's local calendar day, with month-end clamping. Sub-day,
unrecognized, edited, ambiguous, impossible, and future dates remain unknown.
Original labels always survive, and relative labels never become exact dates.

## Offline tests

```powershell
Set-Location C:\Users\SED\Documents\RestaurantReviewIntel
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.browsers'
# Only needed if Chromium is not already installed:
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest tests/test_extension.py tests/test_extension_runtime.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Saved synthetic HTML covers extraction, English/German dates, unknown/missing
dates, rating-only cards, expansion failures, native/fallback deduplication,
incremental insertion/removal, virtualization, panel-only scrolling, pause/resume,
limits/unlimited mode, no progress, time/scroll bounds, end markers, navigation,
restriction and storage failures, and JSON/CSV/import schema compatibility.
One runtime test loads the actual MV3 extension in a temporary Chromium profile,
seeds synthetic records using the real extension API, closes/reopens the popup,
downloads both formats, restarts that test browser, and checks persistence again.
Another checks actual scripting/messaging, the collector, popup pause/resume/stop,
and exported collected fixture records. That test copies unchanged extension JS
into a temporary package with a **test-only** fixture host permission to substitute
for a person's toolbar `activeTab` invocation; the production manifest has no host
permissions. This does not verify the real toolbar permission grant.
Test data never comes from live Maps. Playwright is a **development test tool** and
is not included in the extension. Tests never use the personal Chrome profile.

## Real-data acceptance check (still pending)

Use Piccolo Mondo in normal Chrome and record actual results in VERIFICATION.md:

1. Record full-panel access, displayed count, chosen filter/sort, unique/text/date
   counts, and exact stop reason. If fewer than 30 text reviews are accessible,
   report that number and reason without substituting fixture data.
2. Pause/close/reopen the popup and confirm the same persisted counts.
3. Export JSON/CSV and import JSON through Python. Check unique IDs, matching
   CSV/JSON fields/counts, nonempty original dates where displayed, ratings 1–5,
   and uncertainty flags. Save real exports under ignored `data/exports/`.
4. Manually compare **10 records** (IDs, full text including expansion, rating,
   and displayed date verbatim) to the actual Maps cards. Prefer Newest sorting
   and samples from the beginning/middle/end. Do not record reviewer identities.
5. Mark the live milestone passed only with at least 30 actual unique text
   reviews and 10 manually confirmed records. Document a lower accessible count
   as a partial result, not success or proof of full history.
