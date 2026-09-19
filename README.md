# Athlete Living Atlas

[![Verification](https://github.com/sivalinb/athlete-living-atlas/actions/workflows/atlas-ci.yml/badge.svg)](https://github.com/sivalinb/athlete-living-atlas/actions/workflows/atlas-ci.yml)

An animated alternative to Grafana for exploring wearable observations and agent evaluation evidence. A beating heart, a burro on a trail, a sky of sleep observations, and a constellation of agent outcomes replace conventional dashboard charts.

Built with Python, native JavaScript, CSS animation, and SVG. No frontend dependencies, API keys, or Grafana instance are required for the demo. The original [Athlete Observatory](https://github.com/sivalinb/athlete-observatory) remains a separate project.

**Public data is fictional.** Health scenes use generated fixtures; agent scenes use saved Braintrust runs over synthetic questions. The demo does not stream from an Apple Watch, calculate medical readiness, or infer animal behavior.

## See the experience

### Heart — recorded BPM becomes a visible pulse

![Paused heart replay with the observed heart rate](docs/screenshots/01-heart-paused.jpg)

Play, pause, scrub, select a workout, or accelerate the session. The illustrated pulse follows the current BPM independently of replay speed. Missing or stale samples stop the pulse; reduced motion disables it.

### Trail — follow the burro through a workout

![A burro follows the normalized workout route](docs/screenshots/05-trail-moving.jpg)

Recorded positions determine progress. GPS gaps remain gaps. A slow segment is an observation, not an explanation of why a runner or animal stopped.

### Recovery — thirty nights become a sky

![Thirty selectable night orbs with sleep duration details](docs/screenshots/07-recovery-sky.jpg)

Each orb represents a night; its area scales with recorded sleep duration. Select a night to inspect recorded sleep stages. Orb size is not a recovery score.

### Agents — every evaluation case stays visible

![All forty Nebius evaluation cases, including failures](docs/screenshots/09-nebius-all-40.jpg)

Three saved experiments contain **120 cases**: baseline local **75%**, improved local **100%**, and improved Nebius **90%**. Each star is a case. Inspect its question, route, outcome, latency, and reported token usage; filter failures or blocked requests. Missing model usage is labeled “Unreported.” These are development-set results, not an independent benchmark or newly rerun live experiments.

**[Open the complete 17-screenshot evidence gallery and coverage checklist](docs/SCREENSHOT_COVERAGE.md).** It includes all 40 cases in each experiment, playback, reduced motion, missing signal, a trail stop, night selection, failed and blocked cases, empty results, narrow layout, and the reading guide. Checksums are verified in CI.

## Run the demo

Requires Python 3.11+ and a modern browser. Node 22 is used only for JavaScript checks.

```sh
git clone https://github.com/sivalinb/athlete-living-atlas.git
cd athlete-living-atlas
python3 -m living.serve
```

Open **http://127.0.0.1:8787**. The checked-in synthetic assets work immediately. To rebuild them from the production importer:

```sh
python3 -m living.build_demo
```

For local investigator tools, generate a fictional database and pass it to the server:

```sh
python3 -m observatory.demo --db .local/demo.sqlite
python3 -m living.serve --db .local/demo.sqlite
```

[Local personal-data procedure, architecture, evaluation, and delivery](docs/PROCEDURE.md) · [Design alternatives and course implementation map](docs/DESIGN.md)

## Verification and delivery

```sh
npm run check
npm test
python3 -m unittest discover -s tests -v
python3 -m living.verify
```

GitHub Actions runs the Python and animation tests, rebuilds synthetic data and rejects drift, runs the 40-case local investigator evaluation, verifies public paths and screenshot hashes, and uploads the static site as a commit-specific artifact. There is no paid model call in CI. Hosted deployment is a separate exact-source Sites release; the procedure explains the boundary.

The deployable `dist/` is static. Optional Python APIs run only on loopback. Raw Apple Health ZIP/XML, databases, precise personal routes, secrets, and local traces are excluded from this repository. The personal exporter refuses to write a public bundle unless its database is explicitly marked synthetic.
