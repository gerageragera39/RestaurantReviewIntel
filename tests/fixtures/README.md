These HTML fixtures are synthetic, minimal reproductions of Google Maps DOM
structures and English/German controls. They contain no actual reviewer identities
or live restaurant reviews. The restricted-view fixture preserves the wording of
the warning observed during the authorized Piccolo Mondo verification.

Fixture tests render these files in headless Chromium with all network requests
aborted. They verify DOM extraction and interaction logic; they do not establish
that Google will permit review collection in a live session. Live integration
tests live separately in `tests/live/` and require an explicit `--live-url`.
