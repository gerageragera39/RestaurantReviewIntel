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

Executed result: **221 passed, 1 skipped** across the repository suite. The skipped
test is the opt-in live integration test. Extension-specific coverage comprises
64 saved-DOM tests and 2 unpacked-runtime tests. Twenty-one panel regressions cover
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
