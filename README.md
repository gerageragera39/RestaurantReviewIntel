# Restaurant Review Intelligence

**New collection route: normal-Chrome Manifest V3 extension.** The existing Python
scraper is preserved. Load [`extension/`](extension/README.md) unpacked to collect
from an already open full Google Maps Reviews panel in your regular Chrome
session. No credentials or cookies are requested. It includes local persistence,
pause/resume, bounded panel scrolling, JSON/CSV exports, and a Python importer:

```powershell
.\.venv\Scripts\python.exe -m rri.extension_import "C:\path\to\downloaded-reviews.json" --output-prefix data/exports/extension-import
```

**Extension live milestone: NOT VERIFIED.** No real reviews were collected and
0 of 10 records were manually checked. Browser-control tooling stopped before
installation in personal Chrome; this does not establish a Maps access failure.
Offline fixtures and a real unpacked-extension storage/export test run separately
from the pending [live acceptance check](extension/VERIFICATION.md).
The repository suite passes **193 tests**, with **1 opt-in live test skipped**;
38 tests specifically exercise the extension DOM, exports, importer, and MV3 runtime.

A local-first Python 3.11+ university review-collection project. Playwright Chromium
reads the rendered Google Maps DOM. No paid API, undocumented review endpoint,
cloud service, database server, or frontend. This phase extends the existing package.

**Current live result (2026-11-09): BLOCKED.** The supplied Piccolo Mondo place
exposed a restricted anonymous Maps view. Its saved public DOM showed **59 reviews**
and three preview cards, not the full list. A dedicated persistent-profile check
after cookie consent remained restricted. The user's subsequent manual Google
account sign-in was refused with: “Dieser Browser oder diese App ist unter Umständen
nicht sicher.” Authentication was not completed, so authenticated collection is
**NOT TESTED**, not assumed to work. No review dataset from these attempts is retained.
These results describe the tested sessions, not all normal browsers or networks.

Evidence and counts: `data/reports/piccolo-mondo-access-comparison.json`; prior
anonymous screenshots/sanitized HTML remain in `data/debug/`. The security-warning
text was reported by the user during manual login; no account-page screenshot,
email address, or credential form was captured. No further Google access attempt
was made after that explicit security refusal.

## Install (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location) '.browsers')
.\.venv\Scripts\python.exe -m playwright install chromium
$url = (Get-Content examples/piccolo-mondo.url.txt -Raw).Trim()
```

After activation, use `rri` directly. `python -m rri` is equivalent. Set the browser
path in each shell if using the project-local install. Playwright requires a
[matching browser binary](https://playwright.dev/python/docs/browsers).

## Anonymous and persistent sessions

```powershell
# Anonymous, visible browser, up to 50 text reviews
.\.venv\Scripts\rri.exe scrape --url $url --limit 50 --headed --debug

# Manual sign-in, only where Google permits this browser/session
.\.venv\Scripts\rri.exe login --url $url --profile-dir data/browser-profile

