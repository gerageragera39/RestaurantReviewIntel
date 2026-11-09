# Local Chrome extension proof of concept

This Manifest V3 extension reads the rendered review DOM in normal Chrome. It
uses no Places API, backend review endpoint, external service, login automation,
cookies API, or Playwright at runtime. The existing Python application is preserved.

**Full-list live verification is pending.** The user manually tested the earlier
build and reported three preview reviews, followed by failure after More reviews.
The focused 0.1.6 fix is verified against saved fixtures and an isolated extension
runtime; it has not been retested in the user's personal Chrome session.
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
   full review panel yourself, or leave the restaurant overview open and let Start
   click **Reviews / Rezensionen / Отзывы**, **More reviews / Weitere Rezensionen /
   Ещё отзывы**, or the review-count button. Choose All reviews and the desired
   sort order yourself; filters affect the accessible scope.
6. Use Chrome's puzzle-piece menu to open **Restaurant Review Intelligence**.
   Pin it if convenient. Choose **English / Deutsch / Русский** under
   **Language / Sprache / Язык**. This choice is saved locally and changes the
   popup controls, common statuses, messages, and help text; it does not change
   Google Maps itself. Maps parsing recognizes all three languages independently
   of this setting. Confirm the detected restaurant. Leave the text-review
   limit at **30**, then click **Start Scraping**. Start waits up to 10 seconds for
   a verified full panel with accessible review cards. It then immediately attempts
   a panel scroll if automatic scrolling is enabled and the text limit isn't
   already reached. Preview cards are excluded.
   The limit counts unique reviews
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
the Maps tab, closing it, navigating to another place, or restarting Chrome interrupts collection;
saved datasets can still be exported. Start creates a new dataset, preserving
earlier runs in the Saved collection selector. Uninstalling the extension removes
its local data. Export before uninstalling. No automatic resume after a document
reload or browser restart is attempted; same-place SPA panel transitions are supported.

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

The parser distinguishes PREVIEW_MODE from FULL_REVIEWS_MODE using scoped interface
evidence, rather than card count. An active full-reviews dialog takes precedence
over preview cards. Labelled feeds/regions, scoped sort controls, and the selected
Reviews / Rezensionen / Отзывы tab provide other full-interface evidence. It finds a
scrollable container within that full interface and excludes the general sidebar
and document. A Reviews-labelled preview feed alone cannot override More reviews.
For layouts without recognized headings/tabs/feeds, a fallback combines the active
place's observed reviews-route marker with a dedicated scrollable review container.
It excludes visible business-detail actions or a More reviews opener inside the
scroller, and excludes document scrolling. Sharing a parent `<main>` with an opener,
retaining a place heading/tab strip, or containing hidden overview controls does
not reject an otherwise valid reviews-route scroller. This is a
heuristic for the reported layout, not a guarantee for every Maps variation.
Lazy loading is expected: collection begins with currently rendered cards and
reads new cards after scrolling; it never requires all reviews to be loaded or a
match against a displayed review total. Forty cards alone do not establish mode.
When no restaurant heading is available, the decoded place name in the Maps URL
is used and marked as `url_path` in diagnostics and “from Maps URL” in the popup.
When the route contains several businesses, identity keys use the final active
place block, so an earlier business does not mask a change in the current target.
It never scrolls the map or document. DOM
selectors live in `review-parser.js` and may require changes as Maps changes. It
clicks recognized More / Mehr / Ещё controls, excluding owner replies. If expansion
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
Same-place URL query/data changes and generic Reviews headings are tolerated.
Place identifiers, place-path identity, and non-generic restaurant names guard
against switching restaurants. The original source URL remains stable in exported
records throughout a run. When a full panel is replaced, the collector waits up to
10 seconds to reacquire it, retains deduplication state, and resumes observing the
new panel. It pauses capture/scrolling when identity cannot be verified and stops
with an exact reason if recovery fails. The same logic applies on Resume.
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

English, German, and Russian dates are supported in the extension: for example,
`3 weeks ago`, `vor 3 Wochen`, `3 недели назад`, `неделю назад`, and Russian month
names (`9 ноября 2026`). Russian relative labels remain estimated; sub-day,
edited, invalid, future, or otherwise unrecognized labels remain unknown. Raw
dates and review text are preserved verbatim in all popup languages. JSON/CSV
column names, machine status/diagnostic keys, and the Python importer schema stay
stable. Technical error details can retain their original wording.

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

## Diagnostic logs and troubleshooting

