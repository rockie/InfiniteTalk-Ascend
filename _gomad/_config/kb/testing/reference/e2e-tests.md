---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# End-to-End Tests

## Scope

An end-to-end test drives the whole system the way a real user would. For a web app that means a browser clicking real buttons against a real server and a real database. For a CLI tool that means spawning the binary in a subprocess and asserting on stdout, stderr, and exit codes. For a service-to-service API it means the HTTP client, the HTTP server, and all intermediate layers, running together.

E2E tests are expensive: they are slow, flaky, hard to debug, and sensitive to environmental drift. That cost is the reason you keep them small and focused.

## Framework picks

- **Web UIs.** A modern browser-automation library with a first-class test runner is the right default. Pick one that offers auto-waiting for elements, built-in retries on specific actions (not on the whole test), and trace/video capture on failure.
- **CLI tools.** A lightweight harness that spawns the binary with `child_process.spawnSync` or the language's equivalent, collects stdout/stderr, and asserts on exit code. Keep the harness itself under 100 lines; it is the test runner for your real test cases.
- **HTTP APIs.** An HTTP client inside a normal unit-test file. Spin up the server once per suite, tear it down at the end, and hit real endpoints. Most language ecosystems have a `supertest`-style library that avoids the real network and talks directly to the in-process handler.

Avoid mixing frameworks inside the same test run. A single source of truth for "what is an E2E test in this project" makes the suite cheaper to maintain.

## How many E2E tests to write

Not many. For most applications, five to twenty E2E tests covering the critical user paths is the right order of magnitude — sign up, sign in, the two or three revenue-bearing flows, an admin path, and nothing else. Everything below the critical-path threshold belongs in an integration test.

The honest test is: if this test breaks, does a real user have a real problem? If the answer is "maybe, depending on rare conditions", it is not a critical path.

## Flakiness mitigation

Flaky E2E tests lose their value almost immediately — once the team starts treating failures as noise, real regressions slip through. Three rules help:

- **Explicit waits, not sleeps.** Wait for a specific element or event, with a generous time budget. `sleep(N)` is a confession that the test does not know what it is waiting for.
- **Deterministic seeds.** Reset the database to a known state at the start of each test. Do not rely on the previous test's side effects, and do not rely on the real clock — freeze time or use relative dates ("yesterday", "in 7 days") derived from a fixed anchor.
- **Retry-once on failure, not retry-until-pass.** A single automatic retry absorbs the rare real flake (a network blip). An unlimited retry masks real bugs that only reproduce 20 % of the time.

## Running cost in CI

Budget the E2E suite a fixed slot in the CI pipeline — "runs in under five minutes" is a common target — and enforce it. If the suite starts to exceed the budget, that is a signal to delete the least-load-bearing tests, not to raise the budget. An E2E suite that keeps growing ends up back in the "giant flaky suite that gets bypassed" anti-pattern.