# Reuse that isolated session; no artificial review limit
.\.venv\Scripts\rri.exe scrape --url $url --profile-dir data/browser-profile --limit 0 --headed --debug
```

These commands document the interface; **do not retry the current rejected login
with evasion or alternative identities**. Stop on any CAPTCHA, automation denial,
or unsafe-browser warning. The implemented login mode is for sessions where
ordinary manual authentication is permitted, not a workaround for Google's refusal.

`login` opens visibly. The user handles consent and authentication directly in
Chromium, returns to the restaurant page, and presses Enter in the terminal.
RRI does not fill/click credential fields, read passwords, import cookies, or
inspect the profile's session files. A bounded event loop tolerates normal login
navigation and new tabs, then reopens the supplied Maps URL and verifies the full
Reviews interface. `ACCESS_VERIFIED` means that interface opened; it is not a
collection result or a claim of complete history. The observable account indicator
is reported as `authenticated_ui` or `not_observed`, without reading its identity.
Cookie consent and the presence of a profile alone do not establish authentication.

`--login-timeout-ms` defaults to 600000; login is always visible. Ctrl+C cancels.
Use one process per profile; concurrent profile use fails explicitly. A nonempty
non-RRI directory is rejected so the tool never reuses your normal Chrome profile.
Only a new isolated directory or one carrying RRI's marker is accepted. Profile
state is preserved on close and is not deleted after a run.

**Profile privacy:** persistent profiles deliberately contain cookies and session
authentication material. Keep them local, do not share them, and never commit them.
`data/browser-profile/` is ignored, and RRI creates a `*` `.gitignore` inside every
custom profile directory. It never exports profile contents to review or debug
files. Do not force-add ignored files or use the directory for unrelated files.
[Playwright's persistent-context API](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
requires a dedicated user-data directory rather than the regular Chrome profile.

## Collection and bounds

1. Navigate normally. Handle recognized English/German Google consent, preferring
   Reject all / Alle ablehnen. Unsupported consent is an explicit failure.
2. Check separately for a limited Maps view, mandatory sign-in, CAPTCHA/traffic
   blocking, and a sign-in browser-security rejection. Never treat previews as a
   complete review list. A normal optional sign-in suggestion can be dismissed
   once; repeated or mandatory authentication stops scraping and suggests `login`.
3. Open the semantic Reviews / Rezensionen tab (or a specific review-list action),
   verify its selected state, and locate the review scroll panel. Do not confuse
   review-writing/disclosure buttons or the main document with the review list.
4. Select the All reviews filter when available and Newest / Neueste when supported.
   Missing sorting/filter evidence is reported rather than invented.
5. Expand More / Mehr, read full displayed review text, stars, raw date, native ID,
   and an optional review link. Collect rating-only records too. Deduplicate native
   IDs while scrolling the actual review container, preserving collection order.
6. Stop at the positive text-review limit, an explicit end marker, idle/scroll bounds,
   a time budget, or an access/error condition. **`--limit 0` removes only the artificial
   review-count limit**; all scrolling/time budgets still apply.

| Setting / CLI flag | Default | Meaning |
| --- | --- | --- |
| `limit` / `--limit` | 50 | Text-review limit; 0 means no artificial limit |
| `headed` / `--headed`, `--no-headed` | true | Visible Chromium |
| `profile_dir` / `--profile-dir` | null | Isolated persistent profile; omitted = ephemeral anonymous |
| `timeout_ms` / `--timeout-ms` | 30000 | Navigation/locator operation timeout |
| `collection_timeout_ms` / `--collection-timeout-ms` | 180000 | Collection budget, excluding manual-login wait |
| `max_scroll_iterations` / `--max-scroll-iterations` | 100 | Maximum container scrolls |
| `max_idle_iterations` / `--max-idle-iterations` | 5 | Consecutive passes without new unique IDs |
| `scroll_wait_ms` / `--scroll-wait-ms` | 1500 | DOM update wait after scroll/sort |
| `debug` / `--debug`, `--no-debug` | false | Redacted public-page diagnostics |
| `export_dir` (config) | data/exports | Review exports |
| `report_dir` (config) | data/reports | Machine-readable run reports |
| `debug_dir` (config) | data/debug | Public-page diagnostic artifacts |

CLI flags override JSON config, which overrides defaults. Use `--config
config.example.json`. Unknown settings and invalid values fail early. Relative
paths use the current working directory. Common HTTPS Google place/CID/place-ID
URLs and Maps short links are supported; unrelated sites/search URLs are rejected.

## Completeness and run reports

Each collection writes a `data/reports/reviews-<UTC-timestamp>.report.json`, including
failures when disk access permits. Login checks write a separate login report.
Collection reports contain source/session mode, observable authentication, whether
the full panel opened, displayed totals before/after, unique/text/rating-only counts,
raw/normalized-date counts, sorting/filter evidence, status, and exact stopping reason.
Restriction evidence is kept separate from the review dataset. Failure reports
never pretend that visible preview cards were collected as the full review list.

- **COMPLETE** requires the full panel, confirmed All reviews filter, exhaustion or
  an idle stop, a known unchanged displayed total matching every distinct native
  review ID, and retained records covering that total. Fallback hashes cannot prove
  completeness. The scope is only the **displayed source snapshot** at that time,
  not all reviews ever posted, deleted/hidden reviews, or undisclosed platform data.
- **PARTIAL** covers a positive limit, scroll/time cap, unknown/changing/mismatched
  counts, unavailable filter evidence, or otherwise unverified coverage. An idle
  stop alone does not prove completeness. Previously validated records can be saved
  as PARTIAL when the collection budget expires; incomplete/truncated records are
  never manufactured to fill the requested count.
- **BLOCKED** means collection could not proceed because of source access, unresolved
  consent, sign-in, CAPTCHA/automation refusal, or browser-security rejection. No
  blocked source is retried with alternate identities/access paths. Hard source
  failures write diagnostic statistics but do not export a misleading review dataset.

Stop reasons include `limit`, `exhausted`, `idle_limit`, `scroll_limit`,
`collection_timeout`, `restricted_view`, `login_required`, `browser_security_block`,
and typed operational failures. A reported displayed count is optional; abbreviated
or ambiguous counts are not guessed. Count changes invalidate a completeness claim.

Exit codes: 0 for an exported COMPLETE/PARTIAL collection, 1 for a source/export
failure, 2 for invalid arguments/config, 130 for cancellation. Console output and
logging include counts, sorting, status, stopping reason, file paths, and elapsed time.

## Exports and date transparency

Successful/partial permitted collection writes four matching-schema UTF-8 files:

```text
data/exports/reviews-<UTC-timestamp>.json         Text reviews only, NLP-ready
data/exports/reviews-<UTC-timestamp>.csv
data/exports/reviews-<UTC-timestamp>-all.json     Includes rating-only records
data/exports/reviews-<UTC-timestamp>-all.csv
```

The `-all` files preserve collection order including rating-only records. JSON is an
array; CSV quotes multiline Unicode text. Optional fields are null / empty cells.
Each file is replaced atomically, but the file set is not a transaction: disk failure
may leave an already completed file. Reports identify counts and paths.

| Field | Meaning |
| --- | --- |
| restaurant_url | Exact supplied source URL |
| restaurant_name | Selected restaurant's displayed name, not a sponsored heading |
| review_id | Namespaced native DOM ID; otherwise deterministic fallback hash |
| text | Full expanded displayed text; empty for rating-only records in -all files |
| star_rating | Integer 1–5, not a restaurant aggregate or aspect sub-rating |
| review_date_raw | Date label exactly as displayed, without rewriting/stripping |
| date_estimate | Optional ISO calendar date |
| date_accuracy | exact / estimated / unknown |
| scraped_at | Timezone-aware ISO timestamp in UTC |
| review_url | Optional DOM-provided public review link |

English/German relative days/weeks/months/years, today/yesterday/heute/gestern, ISO,
month-name, and German dotted calendar dates are supported. Relative ages are always
**estimated**; calendar arithmetic handles month ends/leap years. Unrecognized,
edited, ambiguous, invalid, future, and sub-day labels retain the raw text and remain
unknown. The reference date is explicit and matches the browser's UTC timezone.
No rounded age is falsely presented as an exact publication timestamp.

Native IDs are `google_maps:native:<id>`. Fallback IDs hash the canonical place URL,
NFC/whitespace-normalized text, stars, and raw date. No reviewer identity is used.
Edits, advancing relative dates, or changing URLs can change fallback IDs; identical
anonymous/rating-only records can collide. Deduplication is per run, not a database
of cross-run history. Fallback IDs cannot establish a COMPLETE collection.

## Failures and privacy

The original failure states remain: inaccessible_page, consent_required,
reviews_not_found, blocked_captcha, timeout, extraction_failed. A separate
`restriction_kind` distinguishes restricted_view, login_required, captcha,
automated_access_blocked, and browser_security_block. A browser-security rejection
is not reported as evidence of a CAPTCHA. Starting/locking/profile errors are clear
failures; diagnostic-write errors do not replace the original source failure.

`--debug` saves a redacted public Maps screenshot and sanitized DOM HTML. Reviewer
headers, profile/account elements, images, and inputs are masked/redacted; scripts,
comments, frames, forms, links, inline handlers, and non-allowlisted attributes are
removed. **No debug snapshots are taken on account/login pages.** Review exports
exclude reviewer names, profile links, contribution counts, avatars, owner replies,
and unnecessary personal metadata. Review text may itself contain author-supplied
personal details; inspect artifacts before sharing. All data, reports, profiles,
virtual environments, and browser binaries are ignored by Git.

There is no credential automation, CAPTCHA solving, cookie import, stealth,
fingerprint spoofing, proxy rotation, automation-hiding flags, paid-service fallback,
or fixture fallback in live mode. Google's own rendered page may make network
requests; RRI itself reads the DOM rather than calling review backend endpoints.

## Architecture and tests

The existing `src/rri` model/date/storage/CLI/service separation is preserved.
`sources/base.py` provides ScrapeRequest, CollectionResult, and SourceAdapter.
The Google Maps package contains adapter.py, extraction.py, centralized selectors.py,
diagnostics.py, plus browser.py for isolated lifecycle and login.py for manual access
verification. No new services or large abstraction framework.

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location) '.browsers')
.\.venv\Scripts\python.exe -m pytest -q
```

