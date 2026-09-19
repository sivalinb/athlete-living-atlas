# Screenshot evidence and coverage

Seventeen unmodified browser captures from the running application. All health data shown is fictional. Agent screenshots visualize saved synthetic evaluation runs. The three experiment overviews show all **120 case instances** (40 per experiment); individual case outcomes are also retained in [the source report](evidence/braintrust-evidence.json). This is a product-state coverage gallery, not a claim of exhaustive testing of all possible inputs or devices.

Desktop captures use the browser’s existing 1280 × 720 viewport; the narrow capture uses its existing 649 × 908 viewport. Some captures intentionally scroll to show detail. Images are not composited. Static images establish rendered states; animation behavior also has automated timing tests and a manual DOM motion check.

[Machine-readable hashes](screenshots/manifest.json) are checked by `python3 -m living.verify`.

## Coverage index

- [Heart paused](#01-heart-paused) — Session 1 at 05:20; observed BPM and replay controls.
- [Heart playing](#02-heart-playing) — Playback active; separate DOM observations confirmed changing pulse scale.
- [Reduced motion](#03-reduced-motion) — Motion disabled with data and controls retained.
- [Missing heart-rate sample](#04-missing-signal) — Fictional signal gap; no invented BPM or pulse.
- [Trail movement](#05-trail-moving) — Burro position follows normalized recorded coordinates.
- [Trail stop](#06-trail-stop) — Slow segment at 10:50; 0 km/h and stop duration, without behavioral inference.
- [Thirty-night sky](#07-recovery-sky) — Thirty selectable observations; latest night selected.
- [Selected night](#08-recovery-selected) — 2026-08-31 selected; stage durations updated.
- [Improved Nebius: every case](#09-nebius-all-40) — case-001 through case-040 visible; 90% pass rate.
- [Failed case detail](#10-agent-failed-case) — case-012 failed; question, route, and outcome remain visible.
- [Baseline local: every case](#11-baseline-all-40) — case-001 through case-040 visible; 75% pass rate.
- [Improved local: every case](#12-improved-all-40) — case-001 through case-040 visible; 100% pass rate.
- [Empty results](#13-empty-failure-filter) — Improved local has no failed cases; explanation and return path remain available.
- [Failures only](#14-failure-filter) — Four failed Nebius cases remain visible.
- [Blocked requests](#15-blocked-filter) — Six safety cases; case-035 selected, outcome blocked, evaluation passed.
- [Narrow layout](#16-narrow-layout) — 649-pixel-wide browser layout; natural viewport, no screenshot resizing.
- [Reading guide](#17-reading-guide) — Interpretation limits, fictional provenance, and motion controls explained.

<a id="01-heart-paused"></a>
## Heart paused

Session 1 at 05:20; observed BPM and replay controls.

![Heart paused](screenshots/01-heart-paused.jpg)

<a id="02-heart-playing"></a>
## Heart playing

Playback active; separate DOM observations confirmed changing pulse scale.

![Heart playing](screenshots/02-heart-playing.jpg)

<a id="03-reduced-motion"></a>
## Reduced motion

Motion disabled with data and controls retained.

![Reduced motion](screenshots/03-reduced-motion.jpg)

<a id="04-missing-signal"></a>
## Missing heart-rate sample

Fictional signal gap; no invented BPM or pulse.

![Missing heart-rate sample](screenshots/04-missing-signal.jpg)

<a id="05-trail-moving"></a>
## Trail movement

Burro position follows normalized recorded coordinates.

![Trail movement](screenshots/05-trail-moving.jpg)

<a id="06-trail-stop"></a>
## Trail stop

Slow segment at 10:50; 0 km/h and stop duration, without behavioral inference.

![Trail stop](screenshots/06-trail-stop.jpg)

<a id="07-recovery-sky"></a>
## Thirty-night sky

Thirty selectable observations; latest night selected.

![Thirty-night sky](screenshots/07-recovery-sky.jpg)

<a id="08-recovery-selected"></a>
## Selected night

2026-08-31 selected; stage durations updated.

![Selected night](screenshots/08-recovery-selected.jpg)

<a id="09-nebius-all-40"></a>
## Improved Nebius: every case

case-001 through case-040 visible; 90% pass rate.

![Improved Nebius: every case](screenshots/09-nebius-all-40.jpg)

<a id="10-agent-failed-case"></a>
## Failed case detail

case-012 failed; question, route, and outcome remain visible.

![Failed case detail](screenshots/10-agent-failed-case.jpg)

<a id="11-baseline-all-40"></a>
## Baseline local: every case

case-001 through case-040 visible; 75% pass rate.

![Baseline local: every case](screenshots/11-baseline-all-40.jpg)

<a id="12-improved-all-40"></a>
## Improved local: every case

case-001 through case-040 visible; 100% pass rate.

![Improved local: every case](screenshots/12-improved-all-40.jpg)

<a id="13-empty-failure-filter"></a>
## Empty results

Improved local has no failed cases; explanation and return path remain available.

![Empty results](screenshots/13-empty-failure-filter.jpg)

<a id="14-failure-filter"></a>
## Failures only

Four failed Nebius cases remain visible.

![Failures only](screenshots/14-failure-filter.jpg)

<a id="15-blocked-filter"></a>
## Blocked requests

Six safety cases; case-035 selected, outcome blocked, evaluation passed.

![Blocked requests](screenshots/15-blocked-filter.jpg)

<a id="16-narrow-layout"></a>
## Narrow layout

649-pixel-wide browser layout; natural viewport, no screenshot resizing.

![Narrow layout](screenshots/16-narrow-layout.jpg)

<a id="17-reading-guide"></a>
## Reading guide

Interpretation limits, fictional provenance, and motion controls explained.

![Reading guide](screenshots/17-reading-guide.jpg)
