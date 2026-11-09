# Verification record — 2026-11-09

## Initial implementation: personal Chrome NOT VERIFIED

- Installation in the user's normal authenticated Chrome: not completed.
- Full Reviews panel access in that session: not inspected during this task.
- Actual unique real reviews collected by this extension: **0** (no live run).
- Target of 30 unique real text reviews: **not established**.
- Real JSON/CSV export and Python import: not performed.
- Manually checked real records: **0 of 10**.
- Browser-control limitation: Computer Use stopped because it could not determine
  the current Chrome URL confidently enough to enforce policy. No further browser
  control was attempted after that stop. This is a tooling limitation, not evidence
  that Google Maps denied the extension or that reviews are unavailable.

The earlier Python/Playwright restriction reports remain unchanged. They do not
establish whether this extension works in the user's authenticated normal browser.

## More reviews fix (0.1.1): live retest pending

The user subsequently reported manual testing of the earlier build in normal
Chrome: three preview reviews were extracted, but collection failed after opening
More reviews. That report is diagnostic context, not verification of full-list
collection or of the current fix. No new personal-Chrome run was attempted here.
No 30-review dataset or ten manually checked full-list records is established.

Before changing the implementation, two saved-DOM regression tests failed:

- With previews earlier in the DOM and a full reviews dialog open, findPanel()
  returned the preview sidebar instead of the dialog's actual scroll container.
- Changing only the query string within the same restaurant SPA route stopped the
  collector as page_changed.

The patch scopes detection to full-review roots, opens the ordinary More reviews /
Weitere Rezensionen control on Start when necessary, waits for accessible cards,
compares restaurant identity, and reacquires same-place replacement panels with a
10-second grace period. These are fixture-proven defects/fixes; the exact live
DOM that caused the user's report has not been inspected.

## Offline checks

Synthetic fixture tests and an actual unpacked MV3 runtime test are provided.
The runtime check uses a temporary test profile, synthetic records, real
chrome.storage.local, actual popup pages, JSON/CSV downloads, and browser restart.
It does not test the user's session or live Maps selectors.

The message-bridge test also exercises scripting injection, actual Chrome messages,
pause/resume/stop, incremental fixture collection, and collected-data export. It
uses a temporary manifest with a test-only fixture host permission; a human toolbar
activeTab grant remains unverified. Production extension scripts are unchanged.

Executed result: **307 passed, 1 skipped** across the repository suite. The skipped
test is the opt-in live integration test. Extension-specific coverage comprises
147 saved-DOM tests and 5 unpacked-runtime tests. Twenty-one panel regressions cover
three-card previews, misleading feed labels, English/German More reviews controls,
delayed opening, full-dialog priority, alternate scroll containers, SPA URL/heading
changes, immediate/delayed DOM replacement, replacement while paused, removed
virtual cards, wrong-restaurant rejection, and diagnostic failure reasons.
They also cover changing route identifier namespaces, exclude synthetic reviewer
headings from restaurant identity, and distinguish optional login/review text from
a blocking sign-in dialog.
See extension/README.md for the
remaining acceptance steps. Do not replace this pending result with a live success
claim based only on fixture tests.

## Asia Imbiss Le follow-up (0.1.2): live retest pending

The user supplied diagnostics showing 40 detected cards, no restaurant heading,
PREVIEW_MODE, and no accepted full-review container after opening More reviews.
The old parser required recognized dialog/feed/tab/sort semantics, so it could
reject a rendered list despite seeing its cards. It did not require the complete
review history to load at Start; lazy loading was already part of the collector.

The supplied URL also includes an earlier McDonald's block before the current
Asia Imbiss Le block. The first-match identity parser selected the earlier IDs.
Version 0.1.2 reads the final active place block, exposes URL-based restaurant-name
fallback, and adds a guarded dedicated-scroller fallback using the active route's
review marker. Card count alone is insufficient. Structural candidate diagnostics
now explain why each scroll ancestor was accepted/rejected.

Seven synthetic tests based on the supplied symptoms/URL cover initial 40-card
collection, subsequent scroll-only batches with virtualization, source name/raw
dates/ratings/export, active rather than historical IDs, text limits, rejection of
an earlier place's review marker, rejection of general overview containers, and
stopping when the active place changes. They do not reproduce the uninspected live
HTML exactly. A direct read-only browser inspection was attempted but Computer
Use stopped because it could not verify the current Chrome URL; no additional UI
actions were attempted. No live success is claimed for 0.1.2.

## Pizzastar shared-wrapper rejection (0.1.3): live retest pending

The user's 0.1.2 diagnostics identified a scroll ancestor with ten cards, 1092px
client height and 4437px scroll height, rejected as overview_or_preview_container.
Thus collection never started; no scroll was attempted. The grouped rejection did
not identify which condition matched in the uninspected live DOM.

Seven new synthetic regressions exercise the contributing code paths. Before the
fix, five failed: shared-main full-list detection, retained title, retained tab,
hidden address control, and actual scrolling/scroll-triggered collection. Two
negative cases already passed: a local preview opener or visible business-address
action inside the scroller. All now pass.