Saved synthetic HTML tests abort/intercept network requests. They cover model/date
validity, extraction/expansion, native/fallback IDs, real container scrolling,
pagination/loading, bounded/incomplete collection, zero/unlimited limits, all-record
exports, independent completeness checks, login-required/security detection,
transient sign-in navigation, profile isolation/locking, actual persistence of
synthetic session state, diagnostics, reports, config, and CLI. Tests never use the
user's real profile. They do not establish live Google access.

Live tests stay opt-in and separate. Only use a permitted session/authorized target;
do not run further attempts after a source security rejection:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/live -m live --live-url "$url" -q
# Optional already-permitted isolated profile:
.\.venv\Scripts\python.exe -m pytest tests/live -m live --live-url "$url" --live-profile data/browser-profile -q
```

Manual checks on a permitted run: verify restaurant identity, actual Newest order,
All reviews filter, displayed total, several expanded texts/stars/raw dates, native
ID uniqueness, rating-only records, normalized-date uncertainty, and final stop
reason. An idle cap or requested limit is not proof of full history. A stable count
match verifies only the displayed snapshot; independently inspect that source scope.

## Permitted demo alternative

For a verifiable full-history demo, obtain an **owner-authorized first-party feedback
export** with full text, stars, dates, IDs, and an independent total. That can establish
completeness for that explicitly supplied history without bypassing another platform.

The [official Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/)
is also a candidate under its
[academic dataset terms](https://s3-media0.fl.yelpcdn.com/assets/srv0/engineering_pages/f64cb2d3efcc/assets/vendor/Dataset_User_Agreement.pdf).
Use every review for a selected business in the released snapshot and validate
against that snapshot. It is **not guaranteed to contain a business's entire lifetime
platform history** or this Piccolo Mondo restaurant. This is a proposed alternative,
not a silent scraper fallback; no dataset was downloaded or substituted. Yelp's
landing page returned HTTP 403 in this environment, so download availability here
was not verified. Do not scrape Yelp's live pages as a workaround.

NLP, geographical discovery, UI, ranking, and new providers remain out of scope.
