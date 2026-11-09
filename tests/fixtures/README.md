These HTML fixtures are synthetic, minimal reproductions of Google Maps DOM
structures and English/German controls. They contain no actual reviewer identities
or live restaurant reviews. The restricted-view fixture preserves the wording of
the warning observed during the authorized Piccolo Mondo verification.

Fixture tests render these files in headless Chromium with all network requests
aborted. They verify DOM extraction and interaction logic; they do not establish
that Google will permit review collection in a live session. Live integration
tests live separately in `tests/live/` and require an explicit `--live-url`.

The extension's More reviews regressions use `extension_preview.html` (exactly
three previews and a normal button opening a full dialog), `extension_full_de.html`
(German full-dialog labels and a different scroll layout), and `extension_spa.html`
(same-place History API navigation, generic review heading, and delayed panel
replacement). All are synthetic saved HTML, not captures of the user's session.

`extension_lazy_reviews.html` renders 40 synthetic cards without recognized panel
labels or a restaurant heading, then adds reviews/removes older DOM nodes only
on scroll. `extension_reported_route.txt` is the public restaurant URL supplied
with the diagnostic report; it contains earlier and current place blocks. This
fixture matches reported symptoms, not the actual live HTML, which was unavailable.
