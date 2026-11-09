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

`extension_shared_wrapper_reviews.html` starts with ten cards in a 1092px-tall
scroller and retains More reviews elsewhere under the same main wrapper. It tests
the Pizzastar diagnostic's false overview/preview rejection and scroll-triggered
loading. Header/tab/hidden-control variations and true overview controls are
tested separately; this remains synthetic HTML rather than the user's live DOM.

`extension_multilingual_reviews.html` provides English, German, and Russian
preview/full list states, text expansion, rating-only cards, and scroll-triggered
virtualization. Russian control/rating/date labels include strings observed in
the separate LEON's in-app-browser check. Its review bodies are synthetic; it is
not a capture of the user's authenticated Chrome session.

`extension_reviews_tab.html` exposes a normal Reviews tab (and count/More reviews
fallback) opening a list with retained business controls. It loads a further card
on scroll. Synthetic private-text/name sentinels are deliberately present in cards
to verify that diagnostic journals omit review text and reviewer identities.

`extension_colab_filter.html` reproduces the co:Lab log's overview-to-Reviews
transition: three previews, selected Reviews tab, active-place review route,
dedicated ten-card scroller, and a retained list control. Tests vary All reviews
filters and residual More reviews controls. The source log did not include the
button caption; these are synthetic alternatives reproducing its exact veto,
not a claim to have captured the user's DOM. Another card loads on panel scroll.