The parser no longer treats a shared main wrapper, heading, tab strip, or hidden
overview node as sufficient rejection evidence on the active review route. Actual
visible business details/local preview openers and document scrolling remain
excluded. Diagnostics expose each condition separately, version 0.1.3, and actual
scroll positions/attempts. Synthetic full-list collection grows from 10 to 20
reviews after movement of the selected element while window.scrollY remains zero.
This is verified fixture behavior; the user's live scroller has not been retested.

## Three-language support (0.1.4): fixture/runtime verified

The LEON's URL was opened in the separate in-app browser. That session used
Russian (`ru-DE`), displayed 23 reviews and three preview cards, and exposed
`Ещё отзывы (20)`, `Ещё`, `5 звезд`, `4 звезды`, `3 недели назад`, and `неделю назад`.
More reviews produced a sign-in suggestion without exposing the full list there.
This browser/session is separate from the user's normal Chrome, which the user
reported was mostly English. The Russian observation is not claimed to explain
the normal-Chrome scrolling bug. No credentials/cookies were read or exported.

At the user's explicit request, the extension now recognizes English, German, and
Russian review controls, panels, ratings, date labels, end markers, and restriction
messages. The popup has a persisted English / Deutsch / Русский selector for its
controls, common status/error messages, and help. It does not change Maps language
or translate exported review text/date strings/schema keys.

Fifty-five new synthetic tests cover all three collection flows, Russian rating
forms, dates/uncertainty, and localized restrictions/end markers. The actual MV3
runtime test also switches all popup languages, reopens the popup to check saved
preferences/counts, and restarts its temporary browser. Screenshots are rendered
for language layout QA. Personal authenticated Chrome collection, 30 real unique
text reviews, and ten manual record checks remain unverified for this build.

## Automatic Reviews-tab opening and persistent logs (0.1.5)

At the user's request, Start now prefers the normal Reviews / Rezensionen / Отзывы
tab, falling back to More reviews or the review-count button. It waits for
same-restaurant full-list evidence and then attempts an immediate panel scroll
when automatic scrolling is enabled and the text limit has not already been met.
An active Reviews tab scoped to that pane can establish a full list even if Maps
retains business controls in its wrapper; overview-only controls still cannot
authorize collection on their own.

The 300-event bounded journal preserves startup plus recent events in extension
storage, appears in the popup, and downloads separately as diagnostic JSON even
after panel detection fails with zero reviews. Events cover control discovery and
clicking, detection snapshots, starting counts/parsing failures, actual scroll
positions, pause/resume, and exact failure/stop reasons. Tests explicitly assert
that synthetic reviewer-name/review-text sentinels do not appear in exported logs.

Twelve new saved-DOM tests cover three-language Reviews-tab opening with immediate
scrolling/new cards, count-button fallbacks, failure logging, text-limit/manual
no-scroll reasons, retention bounds, access stops before clicking, and identifying
an old content listener despite a newer injected parser. Two additional real MV3
runtime tests download successful/failed logs after popup reopening, verify the
log viewer, and confirm actual panel movement. These use temporary profiles and
test-only fixture host permission; production scripts/permissions are unchanged
except the described behavior. The user's personal Chrome run remains unverified.

## co:Lab diagnostic-log fix (0.1.6)

The user supplied `rri-log-2026-11-09T11-44-11-620Z-5b47bc24.json` from normal
Chrome. Both script versions were 0.1.5, language en-DE, limit 0, autoScroll true,
and scrollOnStart true. The journal proves that the Reviews tab was clicked,
became selected, and that the active place's review route and ten rendered cards
appeared within 333 ms. The candidate had client height 1169, scroll height 4850,
no overview heading/tabs/business details, and confirmed_reviews_tab true. The
sole blocker was preview_opener_in_scroller. After 10 seconds Start failed without
any scroll attempt or parsed review. This is a detector failure, not evidence of
failed scrolling, slow lazy loading, a stale script, or a different UI language.

The log records opener presence, not its caption; it does not prove that the
matched button was specifically All reviews. Four initial synthetic regressions
using All reviews / Alle Rezensionen / Все отзывы reproduced the same veto before
the patch. Version 0.1.6 distinguishes full-list filters from overview entries and
also accepts a residual entry button in the exact confirmed dedicated-list context
recorded by the user. It retains negative tests for ambiguous previews, local
openers without a confirmed tab, and the transient selected-tab/three-preview
overview state. New diagnostic flags show which rule authorized the list.

Nine new DOM tests and one additional real MV3 runtime scenario cover this fix.
The synthetic recorded transition now opens the list, moves its actual scroll
element, and retains 11 unique records after loading an additional card; the
document remains unscrolled. The downloaded runtime log confirms movement and
record counts. The original downloaded log was read without modification. This
build still needs a fresh run in the user's personal Chrome session; no live
successful collection or ten-record manual verification is claimed.