After pressing Start, expand **Collection log / Sammlungsprotokoll / Журнал сбора**
to see the last 12 events, or use **Download log / Protokoll herunterladen /
Скачать журнал** to download `rri-log-<run>.json`. The log remains downloadable
after a panel-detection failure with zero reviews, popup closing/reopening, or
navigation, as long as local storage writes succeeded. Saved runs select their own
logs. The in-tab console also receives the same `[RRI]` events.

The file includes stage timestamps/elapsed time, source URL/restaurant identity,
matched control kind, panel-detection decisions, unique/parsed/skipped counts,
requested scrolls and measured before/after positions, and the stopping reason.
It does not contain review bodies, reviewer names, avatars, account details,
credentials, cookies, full page HTML, or a browser profile. It is separate from
review JSON/CSV export and does not change that schema.

Interpret key events as follows:

| Event | Meaning |
| --- | --- |
| `start_requested` | Options and initial detection, including whether auto-scroll is enabled |
| `open_control_found`, `open_control_clicked` | A Reviews tab, More reviews button, or count button was selected/clicked through normal UI; this alone does not prove the list opened |
| `panel_detection`, `panel_ready` | Scoped container candidates/rejections and successful list detection |
| `initial_collection` | Persisted starting counts, unresolved expansions, and rejected card parses |
| `scroll_requested`, `scroll_result` | Requested panel movement and actual `before`, `after`, `moved` measurements |
| `manual_scrolling_enabled` | Automatic scrolling was unchecked |
| `start_failed`, `collection_stopped` | Exact reason no collection/scrolling began, or why it ended |

The log keeps at most 300 events: the first 20 plus the latest 280, with a dropped
count. Writes are serialized/debounced locally. Committed logs survive popup/tab
closing; an abrupt page/browser shutdown may lose pending writes. Export before
uninstalling the extension, which clears its storage.

To reproduce a no-scroll issue, reload the extension, refresh Maps, leave the
restaurant overview open, set the limit to **0** and enable automatic scrolling.
Press Start, wait for collection or the error, then download the log. A nonzero
limit already reached by initial cards correctly stops before scrolling and is
recorded as `text_limit`. An access restriction is logged before any UI click.
No CAPTCHA/authentication bypass is attempted.

The popup compares the installed extension version with the live content-handler
version. If they differ, it explicitly requests a Maps-tab refresh; a newly
injected parser cannot disguise an older message handler. Saved data/log export
remains accessible even when that startup check fails.

## Real-data acceptance check (still pending)

For the 0.1.6 fix, click **Reload** on this extension's card at
`chrome://extensions`, then **refresh the Maps tab** to remove old injected scripts.
Reopen the full More reviews panel and Start. Also retest Start from preview mode.
Expand **Panel diagnostics** in the popup: check current URL, restaurant name,
mode, detected/full-panel card counts, scrollable_found, panel evidence,
start_failed_panel_detection, and stopping_reason. Panel reacquisitions are counted.
`page_language` reports the Maps document language (for example `ru-DE`), and
`supported_languages` lists `en`, `de`, and `ru`.
`review_route_hint`, `restaurant_name_source`, and `scroll_candidates` explain the
fallback. Each candidate reports only its tag/role, card count, client/scroll
heights, current scroll position, local structural flags, and rejection reason—no
review content or reviewer attributes. Confirm `extension_version: "0.1.6"` and
`content_script_version: "0.1.6"`.
An opener outside the scroller may set `opener_in_shared_main: true`, which is
informational and does not reject it. Actual blockers are individually named
`business_details_in_scroller` or `preview_opener_in_scroller`.
An active Reviews tab scoped to the same pane is positive full-list evidence, so
retained business controls do not veto that verified tab's list. All reviews /
Alle Rezensionen / Все отзывы is classified as a filter only with full-interface
context and appropriate container/control structure. It is still an entry in
ordinary overview mode. A dedicated scroller on the active place's review route,
under its confirmed Reviews tab and without overview heading/tabs/business
details, is not rejected by a residual More reviews button. Ambiguous preview
containers and document scrolling remain excluded. Candidate diagnostics include
`opener_kind`, `ignored_all_reviews_filters`, `verified_dedicated_list`, and
`opener_ignored_in_verified_list` so these decisions appear in downloaded logs.
After Start, `scroll_attempts` and `last_scroll` report the requested panel movement
(`before`, `after`, `moved`) and `automatic_scrolling` shows the selected setting.
If
`panel_evidence` is `reviews_route_scroller`, the route-and-scroller fallback was used.
Diagnostics include no reviewer fields, cookies, credentials, or account details;
concise Start-failure/reacquisition events are also logged with the `[RRI]` prefix
in the Maps tab's content-script console. If detection fails, report these status
fields, without sharing account/reviewer data.

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
